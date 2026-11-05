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


# ----------------------------------------------------------------------------------------- Rules Editor
# Amperity's Rules Editor is an ordered list of deterministic rules evaluated before the probabilistic model;
# the first rule whose conditions hold decides the pair (internals §2.5, dossier §3.8). Here a rule is
#   {name, when: {<feature or predicate>: <condition>, ...}, score, [match_type], [category]}
# where a condition is a scalar (equality), ``true``/``false`` for predicates, or {op: value} with
# op ∈ eq, ne, gt, gte, lt, lte, present (feature comparable / not missing). All conditions must hold.
# Predicates available next to the raw features: ``names_agree`` (both names present and ≥ name_agreement_min),
# ``names_missing`` (at least one side has no name). ``matcher.rules: null`` = the built-in list below, driven by
# ``matcher.deterministic.*``; an explicit list replaces it entirely.
RULE_OPS = ("eq", "ne", "gt", "gte", "lt", "lte", "present")
RULE_PREDICATES = ("names_agree", "names_missing")


def default_rules(det: dict) -> list[dict]:
    rules = [
        {"name": "ck_exact", "when": {"ck_exact": 1.0}, "score": float(det.get("ck_exact_score", 5.0))},
        {"name": "loy_exact", "when": {"loy_exact": 1.0}, "score": float(det.get("loy_exact_score", 5.0))},
        {"name": "email_with_name", "when": {"email_exact": 1.0, "names_agree": True}, "score": float(det.get("email_exact_with_name_score", 4.5))},
        {"name": "phone_with_name", "when": {"phone_exact": 1.0, "names_agree": True}, "score": float(det.get("phone_exact_with_name_score", 4.2))},
    ]
    if det.get("email_exact_no_name_score") is not None:
        rules.append({"name": "email_no_name", "when": {"email_exact": 1.0, "names_missing": True}, "score": float(det["email_exact_no_name_score"])})
    if det.get("phone_exact_no_name_score") is not None:
        rules.append({"name": "phone_no_name", "when": {"phone_exact": 1.0, "names_missing": True}, "score": float(det["phone_exact_no_name_score"])})
    return rules


def compile_rules(cfg) -> list[dict]:
    """Validated, ordered rule list for a ``matcher`` config section."""
    det = cfg.get("deterministic", {}) or {}
    raw = cfg.get("rules")
    rules = default_rules(det) if raw is None else list(raw)
    out = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict) or "when" not in r or "score" not in r:
            raise ValueError(f"matcher.rules[{i}] needs 'when' and 'score': {r!r}")
        when = dict(r["when"])
        if not when:
            raise ValueError(f"matcher.rules[{i}] ({r.get('name')}) has an empty 'when'")
        for feat, cond in when.items():
            if feat not in FEATURE_NAMES and feat not in RULE_PREDICATES:
                raise ValueError(f"matcher.rules[{i}] ({r.get('name')}): unknown feature/predicate {feat!r}")
            if isinstance(cond, dict):
                bad = [k for k in cond if k not in RULE_OPS]
                if bad:
                    raise ValueError(f"matcher.rules[{i}] ({r.get('name')}): unknown operator(s) {bad} (use {RULE_OPS})")
        score = float(r["score"])
        if not 0.0 <= score <= 5.0:
            raise ValueError(f"matcher.rules[{i}] ({r.get('name')}): score {score} outside 0..5")
        out.append({"name": str(r.get("name") or f"rule_{i}"), "when": when, "score": score,
                    "match_type": str(r.get("match_type", "deterministic")), "category": r.get("category")})
    return out


def _cond_scalar(value, cond) -> bool:
    if isinstance(cond, dict):
        for op, target in cond.items():
            if op == "present":
                if (value is not None) != bool(target):
                    return False
                continue
            if value is None:
                return False
            if op == "eq" and not value == target:
                return False
            if op == "ne" and not value != target:
                return False
            if op == "gt" and not value > target:
                return False
            if op == "gte" and not value >= target:
                return False
            if op == "lt" and not value < target:
                return False
            if op == "lte" and not value <= target:
                return False
        return True
    if isinstance(cond, bool):
        return bool(value) == cond
    return value is not None and value == cond


def _cond_vec(values: np.ndarray, cond) -> np.ndarray:
    """values: float array with NaN = missing (features) or bool array (predicates)."""
    if values.dtype == bool:
        if isinstance(cond, dict):
            raise ValueError("operators are not allowed on predicates")
        return values == bool(cond)
    present = ~np.isnan(values)
    if isinstance(cond, dict):
        ok = np.ones(len(values), dtype=bool)
        for op, target in cond.items():
            if op == "present":
                ok &= present == bool(target)
                continue
            v = np.nan_to_num(values, nan=0.0)
            cmp = {"eq": v == target, "ne": v != target, "gt": v > target, "gte": v >= target, "lt": v < target, "lte": v <= target}[op]
            ok &= present & cmp
        return ok
    if isinstance(cond, bool):
        return (np.nan_to_num(values, nan=0.0) != 0.0) == cond
    return present & (np.nan_to_num(values, nan=0.0) == cond)


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
    predicates = {"names_agree": names_agree, "names_missing": f.get("name_both_present") != 1.0}

    # Ordered deterministic rules (Rules Editor; first match wins).
    for rule in compile_rules(cfg):
        if all(_cond_scalar(predicates[k] if k in predicates else f.get(k), c) for k, c in rule["when"].items()):
            s = rule["score"]
            return PairScore(s, rule["category"] or category_for(s), rule["match_type"], False)

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
    name_floor = float(w.get("name_mismatch_floor", 0.6))
    if gs is not None and ss is not None and (gs < name_floor or ss < name_floor):
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
    name_floor = float(w.get("name_mismatch_floor", 0.6))
    z += np.where(both_names & ((gs < name_floor) | (ss < name_floor)), float(w.get("name_mismatch_penalty", -1.5)), 0.0)
    logistic = np.round(5.0 / (1.0 + np.exp(-z)), 3)

    name_min = float(det.get("name_agreement_min", 0.85))
    names_agree = both_names & (gs >= name_min) & (ss >= name_min)
    conflict = bool(hc.get("birthdate", True)) & (g["birthdate_conflict"] == 1.0)
    trivial = is_one("trivial_dupe")
    predicates = {"names_agree": names_agree, "names_missing": ~is_one("name_both_present")}
    rules = compile_rules(cfg)
    conds = [conflict, trivial]
    vals = [0.0, 5.0]
    types = ["scored", "trivial_duplicate"]
    cats: list[str | None] = [None, None]
    for rule in rules:
        mask = np.ones(n, dtype=bool)
        for k, c in rule["when"].items():
            mask &= _cond_vec(predicates[k] if k in predicates else g[k], c)
        conds.append(mask)
        vals.append(rule["score"])
        types.append(rule["match_type"])
        cats.append(rule["category"])
    score = np.select(conds, vals, default=logistic)
    category = categories_for(score)
    winner = np.select(conds, list(range(len(conds))), default=-1)  # index of the deciding rule per row
    for i, cat in enumerate(cats):  # explicit rule categories, only where that rule decided the pair
        if cat:
            category[winner == i] = cat
    category[conflict] = "hard_conflict"
    match_type = np.select(conds, types, default="scored")
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
