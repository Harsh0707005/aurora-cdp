"""Destinations: CSV export (working) and webhook (stub)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

log = logging.getLogger(__name__)

EXPORT_COLUMNS = [
    "aurora_id", "given_name", "surname", "email", "phone", "address", "city", "state", "postal",
    "country", "birthdate", "order_count", "total_spend", "last_order_ts", "datasources", "record_count",
]


def _log(con, destination_id, segment_name, kind, target, rows, status):
    con.execute(
        "INSERT INTO destination_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
        [destination_id, segment_name, kind, target, rows, status, datetime.utcnow()],
    )


def export_csv(con: duckdb.DuckDBPyConnection, segment_name: str, members: pd.DataFrame, outputs_dir: str | Path) -> Path:
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    cols = [c for c in EXPORT_COLUMNS if c in members.columns]
    stamped = outputs_dir / f"{segment_name}_{stamp}.csv"
    latest = outputs_dir / f"{segment_name}.csv"
    members[cols].to_csv(stamped, index=False)
    members[cols].to_csv(latest, index=False)
    _log(con, uuid.uuid4().hex[:16], segment_name, "csv", str(stamped), len(members), "succeeded")
    return latest


def send_webhook(con: duckdb.DuckDBPyConnection, segment_name: str, members: pd.DataFrame, url: str, dry_run: bool = True) -> dict:
    """Stub: builds the JSON payload; only POSTs when dry_run=False. TODO: batching, retries, auth headers."""
    payload = {"segment": segment_name, "count": len(members), "profiles": members[[c for c in EXPORT_COLUMNS if c in members.columns]].head(1000).to_dict(orient="records")}
    body = json.dumps(payload, default=str)
    status = "dry_run"
    if not dry_run:
        import urllib.request

        req = urllib.request.Request(url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            status = f"http_{resp.status}"
    _log(con, uuid.uuid4().hex[:16], segment_name, "webhook", url, len(members), status)
    return {"status": status, "bytes": len(body)}
