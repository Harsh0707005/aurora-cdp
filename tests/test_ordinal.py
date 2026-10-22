"""Ordinal-regression scorer: fitting, score mapping, extended features, label-free self-training and fallback."""

from __future__ import annotations

import random

import duckdb
import numpy as np
import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.stitch.blocking import build_candidate_pairs, load_records_table
from aurora_cdp.stitch.ordinal import (
    ALL_FEATURE_NAMES,
    OrdinalModel,
    all_features,
    context_from_frame,
    corpus_context,
    extended_features,
    fit_ordinal,
    prepare_scorer,
    score_frame_ordinal,
    self_train,
    train_from_candidates,
)

CFG = load_config(use_last_best=False)


def test_fit_recovers_ordered_thresholds_and_monotone_scores():
    rng = np.random.default_rng(1)
    n = 2000
    F = pd.DataFrame(rng.normal(size=(n, len(ALL_FEATURE_NAMES))), columns=ALL_FEATURE_NAMES)
    F.iloc[::5, 2] = np.nan
    zt = (
        2 * F["email_exact"].fillna(0)
        + F["surname_sim"]
        - F["birthdate_conflict"]
        + rng.normal(scale=0.3, size=n)
    )
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
    L = pd.DataFrame(
        [
            {
                "given_name_canon": "michael",
                "surname_norm": "chen",
                "email_norm": "michael.chen@x.org",
                "phone_match": "2065550101",
                "address_norm": "12 main street",
                "postal_norm": "98101",
                "birthdate_norm": "1980-05-01",
            }
        ]
    )
    R = pd.DataFrame(
        [
            {
                "given_name_canon": "michael",
                "surname_norm": "chen",
                "email_norm": "mchen@y.org",
                "phone_match": "2065550102",
                "address_norm": "12 main st",
                "postal_norm": "98101",
                "birthdate_norm": None,
            }
        ]
    )
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
        email, phone, postal, dob = (
            f"{g}.{s}@example.org",
            f"206555{p:04d}",
            f"9{p % 50:04d}",
            f"19{p % 60 + 20:02d}-01-01",
        )
        for c in range(copies):
            r = {
                "datasource": "s",
                "pk": f"{p}-{c}",
                "given_name_canon": g,
                "given_name_norm": g,
                "surname_norm": s,
                "email_norm": email if rng.random() > 0.3 else None,
                "phone_match": phone if rng.random() > 0.4 else None,
                "postal_norm": postal if rng.random() > 0.2 else None,
                "birthdate_norm": dob if rng.random() > 0.5 else None,
                "address_norm": f"{p} main street" if rng.random() > 0.3 else None,
            }
            recs[f"s|{p}-{c}"] = r
    return recs


def test_label_free_training_and_scoring_on_fixture():
    recs = _records(persons=400, copies=4, seed=2)
    con = duckdb.connect(":memory:")
    load_records_table(con, recs)
    st = build_candidate_pairs(con, {**CFG.blocking, "collapse_trivial_dupes": False})
    assert st.pairs > 500
    ctx = corpus_context(con)
    ocfg = {
        **(CFG.matcher.get("ordinal") or {}),
        "min_positive_pairs": 50,
        "min_negative_pairs": 50,
        "epochs": 120,
        "max_train_pairs": 5000,
    }
    cfg = type(CFG)({**CFG, "matcher": {**CFG.matcher, "ordinal": ocfg}})
    model, rep = train_from_candidates(con, cfg, ctx)
    assert model is not None, rep.fallback_reason
    assert rep.positives >= 50 and rep.negatives >= 50 and rep.rounds
    # score a few pairs through the ordinal path: deterministic rules still win, scored pairs get a 0-5 score
    L = pd.DataFrame([recs["s|0-0"], recs["s|1-0"]])
    R = pd.DataFrame([recs["s|0-1"], recs["s|2-0"]])
    F = all_features(L, R, cfg.matcher, ctx)
    S = score_frame_ordinal(F, model, cfg.matcher)
    assert set(S.columns) >= {"score", "match_category", "match_type", "is_edge"}
    assert 0.0 <= S["score"].min() and S["score"].max() <= 5.0


def test_self_training_falls_back_gracefully():
    F = pd.DataFrame(np.zeros((20, len(ALL_FEATURE_NAMES))), columns=ALL_FEATURE_NAMES)
    model, rep = self_train(F, F, CFG.matcher, {"min_positive_pairs": 300})
    assert model is None and rep.fallback_reason.startswith("insufficient positives")
    assert rep.as_metrics()["ordinal_fallback_reason"]


