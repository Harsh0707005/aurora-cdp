"""Import every package, run the demo in fast mode, assert the outputs exist, hit the API."""

from __future__ import annotations

import csv
import importlib
from pathlib import Path

import pytest

PACKAGES = [
    "aurora_cdp",
    "aurora_cdp.config",
    "aurora_cdp.ingestion.landing",
    "aurora_cdp.ingestion.normalize",
    "aurora_cdp.ingestion.semantics",
    "aurora_cdp.storage.duck",
    "aurora_cdp.stitch.blocking",
    "aurora_cdp.stitch.features",
    "aurora_cdp.stitch.matcher",
    "aurora_cdp.stitch.cluster",
    "aurora_cdp.stitch.stable_id",
    "aurora_cdp.stitch.run",
    "aurora_cdp.profile.survivorship",
    "aurora_cdp.profile.builder",
    "aurora_cdp.audiences.segmenter",
    "aurora_cdp.audiences.destinations",
    "aurora_cdp.orchestration.pipeline",
    "aurora_cdp.orchestration.scheduler",
    "aurora_cdp.api.main",
    "aurora_cdp.cli",
    "aurora_cdp.demo",
    "aurora_cdp.tuning",
    "aurora_cdp.adapter",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_imports(name):
    assert importlib.import_module(name)


def test_demo_fast_end_to_end(workspace):
    from aurora_cdp.config import load_config
    from aurora_cdp.demo import run_demo

    ws, out = workspace
    cfg = load_config(overrides={"workspace": str(ws), "outputs_dir": str(out)})
    result = run_demo(cfg, fast=True)

    assert Path(result["db"]).exists(), "DuckDB file should be created under the workspace"
    assert (ws / "runs.jsonl").exists()
    export = Path(result["export"])
    assert export.exists() and export.suffix == ".csv"
    with export.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows and "aurora_id" in rows[0] and "email" in rows[0]
    assert result["profiles"] > 0

    m1, m2 = result["run1"]["metrics"], result["run2"]["metrics"]
    assert m1["records"] > 100 and m1["clusters"] < m1["records"], "stitch should merge records"
    assert m2["mode"] == "incremental" and m2["jitter"]["records_compared"] == m1["records"]
    assert m2["jitter"]["jitter_pct"] <= 2.0, "stable IDs: existing records keep their IDs across runs"
    assert m2["jitter"]["ids_minted"] > 0, "late batch introduces new entities"


def test_api_health_and_endpoints(workspace):
    from fastapi.testclient import TestClient

    from aurora_cdp.api.main import app
    from aurora_cdp.config import load_config
    from aurora_cdp.demo import run_demo

    ws, out = workspace
    cfg = load_config(overrides={"workspace": str(ws), "outputs_dir": str(out)})
    run_demo(cfg, fast=True, people=60)
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    metrics = client.get("/metrics").json()
    assert metrics["metrics"]["clusters"] > 0
    profiles = client.get("/profiles?limit=3").json()
    assert profiles["total"] > 0 and len(profiles["profiles"]) == 3
    aid = profiles["profiles"][0]["aurora_id"]
    assert client.get(f"/profiles/{aid}").json()["profile"]["aurora_id"] == aid
    assert client.get(f"/clusters/{aid}").json()["members"]
    assert client.get("/ui").status_code == 200
    assert client.get(f"/ui/clusters/{aid}").status_code == 200


def test_adapter_contract(workspace, tmp_path):
    """`aurora stitch run --input --out` emits (source_record_id, unified_id, run_date)."""
    import pandas as pd

    from aurora_cdp.adapter import ASSIGNMENT_COLUMNS, run_on_file
    from aurora_cdp.config import load_config

    ws, out = workspace
    cfg = load_config(overrides={"workspace": str(ws), "outputs_dir": str(out)})
    rows = [
        {"source_record_id": "a1", "datasource": "crm", "given_name": "Ann", "surname": "Lee", "email": "ann.lee@example.org", "phone": "206-555-0100"},
        {"source_record_id": "b1", "datasource": "web", "given_name": "Annie", "surname": "Lee", "email": "ANN.LEE@example.org", "phone": ""},
        {"source_record_id": "c1", "datasource": "crm", "given_name": "Bob", "surname": "Ray", "email": "bob@example.org", "phone": ""},
    ]
    inp = tmp_path / "in.csv"
    pd.DataFrame(rows).to_csv(inp, index=False)
    res = run_on_file(cfg, inp, tmp_path / "assign.csv", scores_out=tmp_path / "scores.csv")
    assign = pd.read_csv(tmp_path / "assign.csv")
    assert list(assign.columns) == ASSIGNMENT_COLUMNS
    assert len(assign) == 3 and res["rows"] == 3
    by_id = assign.set_index("source_record_id")["unified_id"]
    assert by_id["a1"] == by_id["b1"] != by_id["c1"]
    assert (tmp_path / "scores.csv").exists()
