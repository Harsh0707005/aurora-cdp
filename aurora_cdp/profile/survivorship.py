"""Per-attribute survivorship with provenance (Amperity: Merged Customers, internals §2.10).

Rule order for each attribute: Field_Priority (per attribute, per source) -> Source_Priority -> recency
(update_dt, newest wins) -> deterministic tie-break on (datasource, pk). Unassigned sources get priority 999.
Every surviving value records where it came from (provenance).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

DEFAULT_PRIORITY = 999


def _priority(attr: str, datasource: str, cfg) -> int:
    field_pri = (cfg.get("field_priority") or {}).get(attr) or {}
    if datasource in field_pri:
        return int(field_pri[datasource])
    return int((cfg.get("source_priority") or {}).get(datasource, DEFAULT_PRIORITY))


def survive(records: list[dict], cfg, attributes: list[str]) -> tuple[dict, dict]:
    """records: raw-attribute dicts for one aurora_id (datasource, pk, update_dt, <attributes>...).
    Returns (values, provenance)."""
    values: dict[str, str | None] = {}
    provenance: dict[str, dict] = {}
    for attr in attributes:
        candidates = []
        for rec in records:
            v = rec.get(attr)
            if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
                continue
            upd = rec.get("update_dt")
            try:
                upd_ts = upd.timestamp() if isinstance(upd, datetime) and not pd.isna(upd) else 0.0
            except (ValueError, AttributeError):
                upd_ts = 0.0
            candidates.append((_priority(attr, rec["datasource"], cfg), -upd_ts, rec["datasource"], rec["pk"], v))
        if not candidates:
            values[attr] = None
            continue
        candidates.sort()
        pri, neg_ts, ds, pk, v = candidates[0]
        rule = "field_priority" if ds in ((cfg.get("field_priority") or {}).get(attr) or {}) else (
            "source_priority" if pri != DEFAULT_PRIORITY else "recency"
        )
        values[attr] = v
        provenance[attr] = {"datasource": ds, "pk": pk, "rule": rule, "priority": pri}
    return values, provenance
