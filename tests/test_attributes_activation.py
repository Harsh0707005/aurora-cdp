"""Customer Attributes (behavioural feature store) and per-destination Activation IDs."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from aurora_cdp.audiences.activation import assign_activation_ids, attach_activation_ids
from aurora_cdp.config import load_config
from aurora_cdp.profile.attributes import build_customer_attributes
from aurora_cdp.storage.duck import connect, init_schema

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from wsi_edap_sim import expected_customer  # noqa: E402  (the executable reference definition)

ORDERS = [  # (order_id, brand, channel, store, date, net, gross, items)
    ("O1", "WS", "WEB", None, "2025-01-10", 120.0, 129.9, 2),
    ("O2", "PB", "RETAIL", "PB007", "2025-03-01", 80.0, 86.6, 1),
    ("O3", "WS", "WEB", None, "2026-09-15", 300.0, 324.75, 3),
    ("O4", "WE", "CALL_CENTER", None, "2026-09-25", 50.0, 54.13, 1),
]
EVENTS_CFG = [{"source": "oms", "feed": "orders", "fk_column": "CUSTOMER_ID", "fk_namespace": "oms", "event_type": "order",
               "ts_column": "ORDER_DT", "amount_column": "NET_AMT",
               "attributes": {"order_id": "ORDER_ID", "brand": "CONCEPT_CD", "channel": "SUB_CHANNEL_TYPE_CD", "store": "LOCATION_ID", "total": "GROSS_AMT", "items": "TOTAL_ITEMS"}}]


def _db(tmp_path):
    cfg = load_config(overrides={"workspace": str(tmp_path), "events": EVENTS_CFG}, use_last_best=False)
    con = connect(cfg.db_path)
    init_schema(con)
    con.execute("INSERT INTO id_ledger VALUES ('ID1', 'oms', 'c1', 'r1', ?, NULL, TRUE)", [datetime(2026, 1, 1)])
    for oid, brand, ch, store, d, net, gross, items in ORDERS:
        payload = json.dumps({"ORDER_ID": oid, "CONCEPT_CD": brand, "SUB_CHANNEL_TYPE_CD": ch, "LOCATION_ID": store, "GROSS_AMT": gross, "TOTAL_ITEMS": items})
        con.execute("INSERT INTO gold_profile_events VALUES (?, 'ID1', 'oms', 'fk-oms', 'c1', 'order', ?, ?, ?, 'r1')", [oid, datetime.fromisoformat(d), net, payload])
    return con, cfg


def test_customer_attributes_match_the_reference_definition(tmp_path):
    con, cfg = _db(tmp_path)
    assert build_customer_attributes(con, cfg, run_id="r1", as_of="2026-09-30") == 1
    got = con.execute("SELECT * FROM customer_attributes").df().iloc[0].to_dict()
    ref = expected_customer(None, [{"order_id": o[0], "brand": o[1], "channel": o[2], "store": o[3], "dt": date.fromisoformat(o[4]), "net": o[5], "gross": o[6], "items": o[7], "emp": None, "loy": None} for o in ORDERS], [], customer_id="ID1")
    skip = {"CUSTOMER_ID", "HOUSEHOLD_ID", "FIRST_NAME", "LAST_NAME", "ADDRESS", "ADDRESS2", "CITY", "STATE_CD", "POSTAL_CD", "COUNTRY_CD", "PRIMARY_EMAIL_ID",
            "RECENT_EMAIL_ID", "PRIMARY_PHONE", "RECENT_PHONE", "DOB_DT", "CUSTOMER_PII_PRESENT_FLAG", "CURRENT_EMPLOYEE_FLAG", "LOYALTY_MEMBER_FLAG", "LOYALTY_ACCT_CNT"}
    mism = []
    for k, v in ref.items():
        if k in skip:
            continue
        g = got[k.lower()]
        if isinstance(g, (pd.Timestamp, date)):
            g = g.isoformat()[:10] if not isinstance(g, str) else g
        if v is None or (isinstance(v, float) and pd.isna(v)):
            ok = g is None or (isinstance(g, float) and pd.isna(g))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            ok = g is not None and abs(float(g) - float(v)) < 0.005
        else:
            ok = str(g) == str(v)
        if not ok:
            mism.append((k, v, g))
    assert not mism, mism[:10]
    assert got["lifetime_order_frequency"] == 4 and got["l30d_order_frequency"] == 2 and got["l12m_rfm_customer_segment"] in ("RECENT", "CHAMPION", "LOYAL", "OCCASIONAL")
    cols = {r[1] for r in con.execute("PRAGMA table_info('customer_360')").fetchall()}
    assert {"lifetime_order_net_amt", "l12m_rfm_score", "first_order_brand"} <= cols  # Customer 360 now carries the family
    con.close()


def test_activation_ids_are_stable_and_survive_merges(tmp_path):
    con, _ = _db(tmp_path)
    a = assign_activation_ids(con, "klaviyo", ["A", "B"])
    b = assign_activation_ids(con, "klaviyo", ["B", "A"])
    assert dict(zip(a.aurora_id, a.activation_id)) == dict(zip(b.aurora_id, b.activation_id))
    other = assign_activation_ids(con, "meta", ["A"])
    assert other.activation_id.iloc[0] != a.set_index("aurora_id").activation_id["A"]   # separate namespace per destination
    # A's cluster merges into C (the change feed records C with aurora_id_prev = A): C inherits A's activation id
    con.execute("INSERT INTO unified_changes_clusters VALUES ('r2', 'C', 'A', 'updated', 5, 3, ?)", [datetime(2026, 2, 1)])
    c = assign_activation_ids(con, "klaviyo", ["C"])
    assert c.activation_id.iloc[0] == a.set_index("aurora_id").activation_id["A"]
    assert con.execute("SELECT inherited_from FROM activation_ids WHERE destination_id = 'klaviyo' AND aurora_id = 'C'").fetchone()[0] == "A"
    members = pd.DataFrame({"aurora_id": ["A", "C", "Z"], "email": ["a@x", "c@x", "z@x"]})
    out = attach_activation_ids(con, "klaviyo", members)
    assert out.activation_id.notna().all() and out.loc[out.aurora_id == "A", "activation_id"].iloc[0] == out.loc[out.aurora_id == "C", "activation_id"].iloc[0]
    con.close()
