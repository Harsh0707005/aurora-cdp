"""Build golden records (gold_merged_customers, SCD2) and the profile event timeline."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime

import duckdb
import pandas as pd

from aurora_cdp.config import Config
from aurora_cdp.storage.duck import latest_run_id, read_df, write_df

from .survivorship import survive

log = logging.getLogger(__name__)


@dataclass
class ProfileBuildResult:
    run_id: str
    profiles: int
    inserted: int
    closed: int
    events: int

    def summary(self) -> str:
        return f"profiles built for {self.run_id}: profiles={self.profiles} new/changed={self.inserted} closed={self.closed} events={self.events}"


def _row_hash(values: dict) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def build_profiles(con: duckdb.DuckDBPyConnection, cfg: Config, run_id: str | None = None) -> ProfileBuildResult:
    run_id = run_id or latest_run_id(con)
    if run_id is None:
        raise RuntimeError("no successful stitch run found; run `aurora stitch` first")
    scfg = cfg.survivorship
    attributes = list(scfg.get("attributes", []))
    raw = read_df(
        con,
        f"""
        SELECT l.aurora_id, r.datasource, r.pk, r.update_dt, {", ".join("r." + a for a in attributes)}
        FROM silver_unified_raw r
        JOIN id_ledger l ON l.datasource = r.datasource AND l.pk = r.pk AND l.is_current
        QUALIFY ROW_NUMBER() OVER (PARTITION BY r.datasource, r.pk ORDER BY r.tagged_at DESC) = 1
        ORDER BY l.aurora_id, r.datasource, r.pk
        """,
    )
    now = datetime.utcnow()
    rows = []
    for aurora_id, grp in raw.groupby("aurora_id", sort=True):
        recs = grp.to_dict(orient="records")
        values, prov = survive(recs, scfg, attributes)
        sources = ",".join(sorted({r["datasource"] for r in recs}))
        row = {"aurora_id": aurora_id, **values}
        row["provenance_json"] = json.dumps(prov)
        row["record_count"] = len(recs)
        row["datasources"] = sources
        row["row_hash"] = _row_hash({**values, "record_count": len(recs), "datasources": sources})
        rows.append(row)
    new = pd.DataFrame(rows)

    current = read_df(con, "SELECT aurora_id, row_hash FROM gold_merged_customers WHERE is_current")
    cur_map = dict(zip(current["aurora_id"], current["row_hash"], strict=False)) if len(current) else {}
    changed_ids = [r["aurora_id"] for r in rows if cur_map.get(r["aurora_id"]) != r["row_hash"]]
    gone_ids = sorted(set(cur_map) - set(new["aurora_id"])) if len(new) else sorted(cur_map)
    to_close = changed_ids + gone_ids
    closed = 0
    if to_close:
        con.register("_aurora_close", pd.DataFrame({"aurora_id": to_close}))
        closed = con.execute(
            "UPDATE gold_merged_customers SET valid_to = ?, is_current = FALSE WHERE is_current AND aurora_id IN (SELECT aurora_id FROM _aurora_close)",
            [now],
        ).fetchone()[0]
        con.unregister("_aurora_close")
    inserted = 0
    if changed_ids:
        ins = new[new["aurora_id"].isin(changed_ids)].copy()
        ins["run_id"] = run_id
        ins["valid_from"] = now
        ins["valid_to"] = None
        ins["is_current"] = True
        inserted = write_df(con, "gold_merged_customers", ins)

    events = build_events(con, cfg, run_id)
    return ProfileBuildResult(run_id, len(rows), inserted, int(closed or 0), events)


def build_events(con: duckdb.DuckDBPyConnection, cfg: Config, run_id: str) -> int:
    """Profile timeline: interaction feeds whose rows carry fk-<namespace> keys to a profile source.

    Interaction feeds are declared in config under `events:` as
      events:
        - source: pos
          feed: orders
          fk_column: customer_no      # value of the foreign key
          fk_namespace: pos           # which datasource/pk namespace it points at
          event_type: order
          ts_column: order_ts
          amount_column: amount
    """
    specs = cfg.get("events") or []
    if not specs:
        return 0
    from aurora_cdp.ingestion.landing import landing_frame

    con.execute("DELETE FROM gold_profile_events")
    total = 0
    graph = read_df(con, "SELECT aurora_id, datasource, pk FROM id_ledger WHERE is_current")
    key = {(d, p): a for a, d, p in graph.itertuples(index=False)}
    for spec in specs:
        df = landing_frame(con, spec["source"], spec["feed"])
        if df.empty:
            continue
        ns = spec["fk_namespace"]
        rows = []
        for rec in df.to_dict(orient="records"):
            fk_value = str(rec.get(spec["fk_column"]) or "").strip()
            if not fk_value:
                continue
            ts = rec.get(spec.get("ts_column"))
            try:
                ts_parsed = pd.to_datetime(ts) if ts else None
            except (ValueError, TypeError):
                ts_parsed = None
            amount = rec.get(spec.get("amount_column"))
            try:
                amount_f = float(amount) if amount not in (None, "") else None
            except (TypeError, ValueError):
                amount_f = None
            rows.append(
                {
                    "event_id": rec.get("__row_hash", "")[:32] or hashlib.sha1(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:32],
                    "aurora_id": key.get((ns, fk_value)),
                    "datasource": spec["source"],
                    "fk_namespace": f"fk-{ns}",
                    "fk_value": fk_value,
                    "event_type": spec.get("event_type", "event"),
                    "event_ts": ts_parsed,
                    "amount": amount_f,
                    "payload": json.dumps({k: v for k, v in rec.items() if not k.startswith("__")}, default=str),
                    "run_id": run_id,
                }
            )
        total += write_df(con, "gold_profile_events", pd.DataFrame(rows))
    return total