def test_scorer_ordinal_end_to_end_and_fallback(tmp_path):
    from aurora_cdp.adapters import resolve_records

    recs = _records(persons=500, copies=4, seed=7)
    df = pd.DataFrame(
        [
            {
                "source_record_id": r["pk"],
                "given_name": r["given_name_canon"],
                "surname": r["surname_norm"],
                "email": r["email_norm"],
                "phone": r["phone_match"],
                "postal": r["postal_norm"],
                "birthdate": r["birthdate_norm"],
                "address": r["address_norm"],
            }
            for r in recs.values()
        ]
    )
    ocfg = {
        "min_positive_pairs": 50,
        "min_negative_pairs": 50,
        "epochs": 120,
        "max_train_pairs": 5000,
        "model_file": str(tmp_path / "m.json"),
    }
    res = resolve_records(
        df, config={"matcher": {"scorer": "ordinal", "ordinal": ocfg}}, datasource="s"
    )
    m = res.metrics
    assert (
        m["scorer_requested"] == "ordinal"
        and m["scorer_used"] == "ordinal"
        and m["scorer_fallback_reason"] is None
    )
    assert m["ordinal_model_source"] == "trained" and (tmp_path / "m.json").exists()
    assert set(res.scores["match_type"]) <= {
        "scored",
        "deterministic",
        "trivial_duplicate",
        "carried",
    }
    assert m["clusters"] > 0 and m["records_dropped_by_blocking"] == 0
    # reuse the saved model without retraining
    res2 = resolve_records(
        df,
        config={"matcher": {"scorer": "ordinal", "ordinal": {**ocfg, "retrain": "never"}}},
        datasource="s",
    )
    assert (
        res2.metrics["ordinal_model_source"] == "file" and res2.metrics["scorer_used"] == "ordinal"
    )
    # insufficient positives -> rules fallback with a reason, never a crash
    res3 = resolve_records(
        df.head(40),
        config={"matcher": {"scorer": "ordinal", "ordinal": {**ocfg, "model_file": None}}},
        datasource="s",
    )
    assert res3.metrics["scorer_used"] == "rules" and res3.metrics[
        "scorer_fallback_reason"
    ].startswith("insufficient")
    # retrain=never without a model -> fallback
    res4 = resolve_records(
        df,
        config={
            "matcher": {"scorer": "ordinal", "ordinal": {"retrain": "never", "model_file": None}}
        },
        datasource="s",
    )
    assert (
        res4.metrics["scorer_used"] == "rules"
        and "retrain=never" in res4.metrics["scorer_fallback_reason"]
    )


# ----------------------------------------------------------------------------------------- monotone fit, bands, persistence
def _trained_monotone(tmp_path):
    recs = _records(persons=400, copies=4, seed=2)
    con = duckdb.connect(":memory:")
    load_records_table(con, recs)
    build_candidate_pairs(con, {**CFG.blocking, "collapse_trivial_dupes": False})
    ctx = corpus_context(con)
    ocfg = {
        **(CFG.matcher.get("ordinal") or {}),
        "min_positive_pairs": 50,
        "min_negative_pairs": 50,
        "epochs": 150,
        "max_train_pairs": 5000,
        "monotone": True,
    }
    cfg = type(CFG)({**CFG, "matcher": {**CFG.matcher, "ordinal": ocfg}})
    model, rep = train_from_candidates(con, cfg, ctx)
    assert model is not None, rep.fallback_reason
    return model, cfg, ctx, recs


def test_monotone_fit_more_agreement_never_lowers_the_score(tmp_path):
    from aurora_cdp.stitch.ordinal import FEATURE_ORIENTATION

    model, cfg, ctx, recs = _trained_monotone(tmp_path)
    assert model.meta["monotone"] is True
    nf = len(model.feature_names)
    for name, w in zip(model.feature_names, model.w[:nf], strict=True):
        o = FEATURE_ORIENTATION[name]
        assert (o > 0 and w >= 0) or (o < 0 and w <= 0), (name, w)
    # a weakly agreeing pair, then the same pair with progressively more agreement
    base = {f: np.nan for f in ALL_FEATURE_NAMES}
    base.update(
        {
            "given_sim": 0.6,
            "surname_sim": 0.7,
            "name_both_present": 1.0,
            "birthdate_conflict": 0.0,
            "trivial_dupe": 0.0,
            "null_pattern_agreement": 0.5,
            "token_agreement": 0.0,
        }
    )
    steps = [dict(base)]
    for upgrade in (
        {"given_sim": 0.9},
        {"surname_sim": 1.0},
        {"postal_exact": 1.0},
        {"email_exact": 1.0, "email_sim": 1.0},
        {"phone_exact": 1.0, "phone_hamming": 1.0},
        {"birthdate_exact": 1.0},
        {"token_agreement": 1.0},
        {"address_sim": 1.0},
    ):
        steps.append({**steps[-1], **upgrade})
    F = pd.DataFrame(steps, columns=ALL_FEATURE_NAMES)
    z = model.z(F)
    assert np.all(np.diff(z) >= -1e-12), z
    S = score_frame_ordinal(F, model, cfg.matcher)
    s = S["score"].to_numpy()
    assert np.all(np.diff(s) >= -1e-9) and s.min() >= 0.0 and s.max() <= 5.0
    assert s[-1] > s[0]
    # and a conflict can only lower it
    conflict = pd.DataFrame(
        [{**steps[-1], "birthdate_conflict": 1.0, "birthdate_exact": 0.0}],
        columns=ALL_FEATURE_NAMES,
    )
    assert model.z(conflict)[0] <= z[-1]
    # the whole candidate set scores inside the 0-5 interval
    L = pd.DataFrame(list(recs.values())[:300])
    R = pd.DataFrame(list(recs.values())[1:301])
    all_s = score_frame_ordinal(all_features(L, R, cfg.matcher, ctx), model, cfg.matcher)["score"]
    assert all_s.between(0.0, 5.0).all()


