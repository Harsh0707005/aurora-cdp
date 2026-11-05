"""Measure whether incremental Stitch reproduces the full batch clustering (internals §2.12: "preserve the same
correctness as the batch" is an engineering aspiration in Amperity's talk, not a documented guarantee).

Two workspaces replay the same windowed corpus: A runs a *full* Stitch after every window; B runs a full Stitch on
window 0 and an *incremental* Stitch (changed-record pairs + carried cluster edges) on every later window. After
each window the two partitions are compared: pairwise agreement (precision / recall of B's same-cluster pairs
against A's), the share of records whose cluster membership (as a set) is identical, and ARI-style counts.

    python tools/incremental_equivalence.py --profiles ~/Documents/aanya/datasets/aurora-testdata/small/profiles.parquet \
        --window-days 30 [--windows 6] --out reports/<date>/incremental-equivalence
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

import duckdb
import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.ingestion.landing import ingest_frame
from aurora_cdp.orchestration.pipeline import tag_feed
from aurora_cdp.stitch.run import run_stitch
from aurora_cdp.storage.duck import connect, init_schema

SEM = {"pk": "profile_id", "fields": {"first_name": "given_name", "last_name": "surname", "email": "email", "phone": "phone", "dob": "birthdate",
                                       "address": "address", "city": "city", "postal_code": "postal", "created_at": "update_dt"}}


def partition(con, run_id: str) -> pd.DataFrame:
    return con.execute("SELECT pk, aurora_id FROM stitch_clusters WHERE run_id = ?", [run_id]).df()


def compare(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    con = duckdb.connect()
    con.register("a", a); con.register("b", b)
    n = con.execute("SELECT COUNT(*) FROM a JOIN b USING (pk)").fetchone()[0]
    pa = con.execute("SELECT COUNT(*) FROM a x JOIN a y ON x.aurora_id = y.aurora_id AND x.pk < y.pk").fetchone()[0]
    pb = con.execute("SELECT COUNT(*) FROM b x JOIN b y ON x.aurora_id = y.aurora_id AND x.pk < y.pk").fetchone()[0]
    both = con.execute("""SELECT COUNT(*) FROM a x JOIN a y ON x.aurora_id = y.aurora_id AND x.pk < y.pk
                          JOIN b bx ON bx.pk = x.pk JOIN b bb ON bb.pk = y.pk WHERE bx.aurora_id = bb.aurora_id""").fetchone()[0]
    same_membership = con.execute("""
        WITH ca AS (SELECT pk, string_agg(pk2, ',' ORDER BY pk2) AS members FROM (SELECT x.pk, y.pk AS pk2 FROM a x JOIN a y USING (aurora_id)) GROUP BY pk),
             cb AS (SELECT pk, string_agg(pk2, ',' ORDER BY pk2) AS members FROM (SELECT x.pk, y.pk AS pk2 FROM b x JOIN b y USING (aurora_id)) GROUP BY pk)
        SELECT COUNT(*) FROM ca JOIN cb USING (pk) WHERE ca.members = cb.members""").fetchone()[0]
    prec = both / pb if pb else 1.0
    rec = both / pa if pa else 1.0
    return {"records": int(n), "pairs_full": int(pa), "pairs_incremental": int(pb), "pairs_both": int(both),
            "pair_precision_vs_full": round(prec, 5), "pair_recall_vs_full": round(rec, 5),
            "pair_f1_vs_full": round(2 * prec * rec / (prec + rec), 5) if prec + rec else 0.0,
            "records_same_membership": int(same_membership), "records_same_membership_share": round(same_membership / n, 5) if n else 1.0,
            "clusters_full": int(a["aurora_id"].nunique()), "clusters_incremental": int(b["aurora_id"].nunique())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", required=True)
    ap.add_argument("--window-days", type=int, default=30)
    ap.add_argument("--windows", type=int, default=None, help="limit the number of windows")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cdp-config", default=None, help="JSON engine config overrides (e.g. the legacy carried-edges mode)")
    a = ap.parse_args()
    overrides = json.loads(a.cdp_config) if a.cdp_config else {}
    df = pd.read_parquet(a.profiles)
    df["created_at"] = pd.to_datetime(df["created_at"])
    epoch = df["created_at"].min().normalize()
    df["_w"] = ((df["created_at"] - epoch).dt.days // a.window_days).astype(int)
    windows = sorted(df["_w"].unique())[: a.windows or None]
    tmp = Path(tempfile.mkdtemp(prefix="aurora-incr-"))
    cons = {}
    for name in ("full", "incr"):
        ws = tmp / name; ws.mkdir()
        cfg = load_config(overrides={"workspace": str(ws), **overrides}, use_last_best=False)
        con = connect(cfg.db_path); init_schema(con)
        cons[name] = (con, cfg)
    results = []
    try:
        for i, w in enumerate(windows):
            batch = df[df["_w"] == w].drop(columns="_w")
            runs = {}
            for name, (con, cfg) in cons.items():
                t = time.perf_counter()
                ingest_frame(con, batch, "input", "profiles", "incremental")
                tag_feed(con, cfg, "input", "profiles", SEM)
                mode = "full" if (name == "full" or i == 0) else "incremental"
                r = run_stitch(con, cfg, mode=mode)
                runs[name] = (r, round(time.perf_counter() - t, 2))
            cmp = compare(partition(cons["full"][0], runs["full"][0].run_id), partition(cons["incr"][0], runs["incr"][0].run_id))
            row = {"window": int(w), "mode_incr": "full" if i == 0 else "incremental", "seconds_full": runs["full"][1], "seconds_incr": runs["incr"][1],
                   "pairs_scored_full": runs["full"][0].metrics.get("pairs_scored"), "pairs_scored_incr": runs["incr"][0].metrics.get("pairs_scored"),
                   "carried_edges": runs["incr"][0].metrics.get("carried_edges"), **cmp}
            results.append(row)
            print(json.dumps(row), flush=True)
    finally:
        for con, _ in cons.values():
            con.close()
        shutil.rmtree(tmp, ignore_errors=True)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps({"profiles": a.profiles, "window_days": a.window_days, "overrides": overrides, "windows": results}, indent=1))
    md = ["# Incremental vs full Stitch — equivalence measurement", "", f"_corpus `{a.profiles}`, {a.window_days}-day windows, overrides `{json.dumps(overrides)}`_", "",
          "| window | incr mode | pairs scored full / incr | carried edges | wall full / incr | pair P / R vs full | records with identical membership | clusters full / incr |",
          "|---|---|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['window']} | {r['mode_incr']} | {r['pairs_scored_full']:,} / {r['pairs_scored_incr']:,} | {r['carried_edges']:,} | {r['seconds_full']} s / {r['seconds_incr']} s | "
                  f"{r['pair_precision_vs_full']} / {r['pair_recall_vs_full']} | {r['records_same_membership_share']:.2%} | {r['clusters_full']:,} / {r['clusters_incremental']:,} |")
    (out / "report.md").write_text("\n".join(md) + "\n")
    print("->", out / "report.md")


if __name__ == "__main__":
    main()
