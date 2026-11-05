"""Diagnostic chain (dupe-group / component / tier ids), Unified Scores with transitive pairs, QA views, blocklist table."""

from __future__ import annotations

import duckdb
import pandas as pd

from aurora_cdp.adapters import resolve_records
from aurora_cdp.cli import QA_VIEWS

RECS = [
    {"source_record_id": "A", "datasource": "web", "given_name": "Amy", "surname": "Chen", "email": "amy@x.org", "postal": "11111"},
    {"source_record_id": "B", "datasource": "crm", "given_name": "Amy", "surname": "Chen", "email": "amy@x.org", "loy_id": "L1", "postal": "22222"},
    {"source_record_id": "C", "datasource": "pos", "loy_id": "L1"},                      # links to B through the loyalty id only
    {"source_record_id": "D", "datasource": "web", "given_name": "Amy", "surname": "Chen", "email": "amy@x.org", "postal": "11111"},  # identical to A
    {"source_record_id": "Z", "datasource": "web", "given_name": "Zed", "surname": "Zulu", "email": "zed@x.org"},
]


def _run(tmp_path, config=None):
    res = resolve_records(pd.DataFrame(RECS), config=config, workspace=tmp_path / "ws")
    con = duckdb.connect(str(tmp_path / "ws" / "adapter.duckdb"), read_only=True)
    return res, con


def test_diagnostic_ids_and_tiers(tmp_path):
    res, con = _run(tmp_path)
    ids = {r.pk: r.unified_id for r in res.assignments.itertuples()}
    assert ids["A"] == ids["B"] == ids["C"] == ids["D"] != ids["Z"]
    rows = con.execute("SELECT pk, cluster_id, dupe_group_id, hier_cluster_id FROM stitch_clusters WHERE run_id = ? ORDER BY pk", [res.run_id]).fetchall()
    by = {r[0]: r for r in rows}
    assert by["A"][2] is not None and by["A"][2] == by["D"][2]          # trivial dupes share a dupe-group id
    assert by["B"][2] is None and by["Z"][2] is None
    for pk, cid, _, hier in rows:                                        # hierarchical id = cluster id + one segment per stronger tier
        assert hier.startswith(cid + ".") and hier.count(".") == 2
    tiers = con.execute("SELECT pk, tier, min_score, tier_cluster_id FROM stitch_cluster_tiers WHERE run_id = ?", [res.run_id]).df()
    assert sorted(tiers["min_score"].unique().tolist()) == [3.25, 4.0, 4.75]
    piv = tiers.pivot(index="pk", columns="tier", values="tier_cluster_id")
    for t in (2, 3):  # nested: same id at a stronger tier => same id at the weaker tier
        g = piv.groupby(t)[t - 1].nunique()
        assert (g == 1).all()
    assert piv.loc["A", 1] == piv.loc["C", 1]           # one final cluster at the threshold tier
    assert piv.loc["A", 3] != piv.loc["C", 3]           # A–C are only transitively linked: they separate at the strongest tier
    assert piv.loc["B", 3] == piv.loc["C", 3]           # loyalty edge (5.0) survives every tier


def test_unified_scores_carry_transitive_pairs_with_the_weakest_link(tmp_path):
    res, con = _run(tmp_path)
    us = con.execute("SELECT left_pk, right_pk, score, match_type FROM unified_scores WHERE run_id = ? ORDER BY 1, 2", [res.run_id]).df()
    pairs = {(a, b): (s, t) for a, b, s, t in us.itertuples(index=False)}
    assert len(pairs) == 6                                                # 4-member cluster -> 6 member pairs; Z is a singleton
    direct = {k: v for k, v in pairs.items() if v[1] != "scored_transitive"}
    trans = {k: v for k, v in pairs.items() if v[1] == "scored_transitive"}
    assert trans and all(abs(v[0] - min(d[0] for d in direct.values())) < 1e-9 for v in trans.values())
    assert ("A", "C") in trans or ("C", "A") in trans


def test_qa_views_are_queryable_and_consistent(tmp_path):
    res, con = _run(tmp_path)
    for v in QA_VIEWS:
        con.execute(f"SELECT * FROM {v} LIMIT 5").fetchall()
    dist = dict(con.execute("SELECT size_bucket, clusters FROM qa_cluster_size_distribution").fetchall())
    assert dist == {"1": 1, "3-5": 1}
    weakest = con.execute("SELECT aurora_id, weakest_score FROM qa_weakest_match").fetchall()
    assert len(weakest) == 1 and weakest[0][1] <= 5.0
    assert con.execute("SELECT COUNT(*) FROM qa_dedupe_keys_per_id").fetchone()[0] == 1   # A and D: two web records in one id


def test_manual_blocklist_table_is_applied_on_the_next_run(tmp_path):
    res, con = _run(tmp_path)
    con.close()
    w = duckdb.connect(str(tmp_path / "ws" / "adapter.duckdb"))
    w.execute("INSERT INTO blocklist_values_manual VALUES ('email', 'AMY@x.org', now(), 'test', 'shared mailbox')")
    w.close()
    res2 = resolve_records(pd.DataFrame(RECS), workspace=tmp_path / "ws")
    ids = {r.pk: r.unified_id for r in res2.assignments.itertuples()}
    assert ids["A"] != ids["B"]                                          # e-mail no longer evidence; B/C still joined by loyalty
    assert ids["B"] == ids["C"]
    assert ids["A"] != ids["D"]  # A and D agree only on name + postal now: no identifier -> no dupe group, and below threshold
    con = duckdb.connect(str(tmp_path / "ws" / "adapter.duckdb"), read_only=True)
    fl = con.execute("SELECT semantic, value, reason, distinct_count FROM stitch_blocklist_values WHERE run_id = ? AND reason = 'manual'", [res2.run_id]).fetchall()
    assert any(v == "amy@x.org" and n == 3 for _, v, _, n in fl)
