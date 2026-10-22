"""Schema-on-read landing zone.

Raw CSV / Parquet rows are stored as JSON payloads in `bronze_landing`, keyed by a sha256 row hash so
re-ingesting the same rows is an exact no-op (trivial duplicates never reach matching). A `full` load
retires every prior current row of the same (source, feed); an `incremental` load appends new hashes only.
Amperity analogue: feeds landing into domain tables (docs/research internals §3.2).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from aurora_cdp.storage.duck import write_df


@dataclass
class IngestResult:
    batch_id: str
    source: str
    feed: str
    file_path: str
    load_mode: str
    rows_read: int
    rows_loaded: int
    rows_deduped: int

    def summary(self) -> str:
        return (
            f"ingested {self.source}/{self.feed}: read={self.rows_read} loaded={self.rows_loaded} "
            f"deduped={self.rows_deduped} mode={self.load_mode} batch={self.batch_id}"
        )


def read_any(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if path.suffix.lower() in {".csv", ".txt"}:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        return pd.read_json(path, lines=True, dtype=False).astype(object)
    if path.suffix.lower() == ".json":
        return pd.read_json(path, dtype=False).astype(object)
    raise ValueError(f"Unsupported file type: {path} (csv, parquet, jsonl, json)")


def _canonical_row(row: dict) -> str:
    cleaned = {k: ("" if v is None else str(v)) for k, v in row.items()}
    return json.dumps(cleaned, sort_keys=True, ensure_ascii=False)


def row_hash(row: dict) -> str:
    return hashlib.sha256(_canonical_row(row).encode("utf-8")).hexdigest()


def frame_to_payloads(df: pd.DataFrame) -> pd.DataFrame:
    df = df.astype(object).where(pd.notnull(df), None)
    records = df.to_dict(orient="records")
    payloads = [_canonical_row(r) for r in records]
    hashes = [hashlib.sha256(p.encode("utf-8")).hexdigest() for p in payloads]
    return pd.DataFrame({"row_hash": hashes, "payload": payloads})


def ingest_frame(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    source: str,
    feed: str,
    load_mode: str = "incremental",
    file_path: str = "",
) -> IngestResult:
    if load_mode not in {"full", "incremental"}:
        raise ValueError("load_mode must be 'full' or 'incremental'")
    batch_id = uuid.uuid4().hex[:16]
    now = datetime.utcnow()
    frame = frame_to_payloads(df)
    rows_read = len(frame)
    frame = frame.drop_duplicates(subset=["row_hash"])  # dedupe within the file

    if load_mode == "full":
        con.execute(
            "UPDATE bronze_landing SET is_current = FALSE WHERE source = ? AND feed = ? AND is_current",
            [source, feed],
        )
        existing: set[str] = set()
    else:
        existing = {
            r[0]
            for r in con.execute(
                "SELECT row_hash FROM bronze_landing WHERE source = ? AND feed = ? AND is_current",
                [source, feed],
            ).fetchall()
        }
    new_rows = frame[~frame["row_hash"].isin(existing)].copy()
    new_rows["source"] = source
    new_rows["feed"] = feed
    new_rows["batch_id"] = batch_id
    new_rows["ingested_at"] = now
    new_rows["is_current"] = True
    loaded = write_df(
        con,
        "bronze_landing",
        new_rows,
        ["row_hash", "source", "feed", "batch_id", "payload", "ingested_at", "is_current"],
    )
    con.execute(
        "INSERT INTO bronze_batches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [batch_id, source, feed, file_path, load_mode, rows_read, loaded, rows_read - loaded, now],
    )
    return IngestResult(batch_id, source, feed, file_path, load_mode, rows_read, loaded, rows_read - loaded)


def ingest_file(
    con: duckdb.DuckDBPyConnection,
    path: str | Path,
    source: str,
    feed: str,
    load_mode: str = "incremental",
) -> IngestResult:
    df = read_any(path)
    return ingest_frame(con, df, source, feed, load_mode, file_path=str(path))


def landing_frame(
    con: duckdb.DuckDBPyConnection, source: str, feed: str, batch_id: str | None = None
) -> pd.DataFrame:
    """Expand the JSON payloads of a feed back into a DataFrame (schema-on-read)."""
    sql = "SELECT row_hash, batch_id, payload FROM bronze_landing WHERE source = ? AND feed = ? AND is_current"
    params: list = [source, feed]
    if batch_id:
        sql += " AND batch_id = ?"
        params.append(batch_id)
    rows = con.execute(sql, params).fetchall()
    if not rows:
        return pd.DataFrame()
    payloads = [json.loads(r[2]) for r in rows]
    df = pd.DataFrame(payloads)
    df["__row_hash"] = [r[0] for r in rows]
    df["__batch_id"] = [r[1] for r in rows]
    return df
