"""File connectors: jsonl / parquet exports log a destination run and write latest + stamped files."""

from __future__ import annotations

import json

import duckdb
import pandas as pd
import pytest

from aurora_cdp.audiences.destinations import export_file
from aurora_cdp.storage.duck import init_schema


def test_jsonl_and_parquet_exports(tmp_path):
    con = duckdb.connect(str(tmp_path / "x.duckdb"))
    init_schema(con)
    members = pd.DataFrame([{"aurora_id": "a", "given_name": "Ann", "email": "a@x.org", "order_count": 2, "extra": 1},
                            {"aurora_id": "b", "given_name": "Bob", "email": None, "order_count": 0, "extra": 2}])
    p = export_file(con, "vip", members, tmp_path / "out", "jsonl")
    lines = [json.loads(l) for l in p.read_text().splitlines()]
    assert p.name == "vip.jsonl" and len(lines) == 2 and "extra" not in lines[0] and lines[0]["aurora_id"] == "a"
    q = export_file(con, "vip", members, tmp_path / "out", "parquet", columns=["aurora_id", "extra"])
    assert pd.read_parquet(q).columns.tolist() == ["aurora_id", "extra"]
    kinds = [r[0] for r in con.execute("SELECT kind FROM destination_runs ORDER BY kind").fetchall()]
    assert kinds == ["jsonl", "parquet"]
    with pytest.raises(ValueError):
        export_file(con, "vip", members, tmp_path / "out", "xml")
    con.close()
