"""Pairwise feature extraction.

Features are computed row-wise in pandas (vectorised via ``mapInPandas`` from
Spark, or directly for the API's on-the-fly resolver). String similarities use
``rapidfuzz`` (MIT). Every feature is a float in [0, 1] except the explicit
conflict indicators, which are 1.0 when a hard disagreement is present.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from rapidfuzz.distance import DamerauLevenshtein, JaroWinkler

from aurora.data.schemas import PAIR_FEATURE_COLUMNS

FEATURE_COLUMNS = PAIR_FEATURE_COLUMNS

# Columns from the standardised frame needed on each side of a pair.
SIDE_COLUMNS = [
    "email_std", "email_canon", "phone_std", "given_std", "given_nick", "surname_std",
    "street_std", "house_no", "postal_std", "dob_std", "loyalty_id",
]


def _jw(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return float(JaroWinkler.normalized_similarity(a, b))


def _dl(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return float(DamerauLevenshtein.normalized_similarity(a, b))


def _days_between(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    try:
        da, db = date.fromisoformat(a), date.fromisoformat(b)
    except ValueError:
        return None
    return abs((da - db).days)


def pair_features(l: dict, r: dict) -> dict[str, float]:
    """Compute the feature vector for one pair of standardised records."""
    f: dict[str, float] = dict.fromkeys(FEATURE_COLUMNS, 0.0)
    le, re_ = l.get("email_std"), r.get("email_std")
    lc, rc = l.get("email_canon"), r.get("email_canon")
    if le and re_:
        f["email_exact"] = 1.0 if (le == re_ or (lc and lc == rc)) else 0.0
        f["email_sim"] = _dl(le.split("@")[0], re_.split("@")[0]) if not f["email_exact"] else 1.0
    lp, rp = l.get("phone_std"), r.get("phone_std")
    if lp and rp:
        f["phone_exact"] = 1.0 if lp == rp else 0.0
        f["phone_prefix"] = 1.0 if (lp[:8] == rp[:8] and lp != rp) else 0.0
    lg, rg = l.get("given_std"), r.get("given_std")
    ls, rs = l.get("surname_std"), r.get("surname_std")
    f["given_jw"] = _jw(lg, rg)
    f["surname_jw"] = _jw(ls, rs)
    f["name_exact"] = 1.0 if (lg and ls and lg == rg and ls == rs) else 0.0
    ln, rn = l.get("given_nick"), r.get("given_nick")
    f["nickname_match"] = 1.0 if (ln and rn and ln == rn and lg != rg) else 0.0
    if ls and rs and f["surname_jw"] < 0.6 and lg and rg and f["given_jw"] < 0.6:
        f["name_conflict"] = 1.0
    # clearly different first names (not nickname variants): spouses / household members
    if lg and rg and f["given_jw"] < 0.75 and not f["nickname_match"]:
        f["given_conflict"] = 1.0
    lpost, rpost = l.get("postal_std"), r.get("postal_std")
    f["postal_eq"] = 1.0 if (lpost and rpost and lpost == rpost) else 0.0
    lh, rh = l.get("house_no"), r.get("house_no")
    f["house_eq"] = 1.0 if (lh and rh and lh == rh and f["postal_eq"]) else 0.0
    f["street_sim"] = _jw(l.get("street_std"), r.get("street_std"))
    days = _days_between(l.get("dob_std"), r.get("dob_std"))
    if days is not None:
        f["dob_eq"] = 1.0 if days == 0 else 0.0
        f["dob_near"] = 1.0 if 0 < days <= 366 else 0.0
        f["dob_conflict"] = 1.0 if days > 366 else 0.0
    lf, rf = l.get("loyalty_id"), r.get("loyalty_id")
    f["fk_match"] = 1.0 if (lf and rf and lf == rf) else 0.0
    return f


def features_frame(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    """Vectorised-ish feature frame for aligned left/right record frames."""
    left = left.astype(object).where(pd.notna(left), None)
    right = right.astype(object).where(pd.notna(right), None)
    lrec = left.to_dict("records")
    rrec = right.to_dict("records")
    rows = [pair_features(a, b) for a, b in zip(lrec, rrec, strict=True)]
    out = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    return out.astype(np.float32)
