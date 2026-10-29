"""Run Aurora on EDAP-shaped feeds (tools/wsi_edap_sim.py) and score the result against the truth.

Pipeline (what EDAP -> Amperity -> EDAP would do):
  ORDER_HEADER bill-to, ORDER_LINE ship-to (one record per order x ship-to address), RETAIL_STORE_ESTIMATE_HEADER
  -> identity records -> aurora_cdp.adapters.resolve_records -> households -> CUSTOMER rows (survivorship + purchase
  aggregates exactly as tools/wsi_edap_sim.expected_customer computes them from the truth) -> metrics + report.

Usage: python tools/wsi_edap_eval.py --data ~/Documents/aanya/datasets/wsi-edap-sim/p60k --run-name wsi-edap-p60k
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wsi_edap_sim import expected_customer  # noqa: E402

from aurora_cdp.adapters import resolve_records  # noqa: E402

ID_COLS = ["source_record_id", "datasource", "given_name", "surname", "email", "phone", "address", "address2", "city", "state", "postal",
           "country", "loy_id", "update_dt", "fk_oms", "fk_clienteling"]


def identity_records(oh: pd.DataFrame, ol: pd.DataFrame, est: pd.DataFrame) -> pd.DataFrame:
    bill = pd.DataFrame({
        "source_record_id": oh["ORDER_HEADER_ID"], "datasource": oh["SOURCE_SYSTEM"] + "_BILLTO",
        "given_name": oh["BILL_TO_FIRST_NAME"], "surname": oh["BILL_TO_LAST_NAME"], "email": oh["BILL_TO_EMAIL_ADDRESS"],
        "phone": oh["BILL_TO_PHONE_NBR"], "address": oh["BILL_TO_ADDRESS_LINE_1"], "address2": oh["BILL_TO_ADDRESS_LINE_2"],
        "city": oh["BILL_TO_CITY"], "state": oh["BILL_TO_STATE_OR_PROV_CD"], "postal": oh["BILL_TO_POSTAL_CD"], "country": oh["BILL_TO_COUNTRY"],
        "loy_id": oh["LOYALTY_ACCOUNT_ID"], "update_dt": pd.to_datetime(oh["ORDER_DT"]), "fk_oms": oh["CUSTOMER_ID"], "fk_clienteling": None,
    })
    s = ol[ol["SHIP_TO_ADDRESS_LINE_1"].fillna("").str.strip() != ""].copy()
    s["_k"] = s["SHIP_TO_ADDRESS_LINE_1"].str.lower()
    s = s.sort_values("ORDER_LINE_ID").drop_duplicates(["ORDER_HEADER_KEY", "_k"], keep="first")
    ship = pd.DataFrame({
        "source_record_id": s["ORDER_LINE_ID"], "datasource": s["SOURCE_SYSTEM"] + "_SHIPTO",
        "given_name": s["SHIP_TO_FIRST_NAME"], "surname": s["SHIP_TO_LAST_NAME"], "email": s["SHIP_TO_EMAIL_ADDRESS"], "phone": s["SHIP_TO_PHONE_NBR"],
        "address": s["SHIP_TO_ADDRESS_LINE_1"], "address2": s["SHIP_TO_ADDRESS_LINE_2"], "city": s["SHIP_TO_CITY"], "state": s["SHIP_TO_STATE_OR_PROV"],
        "postal": s["SHIP_TO_POSTAL_CD"], "country": s["SHIP_TO_COUNTRY"], "loy_id": None, "update_dt": pd.to_datetime(s["ORDER_DT"]),
        "fk_oms": s["SHIP_TO_CUSTOMER_ID"], "fk_clienteling": None,
    })
    e = pd.DataFrame({
        "source_record_id": est["RETAIL_STORE_ESTIMATE_HEADER_ID"], "datasource": "CLIENTELING",
        "given_name": est["CUSTOMER_FIRST_NAME"], "surname": est["CUSTOMER_LAST_NAME"], "email": est["CUSTOMER_EMAIL_ID"], "phone": est["CUSTOMER_DAY_PHONE_NBR"],
        "address": est["CUSTOMER_ADDRESSLINE"], "address2": None, "city": est["CUSTOMER_CITY"], "state": est["CUSTOMER_STATE_CD"], "postal": est["CUSTOMER_POSTAL_CD"],
        "country": est["CUSTOMER_COUNTRY_CD"], "loy_id": None, "update_dt": pd.to_datetime(est["ORDER_DT"]), "fk_oms": None, "fk_clienteling": est["CUSTOMER_CLIENTELING_ID"],
    }) if len(est) else pd.DataFrame(columns=ID_COLS)
    df = pd.concat([bill, ship, e], ignore_index=True)[ID_COLS]
    for c in ID_COLS:
        if c not in ("update_dt",):
            df[c] = df[c].where(df[c].notna(), None)
            df[c] = df[c].map(lambda v: None if (v is None or str(v).strip() == "") else str(v))
    return df


def build_customer_rows(assign: pd.DataFrame, oh: pd.DataFrame, est: pd.DataFrame, households: dict[str, str]) -> pd.DataFrame:
    """CUSTOMER rows per unified_id from the orders whose bill-to record sits in the cluster (+ estimate PII)."""
    a = assign.set_index(assign["datasource"] + "|" + assign["pk"])["unified_id"]
    oh = oh.astype(object).where(oh.notna(), None)   # NaN -> None so blanks are falsy like in the generator
    est = est.astype(object).where(est.notna(), None)
    orders_by: dict[str, list[dict]] = defaultdict(list)
    obs_by: dict[str, list[dict]] = defaultdict(list)
    ohr = oh.to_dict("records")
    for r in ohr:
        uid = a.get(f"{r['SOURCE_SYSTEM']}_BILLTO|{r['ORDER_HEADER_ID']}")
        if uid is None:
            continue
        od = r["ORDER_DT"] if isinstance(r["ORDER_DT"], date) else pd.Timestamp(r["ORDER_DT"]).date()
        orders_by[uid].append({"order_id": r["ORDER_ID"], "brand": r["CONCEPT_CD"], "channel": r["SUB_CHANNEL_TYPE_CD"], "store": r["LOCATION_ID"],
                               "dt": od, "net": float(r["NET_AMT"]), "gross": float(r["GROSS_AMT"]), "items": None, "emp": r["EMPLOYEE_ID"], "loy": r["LOYALTY_ACCOUNT_ID"]})
        obs_by[uid].append({"dt": od, "first": r["BILL_TO_FIRST_NAME"], "last": r["BILL_TO_LAST_NAME"], "email": r["BILL_TO_EMAIL_ADDRESS"], "phone": r["BILL_TO_PHONE_NBR"],
                            "l1": r["BILL_TO_ADDRESS_LINE_1"], "l2": r["BILL_TO_ADDRESS_LINE_2"], "city": r["BILL_TO_CITY"], "state": r["BILL_TO_STATE_OR_PROV_CD"], "postal": r["BILL_TO_POSTAL_CD"]})
    for r in est.to_dict("records"):
        uid = a.get(f"CLIENTELING|{r['RETAIL_STORE_ESTIMATE_HEADER_ID']}")
        if uid is None:
            continue
        od = r["ORDER_DT"] if isinstance(r["ORDER_DT"], date) else pd.Timestamp(r["ORDER_DT"]).date()
        l1 = r["CUSTOMER_ADDRESSLINE"] or ""
        obs_by[uid].append({"dt": od, "first": r["CUSTOMER_FIRST_NAME"], "last": r["CUSTOMER_LAST_NAME"], "email": r["CUSTOMER_EMAIL_ID"], "phone": r["CUSTOMER_DAY_PHONE_NBR"],
                            "l1": l1, "l2": "", "city": r["CUSTOMER_CITY"], "state": r["CUSTOMER_STATE_CD"], "postal": r["CUSTOMER_POSTAL_CD"]})
    return orders_by, obs_by


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--reports-root", default=str(Path(__file__).resolve().parent.parent / "reports"))
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--cdp-config", default=None, help="JSON overrides for the engine config")
    a = ap.parse_args()
    data = Path(a.data).expanduser()
    out = Path(a.reports_root) / a.date / a.run_name
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    def _read(name: str) -> pd.DataFrame:  # single file (small corpora) or a directory of parts (batched corpora)
        f, d = data / f"{name}.parquet", data / name
        return pd.read_parquet(f) if f.exists() else pd.read_parquet(d)
    oh, ol, est = _read("ORDER_HEADER"), _read("ORDER_LINE"), _read("RETAIL_STORE_ESTIMATE_HEADER")
    truth, expected, persons = _read("truth_records"), _read("expected_CUSTOMER"), _read("truth_persons")
    manifest = json.loads((data / "manifest.json").read_text())

    # items per order for the aggregates (ORDER_LINE)
    items = ol.groupby("ORDER_HEADER_KEY")["ORDER_QTY"].sum().to_dict()

    recs = identity_records(oh, ol, est)
    t1 = time.perf_counter()
    ws = out / "workspace"
    cfg = json.loads(a.cdp_config) if a.cdp_config else None
    res = resolve_records(recs, config=cfg, workspace=ws)
    t2 = time.perf_counter()
    assign = res.assignments[["datasource", "pk", "unified_id"]].copy()

    # households through the engine's own module on the kept workspace
    hh_map: dict[str, str] = {}
    hh_metrics = {}
    try:
        from aurora_cdp.config import load_config
        from aurora_cdp.profile.households import build_households
        from aurora_cdp.storage.duck import connect
        con = connect(ws / "adapter.duckdb")
        hres = build_households(con, load_config(overrides=cfg or {}, use_last_best=False), stitch_run_id=res.run_id)
        hh_metrics = hres.metrics
        hh_map = dict(con.execute("SELECT aurora_id, household_id FROM household_members WHERE is_current").fetchall())
        con.close()
    except Exception as e:  # noqa: BLE001
        hh_metrics = {"error": repr(e)[:300]}
    t3 = time.perf_counter()

    # ---------------- identity metrics
    con = duckdb.connect()
    con.register("assign", assign)
    con.register("truth", truth)
    con.register("ol", ol[["ORDER_LINE_ID", "ORDER_HEADER_KEY"]])
    con.register("oh", oh[["ORDER_HEADER_KEY", "ORDER_HEADER_ID"]])
    con.register("persons", persons)
    con.execute("CREATE TABLE a AS SELECT t.record_id, t.role, t.person_id, t.has_pii, s.unified_id FROM truth t JOIN assign s ON s.pk = t.record_id")
    con.execute("CREATE TABLE link AS SELECT * FROM a WHERE NOT (person_id LIKE 'anon:%' OR person_id LIKE 'stranger:%')")
    n_link = con.execute("SELECT COUNT(*) FROM link").fetchone()[0]
    tp = con.execute("SELECT COUNT(*) FROM link x JOIN link y ON x.person_id=y.person_id AND x.record_id<y.record_id AND x.unified_id=y.unified_id").fetchone()[0]
    fn = con.execute("SELECT COUNT(*) FROM link x JOIN link y ON x.person_id=y.person_id AND x.record_id<y.record_id AND x.unified_id<>y.unified_id").fetchone()[0]
    fp = con.execute("SELECT COUNT(*) FROM a x JOIN a y ON x.unified_id=y.unified_id AND x.record_id<y.record_id AND x.person_id<>y.person_id").fetchone()[0]
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F1 = 2 * P * R / (P + R) if P + R else 0.0
    b3 = con.execute("""
        WITH c AS (SELECT unified_id, person_id, COUNT(*) n FROM a GROUP BY 1,2),
             cs AS (SELECT unified_id, COUNT(*) cn FROM a GROUP BY 1), ps AS (SELECT person_id, COUNT(*) pn FROM a GROUP BY 1)
        SELECT AVG(c.n * c.n / (cs.cn * 1.0) / c.n), AVG(c.n * c.n / (ps.pn * 1.0) / c.n)
        FROM a JOIN c USING (unified_id, person_id) JOIN cs USING (unified_id) JOIN ps USING (person_id)""").fetchone()
    b3p, b3r = float(b3[0]), float(b3[1])
    b3f = 2 * b3p * b3r / (b3p + b3r) if b3p + b3r else 0.0
    clusters = con.execute("SELECT COUNT(DISTINCT unified_id) FROM a").fetchone()[0]
    fm_clusters = con.execute("SELECT COUNT(*) FROM (SELECT unified_id FROM a GROUP BY 1 HAVING COUNT(DISTINCT person_id) > 1)").fetchone()[0]
    split_persons = con.execute("SELECT COUNT(*) FROM (SELECT person_id FROM link GROUP BY 1 HAVING COUNT(DISTINCT unified_id) > 1)").fetchone()[0]
    persons_link = con.execute("SELECT COUNT(DISTINCT person_id) FROM link").fetchone()[0]
    role_recall = con.execute("""
        SELECT x.role || ' <-> ' || y.role AS pair_kind, COUNT(*) n, ROUND(AVG(CASE WHEN x.unified_id=y.unified_id THEN 1 ELSE 0 END),4) recall
        FROM link x JOIN link y ON x.person_id=y.person_id AND x.record_id<y.record_id AND x.role<=y.role GROUP BY 1 ORDER BY n DESC""").fetchall()
    # gift contamination via order key join
    gift_contam = con.execute("""
        SELECT COUNT(*) total, COALESCE(SUM(CASE WHEN b.unified_id = g.unified_id THEN 1 ELSE 0 END),0) merged_into_buyer
        FROM a g JOIN ol ON ol.ORDER_LINE_ID = g.record_id JOIN oh USING (ORDER_HEADER_KEY) JOIN a b ON b.record_id = oh.ORDER_HEADER_ID
        WHERE g.role = 'ship_to_gift'""").fetchone()
    fm_examples = con.execute("""
        SELECT x.record_id, y.record_id, x.person_id, y.person_id FROM a x JOIN a y ON x.unified_id=y.unified_id AND x.record_id<y.record_id AND x.person_id<>y.person_id
        WHERE NOT x.person_id LIKE 'anon:%' AND NOT y.person_id LIKE 'anon:%' LIMIT 8""").fetchall()

    # ---------------- CUSTOMER rows from Aurora clusters, compared with the expected rows
    orders_by, obs_by = build_customer_rows(assign, oh, est, hh_map)
    key_by_oid = {r["ORDER_ID"]: r["ORDER_HEADER_KEY"] for r in oh[["ORDER_ID", "ORDER_HEADER_KEY"]].to_dict("records")}
    rows = []
    for uid, orders in orders_by.items():
        for o in orders:
            o["items"] = int(items.get(key_by_oid[o["order_id"]], 0))
        rows.append(expected_customer(None, orders, obs_by.get(uid, []), customer_id=uid, household_id=hh_map.get(uid)))
    customer = pd.DataFrame(rows)
    customer.to_parquet(out / "CUSTOMER_aurora.parquet", index=False)
    # map truth person -> cluster holding the majority of its bill-to records
    maj = con.execute("""
        SELECT person_id, unified_id FROM (
          SELECT person_id, unified_id, COUNT(*) n, ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY COUNT(*) DESC, unified_id) rn
          FROM link WHERE role='bill_to' GROUP BY 1,2) WHERE rn=1""").df()
    got = customer.rename(columns={"CUSTOMER_ID": "unified_id"})
    cmp = expected.merge(maj, left_on="CUSTOMER_ID", right_on="person_id", how="left").merge(got, on="unified_id", how="left", suffixes=("_exp", "_got"))
    attr_cols = [c for c in expected.columns if c not in ("CUSTOMER_ID", "HOUSEHOLD_ID", "DOB_DT", "CUSTOMER_PII_PRESENT_FLAG")]
    def eq(x, y):
        if (x is None or (isinstance(x, float) and pd.isna(x))) and (y is None or (isinstance(y, float) and pd.isna(y))):
            return True
        if isinstance(x, float) or isinstance(y, float):
            try:
                return abs(float(x) - float(y)) < 0.005
            except (TypeError, ValueError):
                return False
        return str(x) == str(y)
    attr_acc = {}
    all_ok = pd.Series(True, index=cmp.index)
    for c in attr_cols:
        x, y = cmp[f"{c}_exp"], cmp[f"{c}_got"]
        both_na = x.isna() & y.isna()
        if pd.api.types.is_numeric_dtype(x) or pd.api.types.is_numeric_dtype(y):
            ok = both_na | ((pd.to_numeric(x, errors="coerce") - pd.to_numeric(y, errors="coerce")).abs() < 0.005)
        else:
            ok = both_na | (x.astype(str) == y.astype(str))
        attr_acc[c] = round(float(ok.mean()), 4)
        all_ok &= ok
    all_match = round(float(all_ok.mean()), 4)
    net_err = (cmp["LIFETIME_ORDER_NET_AMT_got"].fillna(0) - cmp["LIFETIME_ORDER_NET_AMT_exp"]).abs()
    # household pair metrics over truth persons (via majority cluster)
    hh_stats = {}
    if hh_map:
        con.register("maj", maj)
        con.register("hhm", pd.DataFrame({"unified_id": list(hh_map), "household_id": list(hh_map.values())}))
        con.execute("CREATE TABLE ph AS SELECT p.person_id, p.household_id AS hh_true, hhm.household_id AS hh_got FROM persons p JOIN maj USING (person_id) LEFT JOIN hhm USING (unified_id)")
        htp = con.execute("SELECT COUNT(*) FROM ph x JOIN ph y ON x.person_id<y.person_id AND x.hh_true=y.hh_true AND x.hh_got IS NOT NULL AND x.hh_got=y.hh_got").fetchone()[0]
        hfn = con.execute("SELECT COUNT(*) FROM ph x JOIN ph y ON x.person_id<y.person_id AND x.hh_true=y.hh_true AND (x.hh_got IS NULL OR y.hh_got IS NULL OR x.hh_got<>y.hh_got)").fetchone()[0]
        hfp = con.execute("SELECT COUNT(*) FROM ph x JOIN ph y ON x.person_id<y.person_id AND x.hh_true<>y.hh_true AND x.hh_got IS NOT NULL AND x.hh_got=y.hh_got").fetchone()[0]
        hh_stats = {"pair_precision": round(htp / (htp + hfp), 4) if htp + hfp else None, "pair_recall": round(htp / (htp + hfn), 4) if htp + hfn else None,
                    "true_pairs": htp + hfn, "households_output": len(set(hh_map.values())), "engine_metrics": hh_metrics}
    t4 = time.perf_counter()

    result = {
        "run_name": a.run_name, "data": str(data), "manifest": manifest, "engine_run_id": res.run_id,
        "records": int(len(recs)), "clusters_total": int(clusters), "customers_output": int(len(customer)), "persons_with_orders_truth": int(len(expected)),
        "identity": {"pairwise_precision": round(P, 4), "pairwise_recall": round(R, 4), "pairwise_f1": round(F1, 4), "tp": tp, "fp": fp, "fn": fn,
                     "b3_precision": round(b3p, 4), "b3_recall": round(b3r, 4), "b3_f1": round(b3f, 4),
                     "false_merge_clusters": int(fm_clusters), "false_merge_cluster_rate": round(fm_clusters / clusters, 4),
                     "split_persons": int(split_persons), "split_person_rate": round(split_persons / persons_link, 4), "linkable_records": int(n_link),
                     "recall_by_pair_kind": [{"kind": k, "pairs": n, "recall": r} for k, n, r in role_recall],
                     "gift_ship_to_records": int(gift_contam[0]), "gift_ship_to_merged_into_buyer": int(gift_contam[1]),
                     "false_merge_examples": fm_examples},
        "customer_table": {"rows_compared": int(len(cmp)), "all_attributes_exact": all_match, "attribute_accuracy": attr_acc,
                           "lifetime_net_abs_error_total": round(float(net_err.sum()), 2), "lifetime_net_exact_share": round(float((net_err < 0.005).mean()), 4)},
        "households": hh_stats,
        "timing_s": {"prepare": round(t1 - t0, 1), "resolve": round(t2 - t1, 1), "households": round(t3 - t2, 1), "evaluate": round(t4 - t3, 1)},
        "engine_metrics": {k: v for k, v in res.metrics.items() if k in ("records", "pairs_blocked", "pairs_scored", "edges", "clusters", "timings_sec", "peak_rss_mb", "jitter")},
    }
    (out / "metrics.json").write_text(json.dumps(result, indent=1, default=str))
    # markdown
    idm = result["identity"]
    md = [f"# WSI EDAP-shaped simulation — `{a.run_name}`", "",
          f"_{a.date} · generator seed {manifest['seed']} · {manifest['persons']:,} persons · {manifest['orders']:,} orders · {len(recs):,} identity records · engine run `{res.run_id}`_", "",
          "## Identity (records -> persons)", "", "| metric | value |", "|---|---|",
          f"| pairwise precision / recall / F1 | {idm['pairwise_precision']} / {idm['pairwise_recall']} / {idm['pairwise_f1']} |",
          f"| B³ precision / recall / F1 | {idm['b3_precision']} / {idm['b3_recall']} / {idm['b3_f1']} |",
          f"| clusters output / persons with orders | {clusters:,} / {len(expected):,} |",
          f"| false-merge clusters (mixed persons) | {fm_clusters:,} ({idm['false_merge_cluster_rate']:.2%}) |",
          f"| split persons | {split_persons:,} ({idm['split_person_rate']:.2%}) |",
          f"| gift ship-to records merged into the buyer | {gift_contam[1]:,} of {gift_contam[0]:,} |", "",
          "Recall by record roles of the pair:", "", "| pair | pairs | recall |", "|---|---|---|"]
    md += [f"| {k} | {n:,} | {r} |" for k, n, r in role_recall]
    ct = result["customer_table"]
    md += ["", "## CUSTOMER table (Amperity -> EDAP shape) vs expected", "",
           f"Rows: {len(customer):,} output vs {len(expected):,} expected. All attributes exact for **{ct['all_attributes_exact']:.1%}** of customers; "
           f"lifetime net amount exact for {ct['lifetime_net_exact_share']:.1%} (total absolute error ${ct['lifetime_net_abs_error_total']:,.0f}).", "",
           "| attribute | exact-match share |", "|---|---|"]
    md += [f"| {c} | {v:.4f} |" for c, v in sorted(attr_acc.items(), key=lambda kv: kv[1])]
    if hh_stats:
        md += ["", "## Households", "", f"Pair precision {hh_stats['pair_precision']} / recall {hh_stats['pair_recall']} over {hh_stats['true_pairs']:,} true co-household pairs; {hh_stats['households_output']:,} households output."]
    md += ["", "## Timing", "", f"prepare {result['timing_s']['prepare']} s · resolve {result['timing_s']['resolve']} s · households {result['timing_s']['households']} s · evaluate {result['timing_s']['evaluate']} s"]
    (out / "report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:20]))
    print("->", out / "report.md")


if __name__ == "__main__":
    main()
