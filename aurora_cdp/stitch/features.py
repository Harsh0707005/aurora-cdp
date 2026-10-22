"""Pairwise similarity features (Amperity: internals §2.5 — per-attribute measures: edit distance on names
and email, token/Jaccard-style similarity on address, exact agreement on keys)."""

from __future__ import annotations

import json

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler, Levenshtein

FEATURE_NAMES = [
    "given_sim",
    "surname_sim",
    "name_both_present",
    "email_exact",
    "email_sim",
    "phone_exact",
    "address_sim",
    "postal_exact",
    "birthdate_exact",
    "birthdate_conflict",
    "ck_exact",
    "loy_exact",
    "fk_shared",
    "trivial_dupe",
]


def _nn(value):
    """Normalise pandas NaN/NaT and blanks to None so missing values are 'not comparable'."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def sanitize(rec: dict) -> dict:
    return {k: _nn(v) for k, v in rec.items()}


def _fks(rec: dict) -> dict[str, str]:
    raw = rec.get("fk_json")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except json.JSONDecodeError:
        return {}


def _jw(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    return float(JaroWinkler.normalized_similarity(a, b))


def _exact(a, b) -> float | None:
    if not a or not b:
        return None
    return 1.0 if a == b else 0.0


def compute_features(a: dict, b: dict, cfg) -> dict[str, float | None]:
    """None means 'not comparable' (one side missing); the scorer treats None as neutral."""
    tol = int(cfg.get("hard_conflicts", {}).get("birthdate_typo_tolerance", 2))
    a, b = sanitize(a), sanitize(b)
    given_a = a.get("given_name_canon") or a.get("given_name_norm")
    given_b = b.get("given_name_canon") or b.get("given_name_norm")
    f: dict[str, float | None] = {}
    f["given_sim"] = _jw(given_a, given_b)
    f["surname_sim"] = _jw(a.get("surname_norm"), b.get("surname_norm"))
    f["name_both_present"] = 1.0 if (f["given_sim"] is not None and f["surname_sim"] is not None) else 0.0
    ea, eb = a.get("email_norm"), b.get("email_norm")
    f["email_exact"] = _exact(ea, eb)
    f["email_sim"] = (
        float(Levenshtein.normalized_similarity(ea, eb)) if ea and eb and ea != eb else (1.0 if ea and eb else None)
    )
    f["phone_exact"] = _exact(a.get("phone_match"), b.get("phone_match"))
    aa, ab = a.get("address_norm"), b.get("address_norm")
    f["address_sim"] = float(fuzz.token_set_ratio(aa, ab)) / 100.0 if aa and ab else None
    f["postal_exact"] = _exact(a.get("postal_norm"), b.get("postal_norm"))
    ba, bb = a.get("birthdate_norm"), b.get("birthdate_norm")
    if ba and bb:
        if ba == bb:
            f["birthdate_exact"], f["birthdate_conflict"] = 1.0, 0.0
        elif Levenshtein.distance(ba, bb) <= tol:
            f["birthdate_exact"], f["birthdate_conflict"] = 0.5, 0.0  # likely typo / transposition
        else:
            f["birthdate_exact"], f["birthdate_conflict"] = 0.0, 1.0
    else:
        f["birthdate_exact"], f["birthdate_conflict"] = None, 0.0
    f["ck_exact"] = _exact(a.get("ck"), b.get("ck"))
    f["loy_exact"] = _exact(a.get("loy_id_norm"), b.get("loy_id_norm"))
    fa, fb = _fks(a), _fks(b)
    shared = [ns for ns in fa if ns in fb and fa[ns] == fb[ns]]
    f["fk_shared"] = 1.0 if shared else (0.0 if fa and fb else None)
    key_fields = ("given_name_norm", "surname_norm", "email_norm", "phone_match", "address_norm", "postal_norm")
    f["trivial_dupe"] = (
        1.0
        if all(a.get(k) == b.get(k) for k in key_fields) and any(a.get(k) for k in key_fields)
        else 0.0
    )
    return f
