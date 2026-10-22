"""DuckDB connection, schema initialisation and point-in-time helpers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
MIGRATIONS_DIR = Path(__file__).with_name("migrations")
_MIGRATION_RE = re.compile(r"^V(\d+)__.*\.sql$")


def connect(db_path: str | Path, read_only: bool = False, settings: dict | None = None) -> duckdb.DuckDBPyConnection:
    """Open the workspace database and apply the memory settings from ``storage.duckdb`` (see defaults.yaml)."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=read_only)
    apply_settings(con, settings, db_path.parent)
    return con


def apply_settings(con: duckdb.DuckDBPyConnection, settings: dict | None, workspace: Path | None = None) -> dict:
    """``SET memory_limit / threads / temp_directory / preserve_insertion_order`` so joins and sorts spill to
    disk instead of growing the process. Returns the effective settings."""
    s = dict(settings or {})
    effective: dict = {}
    if s.get("memory_limit"):
        con.execute(f"SET memory_limit = '{s['memory_limit']}'")
        effective["memory_limit"] = s["memory_limit"]
    if s.get("threads"):
        con.execute(f"SET threads = {int(s['threads'])}")
        effective["threads"] = int(s["threads"])
    tmp = s.get("temp_directory")
    if not tmp and workspace is not None:
        tmp = str(Path(workspace) / "duckdb_tmp")
    if tmp:
        Path(tmp).mkdir(parents=True, exist_ok=True)
        con.execute(f"SET temp_directory = '{tmp}'")
        effective["temp_directory"] = tmp
    if "preserve_insertion_order" in s:
        con.execute(f"SET preserve_insertion_order = {'true' if s['preserve_insertion_order'] else 'false'}")
        effective["preserve_insertion_order"] = bool(s["preserve_insertion_order"])
    return effective


@contextmanager
def connection(db_path: str | Path, read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    con = connect(db_path, read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def _applied_versions(con: duckdb.DuckDBPyConnection) -> set[int]:
    if not table_exists(con, "schema_version"):
        return set()
    return {int(r[0]) for r in con.execute("SELECT version FROM schema_version").fetchall()}


def init_schema(con: duckdb.DuckDBPyConnection) -> list[int]:
    """Apply schema.sql (V1) and any V<nnn>__*.sql migrations not yet recorded. Idempotent."""
    applied_now: list[int] = []
    con.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    if 1 not in _applied_versions(con):
        con.execute(
            "INSERT INTO schema_version VALUES (1, ?, 'initial schema (schema.sql)')",
            [datetime.utcnow()],
        )
        applied_now.append(1)
    done = _applied_versions(con)
    for path in sorted(MIGRATIONS_DIR.glob("V*__*.sql")):
        m = _MIGRATION_RE.match(path.name)
        if not m:
            continue
        version = int(m.group(1))
        if version in done:
            continue
        con.execute(path.read_text(encoding="utf-8"))
        con.execute(
            "INSERT INTO schema_version VALUES (?, ?, ?)", [version, datetime.utcnow(), path.name]
        )
        applied_now.append(version)
    return applied_now


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchone()
    return bool(row and row[0])


def write_df(
    con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame, columns: list[str] | None = None
) -> int:
    """Append a DataFrame into `table` by column name. Returns rows written."""
    if df is None or len(df) == 0:
        return 0
    cols = columns or list(df.columns)
    con.register("_aurora_tmp_df", df[cols])
    col_list = ", ".join(f'"{c}"' for c in cols)
    con.execute(f'INSERT INTO "{table}" ({col_list}) SELECT {col_list} FROM _aurora_tmp_df')
    con.unregister("_aurora_tmp_df")
    return len(df)


def read_df(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    return con.execute(sql, params or []).df()


def latest_run_id(con: duckdb.DuckDBPyConnection, status: str = "succeeded") -> str | None:
    row = con.execute(
        "SELECT run_id FROM stitch_runs WHERE status = ? ORDER BY started_at DESC LIMIT 1", [status]
    ).fetchone()
    return row[0] if row else None


def ledger_as_of(con: duckdb.DuckDBPyConnection, as_of: datetime | None = None) -> pd.DataFrame:
    """Point-in-time view of the id ledger (SCD2): which aurora_id each (datasource, pk) had at `as_of`."""
    if as_of is None:
        return read_df(con, "SELECT aurora_id, datasource, pk FROM id_ledger WHERE is_current")
    return read_df(
        con,
        "SELECT aurora_id, datasource, pk FROM id_ledger "
        "WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)",
        [as_of, as_of],
    )


def merged_customers_as_of(
    con: duckdb.DuckDBPyConnection, as_of: datetime | None = None
) -> pd.DataFrame:
    if as_of is None:
        return read_df(con, "SELECT * FROM gold_merged_customers WHERE is_current")
    return read_df(
        con,
        "SELECT * FROM gold_merged_customers WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)",
        [as_of, as_of],
    )
