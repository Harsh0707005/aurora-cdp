"""Pairwise scoring: ordered deterministic rules, then a probabilistic (logistic) score on a 0-5 scale.

Amperity scores pairs with a learned ordinal-regression classifier whose bands are
1 weak / 2 moderate / 3 high / 4 excellent / 5 exact, with a default match threshold of 3.0 and explicit
hard-conflict labels (internals §2.5, §2.8). The scaffold reproduces the *interface* (score bands, hard
conflicts, deterministic rules first, threshold) with hand-set weights; see docs/feature-parity.md.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass

import pandas as pd

from .features import compute_features

log = logging.getLogger(__name__)

CATEGORY_BANDS = [
    (4.75, "exact"),
    (4.0, "excellent"),
    (3.0, "high"),
    (2.0, "moderate"),
    (1.0, "weak"),
    (0.0, "non_conflict"),
]


@dataclass
class PairScore:
    score: float
    category: str
    match_type: str
    hard_conflict: bool


def category_for(score: float) -> str:
    for floor, name in CATEGORY_BANDS:
        if score >= floor:
            return name
    return "non_conflict"


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def score_features(f: dict[str, float | None], cfg) -> PairScore:
    """cfg is the `matcher` config section."""
    det = cfg.get("deterministic", {})
    w = cfg.get("weights", {})
    hc = cfg.get("hard_conflicts", {})

    # Hard conflicts first: a strong match with a hard conflict must not merge.
    if hc.get("birthdate", True) and f.get("birthdate_conflict") == 1.0:
        return PairScore(0.0, "hard_conflict", "scored", True)

    if f.get("trivial_dupe") == 1.0:
        return PairScore(5.0, "exact", "trivial_duplicate", False)

    name_min = float(det.get("name_agreement_min", 0.85))
    gs, ss = f.get("given_sim"), f.get("surname_sim")
    names_agree = gs is not None and ss is not None and gs >= name_min and ss >= name_min

    # Ordered deterministic rules (first match wins).
    if f.get("ck_exact") == 1.0:
        return PairScore(float(det.get("ck_exact_score", 5.0)), "exact", "deterministic", False)
    if f.get("loy_exact") == 1.0:
        return PairScore(float(det.get("loy_exact_score", 5.0)), "exact", "deterministic", False)
    if f.get("email_exact") == 1.0 and names_agree:
        s = float(det.get("email_exact_with_name_score", 4.5))
        return PairScore(s, category_for(s), "deterministic", False)
    if f.get("phone_exact") == 1.0 and names_agree:
        s = float(det.get("phone_exact_with_name_score", 4.2))
        return PairScore(s, category_for(s), "deterministic", False)

    # Probabilistic score.
    z = float(w.get("bias", -2.5))
    for name in ("given_sim", "surname_sim", "email_exact", "phone_exact", "address_sim", "postal_exact", "birthdate_exact", "fk_shared"):
        v = f.get(name)
        if v is not None:
            z += float(w.get(name, 0.0)) * v
    es, ee = f.get("email_sim"), f.get("email_exact")
    if es is not None and ee == 0.0:
        z += float(w.get("email_sim", 0.0)) * es
    if gs is not None and ss is not None and (gs < 0.6 or ss < 0.6):
        z += float(w.get("name_mismatch_penalty", -1.5))
    score = round(5.0 * _sigmoid(z), 3)
    return PairScore(score, category_for(score), "scored", False)


def score_pairs(records: dict[str, dict], pairs, cfg, keep_features: bool = True) -> pd.DataFrame:
    """Score candidate pairs. Returns a DataFrame shaped like stitch_scores (without run_id)."""
    threshold = float(cfg.get("match_threshold", 3.0))
    rows = []
    for a_id, b_id in sorted(pairs):
        a, b = records[a_id], records[b_id]
        f = compute_features(a, b, cfg)
        ps = score_features(f, cfg)
        rows.append(
            {
                "left_datasource": a["datasource"],
                "left_pk": a["pk"],
                "right_datasource": b["datasource"],
                "right_pk": b["pk"],
                "left_rid": a_id,
                "right_rid": b_id,
                "score": ps.score,
                "match_category": ps.category,
                "match_type": ps.match_type,
                "is_edge": (not ps.hard_conflict) and ps.score >= threshold,
                "features_json": json.dumps(f) if keep_features else None,
            }
        )
    cols = [
        "left_datasource", "left_pk", "right_datasource", "right_pk", "left_rid", "right_rid",
        "score", "match_category", "match_type", "is_edge", "features_json",
    ]
    return pd.DataFrame(rows, columns=cols)
