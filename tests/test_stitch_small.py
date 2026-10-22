"""Tiny labelled dataset: matcher + cluster + stable id, with precision/recall bounds and unit checks."""

from __future__ import annotations

import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.evaluation import pairwise_metrics
from aurora_cdp.ingestion.normalize import canonical_email, canonical_phone, preprocess_records
from aurora_cdp.ingestion.semantics import RAW_COLUMNS
from aurora_cdp.stitch.blocking import build_blocks
from aurora_cdp.stitch.cluster import cluster_records
from aurora_cdp.stitch.matcher import score_pairs
from aurora_cdp.stitch.run import records_from_frame
from aurora_cdp.stitch.stable_id import assign_stable_ids

CFG = load_config(use_last_best=False)


def _raw(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in RAW_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df["batch_id"] = "b1"
    df["row_hash"] = "h"
    df["tagged_at"] = pd.Timestamp("2026-01-01")
    return df[RAW_COLUMNS]


LABELLED = [
    # person 1: same person across three sources (email / phone / nickname)
    {"datasource": "crm", "pk": "1", "given_name": "Michael", "surname": "Chen", "email": "michael.chen@example.org", "phone": "(206) 555-0101", "postal": "98101", "birthdate": "1980-05-01", "truth": "p1"},
    {"datasource": "web", "pk": "2", "given_name": "Mike", "surname": "Chen", "email": "Michael.Chen+promo@example.org", "phone": "", "postal": "98101", "truth": "p1"},
    {"datasource": "pos", "pk": "3", "given_name": "MICHAEL", "surname": "CHEN", "email": "", "phone": "2065550101", "postal": "98101", "truth": "p1"},
    # person 2: shares a surname + zip with person 1's city but is a different person (birthdate conflict with p1)
    {"datasource": "crm", "pk": "4", "given_name": "Michelle", "surname": "Chen", "email": "mchen@example.org", "phone": "", "postal": "98101", "birthdate": "1992-09-09", "truth": "p2"},
    {"datasource": "web", "pk": "5", "given_name": "Michelle", "surname": "Chen", "email": "mchen@example.org", "phone": "", "postal": "98101", "birthdate": "1992-09-09", "truth": "p2"},
    # person 3: loyalty key links records with otherwise poor overlap
    {"datasource": "crm", "pk": "6", "given_name": "Robert", "surname": "Patel", "email": "", "phone": "", "loy_id": "LOY77", "truth": "p3"},
    {"datasource": "loyalty", "pk": "7", "given_name": "Bob", "surname": "Patel", "email": "bob.patel@example.org", "phone": "+1 425 555 0199", "loy_id": "LOY77", "birthdate": "1970-01-01", "truth": "p3"},
    # person 4: shares p3's email and name but has a conflicting birthdate -> hard conflict, must not merge
    {"datasource": "web", "pk": "8", "given_name": "Robert", "surname": "Patel", "email": "bob.patel@example.org", "phone": "", "birthdate": "1970-01-01", "truth": "p3"},
    {"datasource": "crm", "pk": "9", "given_name": "Robert", "surname": "Patel", "email": "bob.patel@example.org", "phone": "", "birthdate": "2001-12-12", "truth": "p4"},
    # singletons
    {"datasource": "crm", "pk": "10", "given_name": "Sara", "surname": "Novak", "email": "sara@example.org", "phone": "", "postal": "02108", "truth": "p5"},
    {"datasource": "web", "pk": "11", "given_name": "Tomas", "surname": "Rossi", "email": "t.rossi@example.org", "phone": "", "postal": "60601", "truth": "p6"},
]


def _run(rows):
    raw = _raw([{k: v for k, v in r.items() if k != "truth"} for r in rows])
    pre = preprocess_records(raw, CFG)
    records = records_from_frame(pre)
    blocks = build_blocks(records, CFG.blocking)
    scores = score_pairs(records, blocks.pairs, CFG.matcher)
    edges = [(r.left_rid, r.right_rid, float(r.score)) for r in scores[scores["is_edge"]].itertuples(index=False)]
    conflict = {rid: {"birthdate": rec.get("birthdate_norm")} for rid, rec in records.items()}
    clusters = cluster_records(sorted(records), edges, conflict, CFG.cluster)
    return records, scores, clusters


def test_precision_recall_bounds():
    records, scores, clusters = _run(LABELLED)
    assignment = pd.DataFrame([{"datasource": rid.split("|")[0], "pk": rid.split("|")[1], "aurora_id": cid} for rid, cid in clusters.assignment.items()])
    labels = pd.DataFrame([{"datasource": r["datasource"], "pk": r["pk"], "truth_id": r["truth"]} for r in LABELLED])
    m = pairwise_metrics(assignment, labels)
    assert m["precision"] > 0.8, m
    assert m["recall"] > 0.8, m
    assert m["false_merge_rate"] == 0.0, m


def test_hard_conflict_prevents_merge():
    records, scores, clusters = _run(LABELLED)
    a = clusters.assignment
    assert a["web|8"] != a["crm|9"], "birthdate hard conflict must keep records apart despite shared email"
    assert a["crm|6"] == a["loyalty|7"], "shared loyalty key is a deterministic merge"
    assert a["crm|1"] == a["web|2"] == a["pos|3"], "nickname + email/phone normalisation links the same person"
    assert a["crm|4"] != a["crm|1"], "Michelle Chen is not Michael Chen"
    row = scores[(scores.left_rid == "crm|9") & (scores.right_rid == "web|8")]
    assert len(row) == 1 and row.iloc[0]["match_category"] == "hard_conflict"


def test_normalisation_rules():
    ncfg = CFG.normalize
    assert canonical_email("Derek+1234@Example.ORG", ncfg) == "derek@example.org"
    assert canonical_email("info@example.org", ncfg) is None  # junk local part
    assert canonical_email("no@example.org", ncfg) is None  # YAML 'no' must stay a string
    assert canonical_phone("(206) 555-0101") == ("+12065550101", "2065550101")
    assert canonical_phone("garbage") == (None, None)
    gm = dict(ncfg)
    gm["email_strip_gmail_dots"] = True
    assert canonical_email("j.o.h.n@gmail.com", gm) == "john@gmail.com"
    assert canonical_email("j.o.h.n@gmail.com", ncfg) == "j.o.h.n@gmail.com"


def test_blocking_cap_skips_oversized_blocks():
    cfg = {"block_size_limit": 3, "fk_block_size_limit": 1000, "strategies": [{"name": "email_exact", "type": "email"}]}
    records = {f"s|{i}": {"datasource": "s", "pk": str(i), "email_norm": "shared@example.org"} for i in range(5)}
    res = build_blocks(records, cfg)
    assert res.pair_count == 0
    assert res.skipped == [("email_exact", "shared@example.org", 5, 3)]
    assert len(res.keys) == 5


def test_stable_ids_greedy_max_overlap_and_jitter():
    previous = {"r1": "A", "r2": "A", "r3": "A", "r4": "B", "r5": "B", "r6": "C"}
    # r3 moved from A to B's cluster; C split into two singletons; new record r7 joins A.
    current = {"r1": "x", "r2": "x", "r7": "x", "r3": "y", "r4": "y", "r5": "y", "r6": "z"}
    res = assign_stable_ids(current, previous, jitter_alert_pct=2.0)
    assert res.cluster_to_id["x"] == "A" and res.cluster_to_id["y"] == "B" and res.cluster_to_id["z"] == "C"
    assert res.minted == set() and res.retired == set()
    j = res.jitter
    assert j.records_compared == 6 and j.records_changed == 1 and j.alert is True
    kinds = {(c["rid"], c["change_type"]) for c in res.pk_changes}
    assert ("r7", "added") in kinds and ("r3", "updated") in kinds
    # a 1->2 split forces exactly one new id; ties broken by ascending ids
    res2 = assign_stable_ids({"r1": "p", "r2": "q"}, {"r1": "A", "r2": "A"})
    assert res2.cluster_to_id["p"] == "A" and res2.cluster_to_id["q"] in res2.minted and len(res2.minted) == 1
