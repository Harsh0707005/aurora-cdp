"""Pairwise similarity features (Amperity: internals §2.5 — per-attribute measures: edit distance on names
and email, token/Jaccard-style similarity on address, exact agreement on keys).

Two implementations share one definition: :func:`compute_features` (one pair, dicts; the readable reference)
and :func:`features_frame` (aligned left/right frames, vectorised with ``rapidfuzz.process.cpdist``; used by
the chunked scorer). ``tests/test_scoring_vectorised.py`` checks they agree."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
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
TRIVIAL_DUPE_FIELDS = ("given_name_norm", "surname_norm", "email_norm", "phone_match", "address_norm", "postal_norm")
# columns a side needs for feature computation
SIDE_COLUMNS = [
    "given_name_norm", "given_name_canon", "surname_norm", "email_norm", "phone_match", "address_norm", "postal_norm",
    "birthdate_norm", "ck", "loy_id_norm", "fk_json",
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
    except (json.JSONDecodeError, TypeError):
        return {}


def _house_number(addr: str) -> str | None:
    tok = addr.split(" ", 1)[0]
    return tok if tok.isdigit() else None


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
    # Only near-identical emails (typo level) count as similar: name-derived emails of two different people with
    # the same name look alike (ann.lee12@ vs ann.lee98@) and must not add evidence.
    if ea and eb:
        f["email_sim"] = 1.0 if ea == eb else float(Levenshtein.normalized_similarity(ea, eb))
    else:
        f["email_sim"] = None
    f["phone_exact"] = _exact(a.get("phone_match"), b.get("phone_match"))
    aa, ab = a.get("address_norm"), b.get("address_norm")
    if aa and ab:
        sim = float(fuzz.token_set_ratio(aa, ab)) / 100.0
        na, nb = _house_number(aa), _house_number(ab)
        if na and nb and na != nb:
            sim = min(sim, 0.3)  # same street name but different house number is a different address
        f["address_sim"] = sim
    else:
        f["address_sim"] = None
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
    f["trivial_dupe"] = (
        1.0
        if all(a.get(k) == b.get(k) for k in TRIVIAL_DUPE_FIELDS) and any(a.get(k) for k in TRIVIAL_DUPE_FIELDS)
        else 0.0
    )
    return f


# ----------------------------------------------------------------------------------------- vectorised
def _col(df: pd.DataFrame, name: str) -> np.ndarray:
    """Object array with None for missing/blank values."""
    if name not in df.columns:
        return np.full(len(df), None, dtype=object)
    s = df[name]
    if pd.api.types.is_datetime64_any_dtype(s.dtype):
        s = s.astype(object)
    v = s.to_numpy(dtype=object, copy=True)
    out = np.empty(len(v), dtype=object)
    for i, x in enumerate(v):
        out[i] = _nn(x)
    return out


def _present(a: np.ndarray) -> np.ndarray:
    return np.array([x is not None for x in a], dtype=bool)


def _strs(a: np.ndarray) -> list[str]:
    return [x if x is not None else "" for x in a]


def _cpdist(a: np.ndarray, b: np.ndarray, scorer, both: np.ndarray) -> np.ndarray:
    """Element-wise rapidfuzz scorer on the rows where both sides are present (NaN elsewhere)."""
    out = np.full(len(a), np.nan, dtype=np.float64)
    if both.any():
        la, lb = _strs(a[both]), _strs(b[both])
        out[both] = process.cpdist(la, lb, scorer=scorer, dtype=np.float64, workers=1)
    return out


def _exact_vec(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    both = _present(a) & _present(b)
    out = np.full(len(a), np.nan, dtype=np.float64)
    if both.any():
        out[both] = np.array([1.0 if x == y else 0.0 for x, y in zip(a[both], b[both], strict=True)])
    return out


def features_frame(left: pd.DataFrame, right: pd.DataFrame, cfg) -> pd.DataFrame:
    """Feature frame (FEATURE_NAMES columns, NaN = not comparable) for aligned left/right record frames."""
    tol = int(cfg.get("hard_conflicts", {}).get("birthdate_typo_tolerance", 2))
    n = len(left)
    f: dict[str, np.ndarray] = {}
    ga = np.where(_present(_col(left, "given_name_canon")), _col(left, "given_name_canon"), _col(left, "given_name_norm"))
    gb = np.where(_present(_col(right, "given_name_canon")), _col(right, "given_name_canon"), _col(right, "given_name_norm"))
    sa, sb = _col(left, "surname_norm"), _col(right, "surname_norm")
    f["given_sim"] = _cpdist(ga, gb, JaroWinkler.normalized_similarity, _present(ga) & _present(gb))
    f["surname_sim"] = _cpdist(sa, sb, JaroWinkler.normalized_similarity, _present(sa) & _present(sb))
    f["name_both_present"] = (~np.isnan(f["given_sim"]) & ~np.isnan(f["surname_sim"])).astype(np.float64)
    ea, eb = _col(left, "email_norm"), _col(right, "email_norm")
    f["email_exact"] = _exact_vec(ea, eb)
    both_e = _present(ea) & _present(eb)
    es = _cpdist(ea, eb, Levenshtein.normalized_similarity, both_e)
    es[both_e & (f["email_exact"] == 1.0)] = 1.0
    f["email_sim"] = es
    f["phone_exact"] = _exact_vec(_col(left, "phone_match"), _col(right, "phone_match"))
    aa, ab = _col(left, "address_norm"), _col(right, "address_norm")
    both_a = _present(aa) & _present(ab)
    sim = _cpdist(aa, ab, fuzz.token_set_ratio, both_a) / 100.0
    if both_a.any():
        ha = np.array([_house_number(x) if x is not None else None for x in aa], dtype=object)
        hb = np.array([_house_number(x) if x is not None else None for x in ab], dtype=object)
        diff = both_a & _present(ha) & _present(hb) & np.array([x != y for x, y in zip(ha, hb, strict=True)])
        sim[diff] = np.minimum(sim[diff], 0.3)
    f["address_sim"] = sim
    f["postal_exact"] = _exact_vec(_col(left, "postal_norm"), _col(right, "postal_norm"))
    ba, bb = _col(left, "birthdate_norm"), _col(right, "birthdate_norm")
    both_b = _present(ba) & _present(bb)
    bex = np.full(n, np.nan)
    bcf = np.zeros(n)
    if both_b.any():
        eq = np.zeros(n, dtype=bool)
        eq[both_b] = np.array([x == y for x, y in zip(ba[both_b], bb[both_b], strict=True)])
        dist = np.full(n, np.inf)
        dist[both_b] = process.cpdist(_strs(ba[both_b]), _strs(bb[both_b]), scorer=Levenshtein.distance, dtype=np.int64, workers=1)
        bex[both_b & eq] = 1.0
        typo = both_b & ~eq & (dist <= tol)
        bex[typo] = 0.5
        conflict = both_b & ~eq & (dist > tol)
        bex[conflict] = 0.0
        bcf[conflict] = 1.0
    f["birthdate_exact"], f["birthdate_conflict"] = bex, bcf
    f["ck_exact"] = _exact_vec(_col(left, "ck"), _col(right, "ck"))
    f["loy_exact"] = _exact_vec(_col(left, "loy_id_norm"), _col(right, "loy_id_norm"))
    fa, fb = _col(left, "fk_json"), _col(right, "fk_json")
    fk = np.full(n, np.nan)
    for i in np.flatnonzero(_present(fa) | _present(fb)):
        da, db = _fks({"fk_json": fa[i]}), _fks({"fk_json": fb[i]})
        shared = [ns for ns in da if ns in db and da[ns] == db[ns]]
        fk[i] = 1.0 if shared else (0.0 if da and db else np.nan)
    f["fk_shared"] = fk
    allq = np.ones(n, dtype=bool)
    anyv = np.zeros(n, dtype=bool)
    for k in TRIVIAL_DUPE_FIELDS:
        xa, xb = _col(left, k), _col(right, k)
        allq &= np.array([x == y for x, y in zip(xa, xb, strict=True)])
        anyv |= _present(xa)
    f["trivial_dupe"] = (allq & anyv).astype(np.float64)
    return pd.DataFrame(f, columns=FEATURE_NAMES)
