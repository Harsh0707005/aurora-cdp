"""Semantic tagging: map per-source field names onto the shared semantic vocabulary.

A source mapping looks like (YAML / dict):

    crm:
      feed: customers
      pk: customer_id
      ck: null
      fields:
        first_name: given_name
        last_name: surname
        email_address: email
        mobile: phone
        addr1: address
        zip: postal
        dob: birthdate
        loyalty_no: loy_id
        updated_at: update_dt
      fk:
        pos_customer: pos         # column -> fk namespace (becomes fk-pos)

Amperity analogue: semantic tags (given-name, surname, email, phone, address group, fk-*, pk, ck)
applied per feed (docs/research internals §2.2).
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
from dateutil import parser as dateparser

PROFILE_SEMANTICS = [
    "given_name",
    "surname",
    "email",
    "phone",
    "address",
    "address2",
    "city",
    "state",
    "postal",
    "country",
    "birthdate",
    "loy_id",
]
RAW_COLUMNS = [
    "datasource",
    "pk",
    "ck",
    *PROFILE_SEMANTICS,
    "fk_json",
    "update_dt",
    "row_hash",
    "batch_id",
    "tagged_at",
]


def _clean(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_dt(value) -> datetime | None:
    s = _clean(value)
    if not s:
        return None
    try:
        return dateparser.parse(s)
    except (ValueError, OverflowError):
        return None


def _parse_dt_series(s: pd.Series) -> pd.Series:
    """Vectorised :func:`_parse_dt`: datetime columns and ISO-8601 strings take the pandas fast path; anything the
    fast path cannot parse (or a column that mixes time zones) falls back to dateutil row by row."""
    if pd.api.types.is_datetime64_any_dtype(s.dtype):
        # already datetimes: str(ts) -> dateutil round-trips to the same datetime, NaT -> None
        out = pd.Series(s.dt.to_pydatetime(), index=s.index, dtype=object) if len(s) else pd.Series(dtype=object)
        out[s.isna()] = None
        return out
    cleaned = s.map(_clean)
    try:
        fast = pd.to_datetime(cleaned, errors="coerce", format="ISO8601")
    except (ValueError, TypeError):
        return cleaned.map(_parse_dt)
    out = pd.Series(fast.dt.to_pydatetime(), index=s.index, dtype=object) if len(fast) else pd.Series(dtype=object)
    missed = fast.isna() & cleaned.notna()
    if missed.any():
        out[missed] = cleaned[missed].map(_parse_dt)
    out[fast.isna() & ~missed] = None
    return out


def apply_semantics(df: pd.DataFrame, source: str, mapping: dict) -> pd.DataFrame:
    """Return a DataFrame with RAW_COLUMNS for one source using its semantic mapping."""
    if df.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)
    fields: dict[str, str] = mapping.get("fields", {})
    fk_map: dict[str, str] = mapping.get("fk", {}) or {}
    pk_col = mapping["pk"]
    ck_col = mapping.get("ck")

    out = pd.DataFrame(index=df.index)
    out["datasource"] = source
    out["pk"] = df[pk_col].map(_clean)
    out["ck"] = df[ck_col].map(_clean) if ck_col and ck_col in df.columns else None
    inverse: dict[str, str] = {}
    for col, sem in fields.items():
        if sem in inverse:
            raise ValueError(f"semantic '{sem}' mapped twice for source {source}")
        inverse[sem] = col
    for sem in PROFILE_SEMANTICS:
        col = inverse.get(sem)
        out[sem] = df[col].map(_clean) if col and col in df.columns else None
    fk_cols = {col: ns for col, ns in fk_map.items() if col in df.columns}
    if fk_cols:
        fk_rows = []
        for _, row in df[list(fk_cols)].iterrows():
            fks = {}
            for col, ns in fk_cols.items():
                v = _clean(row.get(col))
                if v:
                    fks[f"fk-{ns}"] = v
            fk_rows.append(json.dumps(fks, sort_keys=True) if fks else None)
        out["fk_json"] = fk_rows
    else:
        out["fk_json"] = None
    upd_col = inverse.get("update_dt")
    out["update_dt"] = _parse_dt_series(df[upd_col]) if upd_col and upd_col in df.columns else None
    out["row_hash"] = df["__row_hash"] if "__row_hash" in df.columns else None
    out["batch_id"] = df["__batch_id"] if "__batch_id" in df.columns else None
    out["tagged_at"] = datetime.utcnow()
    out = out[out["pk"].notna()]
    return out[RAW_COLUMNS].reset_index(drop=True)
