"""AmpID compatibility: external id column in exports/previous input; e-mail -> single customer assignment."""

from __future__ import annotations

import pandas as pd

from aurora_cdp.adapters import resolve_records
from aurora_cdp.config import load_config
from aurora_cdp.profile.ampid import assign_email_ampids
from aurora_cdp.storage.duck import connect, init_schema


def test_external_id_column_and_previous_alias(tmp_path):
    df = pd.DataFrame([{"source_record_id": "1", "given_name": "Ann", "surname": "Lee", "email": "ann@x.org"},
                       {"source_record_id": "2", "given_name": "Ann", "surname": "Lee", "email": "ann@x.org"}])
    r1 = resolve_records(df, datasource="s")
    assert "amperity_id" in r1.assignments.columns and (r1.assignments["amperity_id"] == r1.assignments["unified_id"]).all()
    prev = r1.assignments[["source_record_id", "datasource", "amperity_id"]]
    r2 = resolve_records(df, datasource="s", previous=prev)
    assert set(r2.assignments["unified_id"]) == set(r1.assignments["unified_id"]) and r2.metrics["jitter"]["ids_minted"] == 0
    r3 = resolve_records(df, datasource="s", config={"identity": {"ampid_mode": False}})
    assert "amperity_id" not in r3.assignments.columns


def test_email_ampid_narrows_to_one_customer(tmp_path):
    ws = tmp_path / "ws"
    cfg = load_config(overrides={"workspace": str(ws)}, use_last_best=False)
    # shared household e-mail: Ann (3 records) and Bob (1 record, different given name -> hard conflict keeps them apart)
    rows = [{"source_record_id": f"a{i}", "given_name": "Ann", "surname": "Lee", "email": "family@x.org", "birthdate": "1980-01-01"} for i in range(3)]
    rows.append({"source_record_id": "b1", "given_name": "Robert", "surname": "Lee", "email": "family@x.org", "birthdate": "1975-05-05"})
    r = resolve_records(pd.DataFrame(rows), config=cfg, datasource="s", workspace=ws)
    assert r.metrics["clusters"] == 2
    con = connect(ws / "adapter.duckdb")
    init_schema(con)
    m = assign_email_ampids(con, cfg, r.run_id)
    assert m["emails"] == 1 and m["emails_narrowed"] == 1
    email, aid, cands, rule = con.execute("SELECT email, aurora_id, candidates, rule FROM gold_email_ampid WHERE is_current").fetchone()
    ann = {x.source_record_id: x.unified_id for x in r.assignments.itertuples()}["a0"]
    assert (email, aid, cands, rule) == ("family@x.org", ann, 2, "most_records")
    m2 = assign_email_ampids(con, cfg, r.run_id)  # idempotent
    assert m2["email_ampid_changed"] == 0 and con.execute("SELECT COUNT(*) FROM gold_email_ampid").fetchone()[0] == 1
    con.close()
