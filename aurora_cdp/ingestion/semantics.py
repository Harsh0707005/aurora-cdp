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
    fk_rows = []
    for _, row in df.iterrows():
        fks = {}
        for col, ns in fk_map.items():
            v = _clean(row.get(col))
            if v:
                fks[f"fk-{ns}"] = v
        fk_rows.append(json.dumps(fks, sort_keys=True) if fks else None)
    out["fk_json"] = fk_rows
    upd_col = inverse.get("update_dt")
    out["update_dt"] = df[upd_col].map(_parse_dt) if upd_col and upd_col in df.columns else None
    out["row_hash"] = df["__row_hash"] if "__row_hash" in df.columns else None
    out["batch_id"] = df["__batch_id"] if "__batch_id" in df.columns else None
    out["tagged_at"] = datetime.utcnow()
    out = out[out["pk"].notna()]
    return out[RAW_COLUMNS].reset_index(drop=True)
