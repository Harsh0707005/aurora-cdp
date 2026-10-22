"""Stitch labels (forced merge / split) and the manual blocklist: loader validation, pair-level veto in clustering,
end-to-end through the adapter (edges, metrics, stitch_scores rows), default behaviour untouched."""

from __future__ import annotations

import pandas as pd
import pytest

from aurora_cdp.adapters import resolve_records
from aurora_cdp.config import load_config
from aurora_cdp.stitch.cluster import cluster_records
from aurora_cdp.stitch.labels import StitchLabels, apply_split_labels, load_labels, resolve_labels
from aurora_cdp.stitch.run import apply_blocklist, manual_blocklist

CFG = load_config(use_last_best=False)
HEADER = "left_datasource,left_pk,right_datasource,right_pk,label\n"


# ----------------------------------------------------------------------------------------- loader
def test_load_labels_parses_dedupes_and_validates(tmp_path):
    f = tmp_path / "labels.csv"
    f.write_text(HEADER + "crm,1,web,2,merge\nweb,2,crm,1,MERGE\ncrm,3,crm,4,split\n,,,,\n")
    lab = load_labels(f)
    assert lab.merge == [("crm|1", "web|2")] and lab.split == [("crm|3", "crm|4")] and len(lab) == 2
    assert len(load_labels(None)) == 0
    with pytest.raises(FileNotFoundError):
        load_labels(tmp_path / "missing.csv")
    bad = tmp_path / "bad.csv"
    for body, msg in (
        ("left_datasource,left_pk,label\ncrm,1,merge\n", "lacks columns"),
        (HEADER + "crm,1,web,2,maybe\n", "label must be one of"),
        (HEADER + "crm,1,crm,1,merge\n", "against itself"),
        (HEADER + "crm,1,web,2,merge\nweb,2,crm,1,split\n", "both merge and split"),
        (HEADER + "crm,1,,2,merge\n", "every column must be filled"),
    ):
        bad.write_text(body)
        with pytest.raises(ValueError, match=msg):
            load_labels(bad)


def test_resolve_and_split_filter():
    import numpy as np

    lab = StitchLabels(merge=[("a", "c")], split=[("a", "b"), ("x", "a")])
    r = resolve_labels(lab, {"a": 0, "b": 1, "c": 2})
    assert r.merge_left.tolist() == [0] and r.merge_right.tolist() == [2]
    assert r.split_left.tolist() == [0] and r.split_right.tolist() == [1] and r.unmatched == 1
    assert r.forbidden == [(0, 1)] and r.as_metrics() == {
        "labels_merge": 1,
        "labels_split": 1,
        "labels_unmatched": 1,
    }
    left, right, score = np.array([0, 1, 1]), np.array([1, 2, 0]), np.array([4.0, 3.5, 5.0])
    nl, nr, ns, removed = apply_split_labels(left, right, score, r)
    assert removed == 2 and nl.tolist() == [1] and nr.tolist() == [2] and ns.tolist() == [3.5]


# ----------------------------------------------------------------------------------------- clustering veto
def test_cluster_records_honours_forbidden_pairs_transitively():
    rids = ["a", "b", "c", "d"]
    edges = [("a", "b", 5.0), ("b", "c", 5.0), ("c", "d", 4.0)]
    conflict = {r: {"birthdate": None} for r in rids}
    free = cluster_records(rids, edges, conflict, CFG.cluster)
    assert len({free.assignment[r] for r in rids}) == 1
    res = cluster_records(rids, edges, conflict, CFG.cluster, forbidden=[("a", "c")])
    assert res.assignment["a"] != res.assignment["c"]
    assert res.assignment["a"] == res.assignment["b"], "strongest edge first, then b-c is vetoed"
    assert res.assignment["c"] == res.assignment["d"]
    assert res.qa["edges_rejected_by_label"] == 1 and res.qa["edges_rejected_by_conflict"] == 0
    # unknown rids in the veto list are ignored; a veto never changes anything when the pair is not connected
    same = cluster_records(rids, edges, conflict, CFG.cluster, forbidden=[("zz", "a")])
    assert same.assignment == free.assignment


# ----------------------------------------------------------------------------------------- end to end
PEOPLE = [
    {
        "source_record_id": "1",
        "given_name": "Michael",
        "surname": "Chen",
        "email": "michael.chen@example.org",
        "postal": "98101",
    },
    {
        "source_record_id": "2",
        "given_name": "Mike",
        "surname": "Chen",
        "email": "michael.chen@example.org",
        "postal": "98101",
    },
    {
        "source_record_id": "3",
        "given_name": "Michael",
        "surname": "Chen",
        "phone": "2065550101",
        "postal": "98101",
        "email": "michael.chen@example.org",
    },
    {
        "source_record_id": "4",
        "given_name": "Sara",
        "surname": "Novak",
        "email": "sara@example.org",
        "postal": "02108",
    },
    {
        "source_record_id": "5",
        "given_name": "Tomas",
        "surname": "Rossi",
        "email": "t.rossi@example.org",
        "postal": "60601",
    },
]