def test_ordinal_scores_map_to_the_same_bands_and_threshold(tmp_path):
    from aurora_cdp.stitch.matcher import category_for

    model, cfg, _ctx, _recs = _trained_monotone(tmp_path)
    # sweep z across the learned thresholds and check the band mapping of the continuous score
    zs = np.linspace(model.thresholds[0] - 6, model.thresholds[-1] + 6, 400)
    s = model.score(zs)
    assert np.all(np.diff(s) >= -1e-9) and s.min() >= 0.0 and s.max() <= 5.0
    assert s[zs < model.thresholds[0]].max() < 2.0 and s[zs >= model.thresholds[-1]].min() >= 3.0
    F = pd.DataFrame(np.nan, index=range(len(zs)), columns=ALL_FEATURE_NAMES)
    F["birthdate_conflict"], F["trivial_dupe"] = 0.0, 0.0
    fake = OrdinalModel(
        model.feature_names,
        model.w,
        model.thresholds,
        model.mean,
        model.std,
        model.levels,
        model.meta,
    )
    out = score_frame_ordinal(F, fake, cfg.matcher)
    # the category of every scored row is the weak/moderate/high/excellent/exact band of its score
    scored = out[out["match_type"] == "scored"]
    assert len(scored) == len(out)
    assert all(
        cat == category_for(sc)
        for cat, sc in zip(scored["match_category"], scored["score"], strict=True)
    )
    assert set(out["match_category"]) <= {
        "non_conflict",
        "weak",
        "moderate",
        "high",
        "excellent",
        "exact",
    }
    assert (out["is_edge"] == (out["score"] >= float(cfg.matcher["match_threshold"]))).all()
    # deterministic rules and hard conflicts keep precedence over the model
    rules = pd.DataFrame(np.nan, index=range(3), columns=ALL_FEATURE_NAMES)
    rules["birthdate_conflict"], rules["trivial_dupe"] = [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]
    rules.loc[0, "ck_exact"] = 1.0
    r = score_frame_ordinal(rules, model, cfg.matcher)
    assert list(r["match_type"]) == ["deterministic", "trivial_duplicate", "scored"]
    assert (
        list(r["match_category"]) == ["exact", "exact", "hard_conflict"] and not r.loc[2, "is_edge"]
    )


def test_ordinal_params_round_trip_through_file(tmp_path):
    model, cfg, ctx, recs = _trained_monotone(tmp_path)
    path = tmp_path / "models" / "ordinal.json"
    model.save(path)
    loaded = OrdinalModel.load(path)
    assert loaded.feature_names == model.feature_names and loaded.levels == model.levels
    assert np.array_equal(loaded.w, model.w) and np.array_equal(loaded.thresholds, model.thresholds)
    assert np.array_equal(loaded.mean, model.mean) and np.array_equal(loaded.std, model.std)
    assert loaded.meta == model.meta
    L = pd.DataFrame(list(recs.values())[:50])
    R = pd.DataFrame(list(recs.values())[50:100])
    F = all_features(L, R, cfg.matcher, ctx)
    pd.testing.assert_frame_equal(
        score_frame_ordinal(F, loaded, cfg.matcher), score_frame_ordinal(F, model, cfg.matcher)
    )
    # a run that points at the file reuses it (retrain: never) and reports the source
    from aurora_cdp.stitch.ordinal import OrdinalScorer

    con = duckdb.connect(":memory:")
    load_records_table(con, recs)
    build_candidate_pairs(con, CFG.blocking)
    cfg2 = type(CFG)(
        {
            **CFG,
            "matcher": {
                **CFG.matcher,
                "scorer": "ordinal",
                "ordinal": {**cfg.matcher["ordinal"], "model_file": str(path), "retrain": "never"},
            },
        }
    )
    scorer, info = prepare_scorer(con, cfg2, "run-y")
    assert (
        isinstance(scorer, OrdinalScorer)
        and info["ordinal_model_source"] == "file"
        and info["scorer_used"] == "ordinal"
    )
    assert info["ordinal_thresholds"] == [round(float(t), 4) for t in model.thresholds]
