"""The hand-set (``matcher.scorer: rules``) scorer must stay byte-identical to the frozen snapshot.

``tests/fixtures/handset_scores_frozen.json`` was generated from ``score_features`` on a fixed pseudo-random grid of
feature rows (seed 1234, 120 rows covering every rule path) *before* the learned scorer was introduced. The default
configuration must reproduce every score, category, match type and hard-conflict flag exactly, through both the
per-pair reference and the vectorised scorer."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.stitch.features import FEATURE_NAMES
from aurora_cdp.stitch.matcher import score_features, score_frame
from aurora_cdp.stitch.ordinal import RulesScorer, prepare_scorer

FROZEN = Path(__file__).with_name("fixtures") / "handset_scores_frozen.json"
GRID: dict[str, list[float | None]] = {
    "given_sim": [None, 0.5, 0.9, 1.0],
    "surname_sim": [None, 0.5, 1.0],
    "email_exact": [None, 0.0, 1.0],
    "email_sim": [None, 0.95, 1.0],
    "phone_exact": [None, 1.0],
    "address_sim": [None, 0.2, 0.9],
    "postal_exact": [None, 1.0],
    "birthdate_exact": [None, 0.5, 1.0],
    "birthdate_conflict": [0.0, 1.0],
    "ck_exact": [None, 1.0],
    "loy_exact": [None, 1.0],
    "fk_shared": [None, 0.0, 1.0],
    "trivial_dupe": [0.0, 1.0],
}


def _grid_rows() -> list[dict]:
    rng = random.Random(1234)
    rows = []
    for _ in range(120):
        f: dict[str, float | None] = {k: rng.choice(v) for k, v in GRID.items()}
        if f["email_exact"] == 1.0:
            f["email_sim"] = 1.0
        rows.append(f)
    return rows


def test_grid_generator_matches_fixture_inputs():
    frozen = json.loads(FROZEN.read_text())
    assert [r["f"] for r in frozen] == _grid_rows()


def test_handset_scores_are_byte_identical_to_snapshot():
    cfg = load_config(use_last_best=False).matcher
    assert (
        cfg.get("scorer", "rules") == "rules"
    ), "the default scorer must stay the hand-set rules scorer"
    frozen = json.loads(FROZEN.read_text())
    for row in frozen:
        got = score_features(row["f"], cfg)
        assert (got.score, got.category, got.match_type, got.hard_conflict) == (
            row["score"],
            row["category"],
            row["match_type"],
            row["hard_conflict"],
        ), row
    F = pd.DataFrame(
        [
            {k: (np.nan if r["f"].get(k) is None else r["f"][k]) for k in FEATURE_NAMES}
            for r in frozen
        ]
    )
    F["name_both_present"] = (~F["given_sim"].isna() & ~F["surname_sim"].isna()).astype(float)
    S = score_frame(F, cfg)
    assert S["score"].tolist() == [r["score"] for r in frozen]
    assert S["match_category"].tolist() == [r["category"] for r in frozen]
    assert S["match_type"].tolist() == [r["match_type"] for r in frozen]
    assert S["hard_conflict"].tolist() == [r["hard_conflict"] for r in frozen]
    # the run-time scorer object for the default config is the rules scorer and delegates to score_frame
    scorer, info = prepare_scorer(None, load_config(use_last_best=False), "run-x")
    assert (
        isinstance(scorer, RulesScorer)
        and info["scorer_used"] == "rules"
        and info["scorer_fallback_reason"] is None
    )
