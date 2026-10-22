"""Ordinal-regression scorer: fitting, score mapping, extended features, label-free self-training and fallback."""

from __future__ import annotations

import random

import duckdb
import numpy as np
import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.stitch.blocking import build_candidate_pairs, load_records_table
from aurora_cdp.stitch.ordinal import (
    ALL_FEATURE_NAMES, EXTENDED_FEATURE_NAMES, OrdinalModel, all_features, context_from_frame, corpus_context, extended_features,
    fit_ordinal, score_frame_ordinal, self_train, train_from_candidates,
)

CFG = load_config(use_last_best=False)


def test_fit_recovers_ordered_thresholds_and_monotone_scores():
    rng = np.random.default_rng(1)
    n = 2000
    F = pd.DataFrame(rng.normal(size=(n, len(ALL_FEATURE_NAMES))), columns=ALL_FEATURE_NAMES)
    F.iloc[::5, 2] = np.nan
    zt = 2 * F["email_exact"].fillna(0) + F["surname_sim"] - F["birthdate_conflict"] + rng.normal(scale=0.3, size=n)
    y = np.where(zt > 1.2, 2, np.where(zt > -0.6, 1, 0))
    m = fit_ordinal(F, y, epochs=200)
    assert np.all(np.diff(m.thresholds) > 0)
    z = m.z(F)
    assert (m.level(z) == y).mean() > 0.85
    s = m.score(z)
    assert np.all(np.diff(s[np.argsort(z)]) >= -1e-9)  # monotone in z
    assert s[m.level(z) == 2].min() >= 3.0 and s[m.level(z) == 0].max() < 2.0
    m2 = OrdinalModel.from_json(m.to_json())
    assert np.allclose(m2.z(F), z)


def test_extended_features_values():
    L = pd.DataFrame([{"given_name_canon": "michael", "surname_norm": "chen", "email_norm": "michael.chen@x.org", "phone_match": "2065550101",
                       "address_norm": "12 main street", "postal_norm": "98101", "birthdate_norm": "1980-05-01"}])
    R = pd.DataFrame([{"given_name_canon": "michael", "surname_norm": "chen", "email_norm": "mchen@y.org", "phone_match": "2065550102",
                       "address_norm": "12 main st", "postal_norm": "98101", "birthdate_norm": None}])
    ctx = {"n": 1000, "given_pop": {"michael": 0.05}, "postal_pop": {"98101": 0.001}}
    f = extended_features(L, R, ctx).iloc[0]
    assert f["name_email_closeness"] > 0.7 and f["email_domain_exact"] == 0.0
    assert abs(f["phone_hamming"] - 0.9) < 1e-9 and 0 < f["address_token_jaccard"] < 1
    assert f["postal_population"] > f["given_popularity"]  # rarer shared value = stronger evidence
    assert f["token_agreement"] == 3 / 6 and f["null_pattern_agreement"] == 6 / 7
    assert list(all_features(L, R, CFG.matcher, ctx).columns) == ALL_FEATURE_NAMES
    assert set(context_from_frame(L)["given_pop"]) == {"michael"}


def _records(persons: int, copies: int, seed: int) -> dict[str, dict]:
    rng = random.Random(seed)
    given = ["michael", "sarah", "robert", "linda", "david", "susan", "james", "karen"]
    sur = ["chen", "patel", "novak", "rossi", "garcia", "miller", "okafor", "lee"]
    recs = {}
    for p in range(persons):
        g, s = rng.choice(given), rng.choice(sur) + str(p % 97)
        email, phone, postal, dob = f"{g}.{s}@example.org", f"206555{p:04d}", f"9{p % 50:04d}", f"19{p % 60 + 20:02d}-01-01"
        for c in range(copies):
            r = {"datasource": "s", "pk": f"{p}-{c}", "given_name_canon": g, "given_name_norm": g, "surname_norm": s,
                 "email_norm": email if rng.random() > 0.3 else None, "phone_match": phone if rng.random() > 0.4 else None,
                 "postal_norm": postal if rng.random() > 0.2 else None, "birthdate_norm": dob if rng.random() > 0.5 else None,
                 "address_norm": f"{p} main street" if rng.random() > 0.3 else None}
            recs[f"s|{p}-{c}"] = r
    return recs


def test_label_free_training_and_scoring_on_fixture():
    recs = _records(persons=400, copies=4, seed=2)
    con = duckdb.connect(":memory:")
    load_records_table(con, recs)
    st = build_candidate_pairs(con, {**CFG.blocking, "collapse_trivial_dupes": False})
    assert st.pairs > 500
    ctx = corpus_context(con)
    ocfg = {**(CFG.matcher.get("ordinal") or {}), "min_positive_pairs": 50, "min_negative_pairs": 50, "epochs": 120, "max_train_pairs": 5000}
    cfg = type(CFG)({**CFG, "matcher": {**CFG.matcher, "ordinal": ocfg}})
    model, rep = train_from_candidates(con, cfg, ctx)
    assert model is not None, rep.fallback_reason
    assert rep.positives >= 50 and rep.negatives >= 50 and rep.rounds
    # score a few pairs through the ordinal path: deterministic rules still win, scored pairs get a 0-5 score
    L = pd.DataFrame([recs["s|0-0"], recs["s|1-0"]]); R = pd.DataFrame([recs["s|0-1"], recs["s|2-0"]])
    F = all_features(L, R, cfg.matcher, ctx)
    S = score_frame_ordinal(F, model, cfg.matcher)
    assert set(S.columns) >= {"score", "match_category", "match_type", "is_edge"}
    assert 0.0 <= S["score"].min() and S["score"].max() <= 5.0


def test_self_training_falls_back_gracefully():
    F = pd.DataFrame(np.zeros((20, len(ALL_FEATURE_NAMES))), columns=ALL_FEATURE_NAMES)
    model, rep = self_train(F, F, CFG.matcher, {"min_positive_pairs": 300})
    assert model is None and rep.fallback_reason.startswith("insufficient positives")
    assert rep.as_metrics()["ordinal_fallback_reason"]
