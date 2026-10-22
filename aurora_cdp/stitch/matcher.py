"""Pairwise scoring: ordered deterministic rules, then a probabilistic (logistic) score on a 0-5 scale.

Amperity scores pairs with a learned ordinal-regression classifier whose bands are
1 weak / 2 moderate / 3 high / 4 excellent / 5 exact, with a default match threshold of 3.0 and explicit
hard-conflict labels (internals §2.5, §2.8). The scaffold reproduces the *interface* (score bands, hard
conflicts, deterministic rules first, threshold) with hand-set weights; see docs/feature-parity.md.

:func:`score_features` is the per-pair reference; :func:`score_frame` is the vectorised equivalent used by the
chunked scorer (``tests/test_scoring_vectorised.py`` checks they agree)."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, SIDE_COLUMNS, compute_features, features_frame

log = logging.getLogger(__name__)

CATEGORY_BANDS = [
    (4.75, "exact"),
    (4.0, "excellent"),
    (3.0, "high"),
    (2.0, "moderate"),
    (1.0, "weak"),
    (0.0, "non_conflict"),
]
LOGISTIC_FEATURES = ("given_sim", "surname_sim", "email_exact", "phone_exact", "postal_exact", "birthdate_exact", "fk_shared")
SCORE_COLUMNS = ["score", "match_category", "match_type", "hard_conflict", "is_edge"]


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
    for name in LOGISTIC_FEATURES:
        v = f.get(name)
        if v is not None:
            z += float(w.get(name, 0.0)) * v
    addr = f.get("address_sim")
    if addr is not None:
        z += float(w.get("address_sim", 0.0)) * (2.0 * addr - 1.0)  # centred: dissimilar addresses count against
    es, ee = f.get("email_sim"), f.get("email_exact")
    if es is not None and ee == 0.0:
        typo_floor = float(w.get("email_sim_min", 0.92))
        if es >= typo_floor:
            z += float(w.get("email_sim", 0.0)) * (es - typo_floor) / max(1e-9, 1.0 - typo_floor)
    if gs is not None and ss is not None and (gs < 0.6 or ss < 0.6):
        z += float(w.get("name_mismatch_penalty", -1.5))
    score = round(5.0 * _sigmoid(z), 3)
    return PairScore(score, category_for(score), "scored", False)


# ----------------------------------------------------------------------------------------- vectorised
def categories_for(scores: np.ndarray) -> np.ndarray:
    out = np.full(len(scores), "non_conflict", dtype=object)
    for floor, name in reversed(CATEGORY_BANDS):  # ascending floors: later (higher) bands overwrite
        out[scores >= floor] = name
    return out


def score_frame(F: pd.DataFrame, cfg) -> pd.DataFrame:
    """Vectorised :func:`score_features` over a feature frame (NaN = None). Returns SCORE_COLUMNS."""
    det = cfg.get("deterministic", {})
    w = cfg.get("weights", {})
    hc = cfg.get("hard_conflicts", {})
    threshold = float(cfg.get("match_threshold", 3.0))
    n = len(F)
    g = {k: F[k].to_numpy(dtype=np.float64) for k in FEATURE_NAMES}

    def is_one(k):
        return np.nan_to_num(g[k], nan=0.0) == 1.0

    z = np.full(n, float(w.get("bias", -2.5)))
    for name in LOGISTIC_FEATURES:
        v = g[name]
        z += np.where(np.isnan(v), 0.0, float(w.get(name, 0.0)) * np.nan_to_num(v))
    addr = g["address_sim"]
    z += np.where(np.isnan(addr), 0.0, float(w.get("address_sim", 0.0)) * (2.0 * np.nan_to_num(addr) - 1.0))
    es, ee = g["email_sim"], g["email_exact"]
    floor_ = float(w.get("email_sim_min", 0.92))
    typo = ~np.isnan(es) & (ee == 0.0) & (es >= floor_)
    z += np.where(typo, float(w.get("email_sim", 0.0)) * (np.nan_to_num(es) - floor_) / max(1e-9, 1.0 - floor_), 0.0)
    gs, ss = g["given_sim"], g["surname_sim"]
    both_names = ~np.isnan(gs) & ~np.isnan(ss)
    z += np.where(both_names & ((gs < 0.6) | (ss < 0.6)), float(w.get("name_mismatch_penalty", -1.5)), 0.0)
    logistic = np.round(5.0 / (1.0 + np.exp(-z)), 3)

    name_min = float(det.get("name_agreement_min", 0.85))
    names_agree = both_names & (gs >= name_min) & (ss >= name_min)
    conflict = bool(hc.get("birthdate", True)) & (g["birthdate_conflict"] == 1.0)
    trivial = is_one("trivial_dupe")
    ck = is_one("ck_exact")
    loy = is_one("loy_exact")
    email_name = is_one("email_exact") & names_agree
    phone_name = is_one("phone_exact") & names_agree
    s_email = float(det.get("email_exact_with_name_score", 4.5))
    s_phone = float(det.get("phone_exact_with_name_score", 4.2))
    conds = [conflict, trivial, ck, loy, email_name, phone_name]
    score = np.select(conds, [0.0, 5.0, float(det.get("ck_exact_score", 5.0)), float(det.get("loy_exact_score", 5.0)), s_email, s_phone], default=logistic)
    category = categories_for(score)
    category[conflict] = "hard_conflict"
    match_type = np.select(conds, ["scored", "trivial_duplicate", "deterministic", "deterministic", "deterministic", "deterministic"], default="scored")
    return pd.DataFrame({
        "score": score, "match_category": category, "match_type": match_type, "hard_conflict": conflict,
        "is_edge": (~conflict) & (score >= threshold),
    })


def score_pairs(records: dict[str, dict], pairs, cfg, keep_features: bool = True) -> pd.DataFrame:
    """Score candidate pairs. Returns a DataFrame shaped like stitch_scores (without run_id)."""
    ordered = sorted(pairs)
    cols = [
        "left_datasource", "left_pk", "right_datasource", "right_pk", "left_rid", "right_rid",
        "score", "match_category", "match_type", "is_edge", "features_json",
    ]
    if not ordered:
        return pd.DataFrame(columns=cols)
    left = pd.DataFrame([{c: records[a].get(c) for c in SIDE_COLUMNS} for a, _ in ordered])
    right = pd.DataFrame([{c: records[b].get(c) for c in SIDE_COLUMNS} for _, b in ordered])
    F = features_frame(left, right, cfg)
    S = score_frame(F, cfg)
    out = pd.DataFrame({
        "left_datasource": [records[a]["datasource"] for a, _ in ordered],
        "left_pk": [records[a]["pk"] for a, _ in ordered],
        "right_datasource": [records[b]["datasource"] for _, b in ordered],
        "right_pk": [records[b]["pk"] for _, b in ordered],
        "left_rid": [a for a, _ in ordered],
        "right_rid": [b for _, b in ordered],
        "score": S["score"].to_numpy(), "match_category": S["match_category"].to_numpy(),
        "match_type": S["match_type"].to_numpy(), "is_edge": S["is_edge"].to_numpy(),
    })
    out["features_json"] = [json.dumps({k: (None if pd.isna(v) else float(v)) for k, v in row.items()}) for row in F.to_dict("records")] if keep_features else None
    return out[cols]
