"""Persisted Stitch labels: stored in the workspace table, applied by the run, survive across runs."""

from __future__ import annotations

import pandas as pd

from aurora_cdp.adapters import resolve_records
from aurora_cdp.config import load_config
from aurora_cdp.stitch.labels import add_label, load_labels_table, merge_labels
from aurora_cdp.storage.duck import connect, init_schema


def _rows():
    return pd.DataFrame([
        {"source_record_id": "a1", "given_name": "Dana", "surname": "Kim", "email": "dana@x.org"},
        {"source_record_id": "a2", "given_name": "Dana", "surname": "Kim", "email": "dana@x.org"},
        {"source_record_id": "b1", "given_name": "Pat", "surname": "Roe", "email": "pat@y.org"},
    ])


def test_labels_persist_and_apply(tmp_path):
    ws = tmp_path / "ws"
    cfg = load_config(overrides={"workspace": str(ws)}, use_last_best=False)
    con = connect(cfg.db_path)
    init_schema(con)
    lid = add_label(con, ("s", "a1"), ("s", "a2"), "split", "tester", "same email but two people")
    assert add_label(con, ("s", "a1"), ("s", "a2"), "split") == lid  # idempotent
    add_label(con, ("s", "a1"), ("s", "b1"), "merge")
    con.close()
    # a later run in the same workspace reads the table; the adapter uses its own throwaway DB, so seed via workspace=
    res = resolve_records(_rows(), config=cfg, datasource="s", workspace=ws / "adapter")
    assert res.metrics["labels_split"] == 0  # throwaway workspace: no table labels visible there
    con = connect(cfg.db_path)
    labels = merge_labels(load_labels_table(con))
    assert ("s|a1", "s|a2") in labels.split and ("s|a1", "s|b1") in labels.merge
    # contradicting label replaces the old one
    add_label(con, ("s", "a1"), ("s", "a2"), "merge")
    labels2 = load_labels_table(con)
    assert ("s|a1", "s|a2") in labels2.merge and ("s|a1", "s|a2") not in labels2.split
    con.close()