def _ids(res):
    return dict(
        zip(res.assignments["source_record_id"], res.assignments["unified_id"], strict=True)
    )


def test_labels_end_to_end_merge_split_and_metrics(tmp_path):
    df = pd.DataFrame(PEOPLE)
    base = resolve_records(df, workspace=tmp_path / "ws0")
    ids = _ids(base)
    assert ids["1"] == ids["2"] == ids["3"] and ids["4"] != ids["5"] != ids["1"]
    assert (
        base.metrics["labels_merge"] == 0
        and base.metrics["labels_split"] == 0
        and base.metrics["edges_removed_by_label"] == 0
    )
    labels = tmp_path / "labels.csv"
    labels.write_text(
        HEADER + "input,1,input,3,split\ninput,4,input,5,merge\ninput,1,input,999,merge\n"
    )
    res = resolve_records(df, config={"labels": {"file": str(labels)}}, workspace=tmp_path / "ws1")
    ids = _ids(res)
    assert ids["1"] != ids["3"], "split label keeps 1 and 3 apart even though 2 links both"
    assert ids["2"] in (ids["1"], ids["3"])
    assert ids["4"] == ids["5"], "merge label joins two unrelated people"
    m = res.metrics
    assert m["labels_merge"] == 1 and m["labels_split"] == 1 and m["labels_unmatched"] == 1
    assert m["edges_rejected_by_label"] >= 1 and m["edges_removed_by_label"] >= 1
    types = res.scores["match_type"]
    assert (types == "label_merge").sum() == 1 and (types == "label_split").sum() == 1
    merge_row = res.scores[types == "label_merge"].iloc[0]
    assert (
        merge_row["score"] == 5.0
        and bool(merge_row["is_edge"])
        and merge_row["match_category"] == "exact"
    )
    split_row = res.scores[types == "label_split"].iloc[0]
    assert split_row["score"] == 0.0 and not bool(split_row["is_edge"])
    # labels are idempotent across runs and survive the incremental/stable-id path (same workspace)
    res2 = resolve_records(df, config={"labels": {"file": str(labels)}}, workspace=tmp_path / "ws1")
    assert _ids(res2)["1"] != _ids(res2)["3"] and _ids(res2)["4"] == _ids(res2)["5"]
    # a broken labels file fails loudly rather than being ignored
    broken = tmp_path / "broken.csv"
    broken.write_text(HEADER + "input,1,input,2,nope\n")
    with pytest.raises(ValueError):
        resolve_records(df, config={"labels": {"file": str(broken)}}, workspace=tmp_path / "ws3")


# ----------------------------------------------------------------------------------------- manual blocklist
def test_manual_blocklist_normalises_values_and_blanks_records(tmp_path):
    cfg = load_config(
        use_last_best=False,
        overrides={
            "blocklist": {
                "manual": {
                    "email": ["Michael.Chen+promo@Example.org"],
                    "phone": "(206) 555-0101",
                    "address": ["12 Main St."],
                }
            }
        },
    )
    rules = {sem: vals for _col, sem, vals in manual_blocklist(cfg)}
    assert (
        "michael.chen@example.org" in rules["email"]
        and "2065550101" in rules["phone"]
        and "12 MAIN STREET" in rules["address"]
    )
    assert manual_blocklist(CFG) == []
    frame = pd.DataFrame(
        {
            "email_norm": ["michael.chen@example.org", "x@y.org"],
            "phone_match": ["2065550101", None],
            "address_norm": ["12 MAIN STREET", "1 ELM"],
            "given_name_canon": ["MICHAEL", "X"],
            "surname_norm": ["CHEN", "Y"],
        }
    )
    out, flagged = apply_blocklist(frame, cfg)
    assert pd.isna(out["email_norm"][0]) and out["email_norm"][1] == "x@y.org"
    assert out["phone_match"].isna().all()
    assert pd.isna(out["address_norm"][0]) and out["address_norm"][1] == "1 ELM"
    manual = [f for f in flagged if f["reason"] == "manual"]
    assert {(f["semantic"], f["value"], f["distinct_count"]) for f in manual} >= {
        ("email", "michael.chen@example.org", 1),
        ("phone", "2065550101", 1),
        ("address", "12 MAIN STREET", 1),
    }
    # end to end: the shared e-mail no longer links 1 and 2
    df = pd.DataFrame(PEOPLE[:2] + PEOPLE[3:])
    free = _ids(resolve_records(df, workspace=tmp_path / "a"))
    assert free["1"] == free["2"]
    res = resolve_records(
        df,
        config={"blocklist": {"manual": {"email": ["michael.chen@example.org"]}}},
        workspace=tmp_path / "c",
    )
    assert _ids(res)["1"] != _ids(res)["2"]
    assert res.metrics["blocklisted_values"] >= 1
