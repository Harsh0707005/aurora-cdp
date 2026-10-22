"""Ordinal scoring: thresholds, deterministic short-circuit, hard conflicts, tuner."""

import numpy as np
import pandas as pd

from aurora.config.schema import load_config
from aurora.data.schemas import PAIR_FEATURE_COLUMNS
from aurora.features.pairwise import pair_features
from aurora.graph.edges import keep_edges
from aurora.scoring.ordinal import ConfigScorer, fit_learned, tune_thresholds


def _X(rows):
    return pd.DataFrame(rows).reindex(columns=PAIR_FEATURE_COLUMNS).fillna(0.0)


def test_categories_follow_thresholds():
    cfg = load_config("configs/tenants/demo.yaml").scoring
    X = _X([
        {"given_jw": 0.3},                                        # ~0.4 -> non_match
        {"surname_jw": 1.0, "given_jw": 0.5},                     # 1.6+0.65=2.25 -> moderate
        {"surname_jw": 1.0, "given_jw": 1.0, "dob_eq": 1.0},      # 4.7 -> excellent
        {"email_exact": 1.0, "email_sim": 1.0},                   # deterministic -> exact
    ])
    out = ConfigScorer(cfg).score(X)
    assert list(out["match_category"]) == ["non_match", "moderate", "excellent", "exact"]
    assert out["score"].is_monotonic_increasing
    assert out.loc[3, "match_type"] == "deterministic" and out.loc[3, "score"] == 5.0


def test_hard_conflict_caps_and_blocks_edge():
    cfg = load_config("configs/tenants/demo.yaml").scoring
    X = _X([{"email_exact": 1.0, "email_sim": 1.0, "surname_jw": 1.0, "given_jw": 1.0, "dob_conflict": 1.0}])
    out = ConfigScorer(cfg).score(X)
    assert out.loc[0, "match_type"] == "hard_conflict"
    assert out.loc[0, "category"] <= 2
    scored = pd.concat([pd.DataFrame({"rid_l": [1], "rid_r": [2]}), out], axis=1)
    assert keep_edges(scored, cfg).empty


def test_pair_features_nickname_and_canonical_email():
    f = pair_features(
        {"email_std": "bill.smith+promo@gmail.com", "email_canon": "billsmith@gmail.com", "given_std": "bill",
         "given_nick": "william", "surname_std": "smith"},
        {"email_std": "billsmith@gmail.com", "email_canon": "billsmith@gmail.com", "given_std": "william",
         "given_nick": "william", "surname_std": "smith"},
    )
    assert f["email_exact"] == 1.0 and f["nickname_match"] == 1.0 and f["surname_jw"] == 1.0


def test_tuner_and_learned_mode_pick_separating_threshold():
    rng = np.random.default_rng(0)
    pos = [{"surname_jw": 1.0, "given_jw": rng.uniform(0.8, 1.0), "dob_eq": 1.0} for _ in range(60)]
    neg = [{"surname_jw": rng.uniform(0.0, 0.7), "given_jw": rng.uniform(0.0, 0.7)} for _ in range(60)]
    X = _X(pos + neg)
    y = np.array([1] * 60 + [0] * 60, dtype=bool)
    cfg = load_config("configs/tenants/demo.yaml").scoring
    best = tune_thresholds(X, y, cfg, weight_scales=(1.0,))
    assert best["f1"] >= 0.99
    learned = fit_learned(X, y, cfg)
    out = learned.score(X)
    assert (out["category"][:60] >= 3).mean() > 0.95
    assert (out["category"][60:] < 3).mean() > 0.95
