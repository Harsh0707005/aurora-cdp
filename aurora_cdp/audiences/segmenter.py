"""Simple segment builder over customer_360 (Amperity: segments as SQL over the Customer 360 table, §4.1).

Definition format (JSON/YAML):
    {"name": "wa_buyers", "match": "all",           # all | any
     "filters": [{"field": "state", "op": "=", "value": "WA"},
                 {"field": "order_count", "op": ">=", "value": 1},
                 {"field": "email", "op": "is_not_null"}]}
Only whitelisted columns and operators are accepted; values are bound as parameters (no SQL injection).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import duckdb
import pandas as pd

from aurora_cdp.storage.duck import latest_run_id, read_df, write_df

ALLOWED_OPS = {"=", "!=", ">", ">=", "<", "<=", "like", "ilike", "in", "is_null", "is_not_null"}


def _columns(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {r[0] for r in con.execute("DESCRIBE customer_360").fetchall()}


def build_where(definition: dict, allowed_columns: set[str]) -> tuple[str, list]:
    clauses, params = [], []
    for f in definition.get("filters", []):
        field, op = f["field"], f.get("op", "=").lower()
        if field not in allowed_columns:
            raise ValueError(f"unknown field '{field}'")
        if op not in ALLOWED_OPS:
            raise ValueError(f"unsupported operator '{op}'")
        col = f'"{field}"'
        if op == "is_null":
            clauses.append(f"{col} IS NULL")
        elif op == "is_not_null":
            clauses.append(f"{col} IS NOT NULL")
        elif op == "in":
            vals = list(f.get("value") or [])
            if not vals:
                clauses.append("FALSE")
            else:
                clauses.append(f"{col} IN ({', '.join('?' for _ in vals)})")
                params.extend(vals)
        else:
            sql_op = {"like": "LIKE", "ilike": "ILIKE"}.get(op, op)
            clauses.append(f"{col} {sql_op} ?")
            params.append(f["value"])
    joiner = " OR " if definition.get("match", "all") == "any" else " AND "
    return (joiner.join(clauses) if clauses else "TRUE"), params


@dataclass
class SegmentResult:
    name: str
    run_id: str
    members: pd.DataFrame

    def summary(self) -> str:
        return f"segment '{self.name}' evaluated: {len(self.members)} profiles (run {self.run_id})"


def save_segment(con: duckdb.DuckDBPyConnection, definition: dict) -> None:
    name = definition["name"]
    now = datetime.utcnow()
    con.execute("DELETE FROM segments WHERE segment_name = ?", [name])
    con.execute("INSERT INTO segments VALUES (?, ?, ?, ?)", [name, json.dumps(definition), now, now])


def load_segment(con: duckdb.DuckDBPyConnection, name: str) -> dict:
    row = con.execute("SELECT definition_json FROM segments WHERE segment_name = ?", [name]).fetchone()
    if not row:
        raise KeyError(f"segment '{name}' not found")
    return json.loads(row[0])


def evaluate_segment(con: duckdb.DuckDBPyConnection, definition: dict, persist: bool = True) -> SegmentResult:
    where, params = build_where(definition, _columns(con))
    members = read_df(con, f"SELECT * FROM customer_360 WHERE {where} ORDER BY aurora_id", params)
    run_id = latest_run_id(con) or "no-run"
    if persist:
        con.execute("DELETE FROM segment_members WHERE segment_name = ?", [definition["name"]])
        if len(members):
            m = pd.DataFrame(
                {"segment_name": definition["name"], "run_id": run_id, "aurora_id": members["aurora_id"], "evaluated_at": datetime.utcnow()}
            )
            write_df(con, "segment_members", m)
    return SegmentResult(definition["name"], run_id, members)
