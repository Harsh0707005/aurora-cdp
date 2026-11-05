"""Stitch runs only when data changed (force overrides); Amperity's group-id label form."""

from __future__ import annotations

import pandas as pd
import pytest

from aurora_cdp.adapters import resolve_records
from aurora_cdp.config import load_config
from aurora_cdp.orchestration.pipeline import run_pipeline, stitch_updates_pending
from aurora_cdp.stitch.labels import group_labels_to_pairs, load_labels
from aurora_cdp.storage.duck import connect, init_schema


def test_group_labels_expand_to_merge_chains_and_cross_group_splits(tmp_path):
    f = tmp_path / "groups.csv"
    f.write_text("datasource,pk,group_id\nweb,1,G1\ncrm,2,G1\npos,3,G1\nweb,9,G2\n")
    labels = load_labels(f)
    assert sorted(labels.merge) == [("crm|2", "pos|3"), ("pos|3", "web|1")] or len(labels.merge) == 2
    assert len(labels.split) == 3 and all("web|9" in p for p in labels.split)
    with pytest.raises(ValueError):
        group_labels_to_pairs([("web", "1", "G1"), ("web", "1", "G2")])


def test_group_labels_drive_the_resolver(tmp_path):
    recs = pd.DataFrame([
        {"source_record_id": "1", "datasource": "web", "given_name": "Amy", "surname": "Chen", "email": "amy@x.org"},
        {"source_record_id": "2", "datasource": "crm", "given_name": "Amy", "surname": "Chen", "email": "amy@x.org"},
        {"source_record_id": "3", "datasource": "pos", "given_name": "Zed", "surname": "Zulu", "email": "zed@x.org"},
    ])
    f = tmp_path / "groups.csv"
    f.write_text("datasource,pk,group_id\nweb,1,A\ncrm,2,B\npos,3,A\n")   # split 1 from 2 despite the shared e-mail; force 1 with 3
    ids = {r.pk: r.unified_id for r in resolve_records(recs, config={"labels": {"file": str(f)}}).assignments.itertuples()}
    assert ids["1"] == ids["3"] and ids["1"] != ids["2"]


def test_pipeline_skips_stitch_without_new_data_and_runs_when_forced(tmp_path):
    cfg = load_config(overrides={"workspace": str(tmp_path / "ws")}, use_last_best=False)
    (tmp_path / "ws").mkdir()
    feed = tmp_path / "crm.csv"
    feed.write_text("id,first,last,email\n1,Amy,Chen,amy@x.org\n2,Amy,Chen,amy@x.org\n")
    sem = {"pk": "id", "fields": {"first": "given_name", "last": "surname", "email": "email"}}
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        spec = {"name": "t", "feeds": [{"source": "crm", "feed": "c", "path": str(feed), "semantics": sem}], "stitch": {"mode": "full"}}
        r1 = run_pipeline(con, cfg, spec)
        first_run = r1.stitch_run_id
        assert first_run and stitch_updates_pending(con)["new_rows"] == 0
        r2 = run_pipeline(con, cfg, {"name": "t", "stitch": {"mode": "full"}})          # nothing landed since -> skipped
        assert r2.stitch_run_id == first_run and "skipped" in r2.steps[-1]["detail"]
        r3 = run_pipeline(con, cfg, {"name": "t", "stitch": {"mode": "full", "force": True}})
        assert r3.stitch_run_id != first_run and r3.steps[-1]["detail"].get("forced") is True
        feed.write_text("id,first,last,email\n1,Amy,Chen,amy@x.org\n2,Amy,Chen,amy@x.org\n3,Bo,Li,bo@x.org\n")
        r4 = run_pipeline(con, cfg, spec)                                                 # new row landed -> runs
        assert r4.stitch_run_id not in (first_run, r3.stitch_run_id)
    finally:
        con.close()
