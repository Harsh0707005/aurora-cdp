"""Households: evidence edges, persistent ids across a move (TTL), skipped hot values, relationships."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from aurora_cdp.adapters import resolve_records
from aurora_cdp.config import load_config
from aurora_cdp.profile.households import add_relationship, build_households, household_of
from aurora_cdp.storage.duck import connect, init_schema


def _people(move: bool = False):
    addr_a = "12 Main St" if not move else "99 Elm Rd"
    rows = [
        {"source_record_id": "ann", "given_name": "Ann", "surname": "Lee", "email": "ann@x.org", "address": addr_a, "postal": "98101"},
        {"source_record_id": "bob", "given_name": "Bob", "surname": "Lee", "email": "bob@x.org", "address": "12 Main St", "postal": "98101"},
        {"source_record_id": "cat", "given_name": "Cat", "surname": "Ng", "email": "cat@x.org", "address": "7 Oak Ave", "postal": "02134"},
        {"source_record_id": "dan", "given_name": "Dan", "surname": "Ng", "email": "dan@x.org", "address": "8 Oak Ave", "postal": "02134"},
    ]
    return pd.DataFrame(rows)


def test_households_persist_across_a_move(tmp_path):
    ws = tmp_path / "ws"
    cfg = load_config(overrides={"workspace": str(ws)}, use_last_best=False)
    r1 = resolve_records(_people(), config=cfg, datasource="s", workspace=ws)
    con = connect(ws / "adapter.duckdb")
    init_schema(con)
    h1 = build_households(con, cfg, r1.run_id)
    ids = dict(con.execute("SELECT aurora_id, household_id FROM household_members WHERE is_current").fetchall())
    a = {r.source_record_id: r.unified_id for r in r1.assignments.itertuples()}
    assert ids[a["ann"]] == ids[a["bob"]], "shared address -> one household"
    assert ids[a["cat"]] != ids[a["dan"]], "same surname + postal alone (0.4) is below min_evidence_weight"
    assert h1.metrics["multi_member_households"] == 1 and h1.metrics["evidence_new"] >= 2
    hh_ann = ids[a["ann"]]
    con.close()
    # Ann moves: no shared address any more, but the evidence is still within its TTL -> household persists
    r2 = resolve_records(_people(move=True), config=cfg, datasource="s", workspace=ws, previous=r1.assignments)
    con = connect(ws / "adapter.duckdb")
    h2 = build_households(con, cfg, r2.run_id)
    ids2 = dict(con.execute("SELECT aurora_id, household_id FROM household_members WHERE is_current").fetchall())
    a2 = {r.source_record_id: r.unified_id for r in r2.assignments.itertuples()}
    assert ids2[a2["ann"]] == ids2[a2["bob"]] == hh_ann and h2.metrics["jitter"]["records_changed"] == 0
    # age the evidence beyond the TTL -> the next build splits the household, keeping Bob's id stable by overlap
    con.execute("UPDATE household_evidence SET last_seen = ?", [datetime.utcnow() - timedelta(days=400)])
    h3 = build_households(con, cfg, r2.run_id)
    ids3 = dict(con.execute("SELECT aurora_id, household_id FROM household_members WHERE is_current").fetchall())
    assert ids3[a2["ann"]] != ids3[a2["bob"]] and h3.metrics["evidence_expired"] >= 1
    assert hh_ann in {ids3[a2["ann"]], ids3[a2["bob"]]}
    # explicit relationship re-joins them with full weight
    add_relationship(con, ("s", "ann"), ("s", "bob"), "registry", "wedding-registry")
    build_households(con, cfg, r2.run_id)
    ids4 = dict(con.execute("SELECT aurora_id, household_id FROM household_members WHERE is_current").fetchall())
    assert ids4[a2["ann"]] == ids4[a2["bob"]]
    h = household_of(con, a2["ann"])
    assert h and set(h["members"]) == {a2["ann"], a2["bob"]} and any(e["kind"] == "relationship" for e in h["evidence"])
    con.close()


def test_hot_values_are_not_evidence(tmp_path):
    ws = tmp_path / "ws"
    cfg = load_config(overrides={"workspace": str(ws), "household": {"max_customers_per_value": 3}}, use_last_best=False)
    rows = [{"source_record_id": f"p{i}", "given_name": f"N{i}", "surname": f"S{i}", "email": f"p{i}@x.org", "address": "1 Tower Plaza", "postal": "10001"} for i in range(6)]
    r = resolve_records(pd.DataFrame(rows), config=cfg, datasource="s", workspace=ws)
    con = connect(ws / "adapter.duckdb")
    init_schema(con)
    h = build_households(con, cfg, r.run_id)
    assert h.metrics["households"] == 6 and h.metrics["evidence_skipped_values"]["shared_address"] == 1
    con.close()
