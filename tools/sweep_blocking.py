#!/usr/bin/env python
"""Held-out parameter sweep for the blocking / threshold knobs of the aurora_cdp resolver.

Protocol (anti-overfitting): tune on corpora generated with seeds the reported evaluations never use
(`--tune` dirs), score every trial with the same gate metrics the harness reports, then confirm the winner on
`--confirm` dirs (another held-out seed / tier). The reported tiers (seed 42) are evaluated afterwards by the
harness and are never read here. Every trial is a full engine run (final snapshot, single process) through
`aurora_cdp.adapters.resolve_records`, i.e. the real resolver, not a stub.

Outputs `reports/<date>/tuning/{trials.jsonl, sweep.json, sweep.md}` (search space, trial count, per-trial
metrics, the noise band of the top configs, and the confirmation results).

    tools/sweep_blocking.py --tune ~/data/aurora-testdata-tune/small-s7 ~/data/aurora-testdata-tune/small-s11 \
        --confirm ~/data/aurora-testdata-tune/medium-s7 --out reports/2026-10-22/tuning
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from aurora_cdp.adapters import resolve_records  # noqa: E402
from aurora_cdp.config import load_config  # noqa: E402

SEMANTIC_MAP = {"first_name": "given_name", "last_name": "surname", "email": "email", "phone": "phone", "dob": "birthdate",
                "address": "address", "city": "city", "postal_code": "postal", "created_at": "update_dt"}

# search space: documented defaults are the centre; every axis is auditable from the sweep report
SPACE: dict[str, list] = {
    "matcher.scorer": ["rules", "ordinal"],
    "matcher.match_threshold": [2.5, 3.0, 3.5, 4.0],
    "blocking.name_budget": [20_000, 50_000, 200_000],
    "blocking.max_pairs_per_block": [500_000],
    "blocking.sn_window": [25],
}
GATES = {"precision": 0.98, "f1": 0.90, "bcubed_f1": 0.93, "blocking_recall": 0.85, "false_merge_clusters": 0.02}


def bcubed_f1(res, truth: pd.Series, ids: pd.Series) -> float:
    a = res.assignments[["source_record_id", "unified_id"]].merge(pd.DataFrame({"source_record_id": ids.astype(str), "truth": truth.to_numpy()}), on="source_record_id")
    both = a.groupby(["unified_id", "truth"]).size().rename("n").reset_index()
    cs = a.groupby("unified_id").size().rename("cs")
    ts = a.groupby("truth").size().rename("ts")
    both = both.join(cs, on="unified_id").join(ts, on="truth")
    n = len(a)
    p = float((both["n"] ** 2 / both["cs"]).sum() / n)
    r = float((both["n"] ** 2 / both["ts"]).sum() / n)
    return round(2 * p * r / (p + r), 4) if p + r else 0.0


def load_corpus(path: Path) -> tuple[pd.DataFrame, pd.Series, dict]:
    prof = pd.read_parquet(path / "profiles.parquet")
    truth = pd.read_parquet(path / "truth.parquet")
    man = json.loads((path / "manifest.json").read_text())
    df = prof.merge(truth, on="profile_id")
    rec = pd.DataFrame({"source_record_id": df["profile_id"].astype(str), "datasource": df["source"].astype(str)})
    for col, sem in SEMANTIC_MAP.items():
        if col in df.columns:
            v = df[col]
            rec[sem] = (v.dt.strftime("%Y-%m-%d %H:%M:%S") if pd.api.types.is_datetime64_any_dtype(v.dtype) else v.astype(str))
    rec = rec.astype(object)
    for c in rec.columns:
        if c in ("source_record_id", "datasource"):
            continue
        s = rec[c].astype(str)
        rec[c] = rec[c].where((s.str.strip() != "") & (s != "nan") & (s != "NaT") & (s != "None"), None)
    return rec, df["person_id"].astype(str).reset_index(drop=True), man


def _pairs(counts) -> int:
    return int(sum(comb(int(n), 2) for n in counts))


def metrics(res, truth: pd.Series, ids: pd.Series, true_pairs_total: int) -> dict:
    a = res.assignments[["source_record_id", "unified_id"]].copy()
    t = pd.DataFrame({"source_record_id": ids.astype(str), "truth": truth.to_numpy()})
    df = a.merge(t, on="source_record_id")
    pred = _pairs(df.groupby("unified_id").size())
    true = _pairs(df.groupby("truth").size())
    tp = _pairs(df.groupby(["unified_id", "truth"]).size())
    p = tp / pred if pred else 1.0
    r = tp / true if true else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    sizes = df.groupby("unified_id").agg(n=("truth", "size"), k=("truth", "nunique"))
    multi = sizes[sizes["n"] > 1]
    fm = float((multi["k"] > 1).mean()) if len(multi) else 0.0
    # blocking recall: true pairs among scored candidate pairs / all true pairs
    s = res.scores
    tr = dict(zip(t["source_record_id"], t["truth"], strict=True))
    lt = s["left_record_id"].astype(str).map(tr)
    rt = s["right_record_id"].astype(str).map(tr)
    pos = int(((lt == rt) & lt.notna()).sum())
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4), "false_merge_clusters": round(fm, 4),
            "blocking_recall": round(min(1.0, pos / true_pairs_total), 4), "pairs_scored": int(len(s)),
            "clusters": int(df["unified_id"].nunique()), "true_pairs": true}


def overlay(trial: dict) -> dict:
    strategies = [dict(s) for s in load_config(use_last_best=False)["blocking"]["strategies"]]
    for s in strategies:
        if s["type"] == "name":
            s["max_pairs_per_block"] = int(trial["blocking.name_budget"])
    return {"blocking": {"max_pairs_per_block": int(trial["blocking.max_pairs_per_block"]), "sn_window": int(trial["blocking.sn_window"]),
                         "strategies": strategies},
            "matcher": {"match_threshold": float(trial["matcher.match_threshold"]), "scorer": str(trial.get("matcher.scorer", "rules"))}}


def run_trial(trial: dict, corpora: list[tuple[str, pd.DataFrame, pd.Series, dict]]) -> dict:
    out = {"trial": trial, "per_corpus": {}}
    for name, rec, truth, man in corpora:
        t0 = time.time()
        res = resolve_records(rec, config=overlay(trial), datasource="input")
        m = metrics(res, truth, rec["source_record_id"], man["counts"]["true_pairs"])
        m["wall_s"] = round(time.time() - t0, 1)
        m["engine_peak_rss_mb"] = res.metrics.get("peak_rss_mb")
        m["records_dropped_by_blocking"] = res.metrics.get("records_dropped_by_blocking")
        m["scorer_used"] = res.metrics.get("scorer_used")
        m["scorer_fallback_reason"] = res.metrics.get("scorer_fallback_reason")
        m["bcubed_f1"] = bcubed_f1(res, truth, rec["source_record_id"])
        out["per_corpus"][name] = m
    keys = ["precision", "recall", "f1", "bcubed_f1", "blocking_recall", "false_merge_clusters", "pairs_scored", "wall_s"]
    out["mean"] = {k: round(float(np.mean([c[k] for c in out["per_corpus"].values()])), 4) for k in keys}
    g = out["mean"]
    def passes(m):
        return bool(m["precision"] >= GATES["precision"] and m["f1"] >= GATES["f1"] and m["bcubed_f1"] >= GATES["bcubed_f1"]
                    and m["blocking_recall"] >= GATES["blocking_recall"] and m["false_merge_clusters"] <= GATES["false_merge_clusters"])

    out["gates_pass"] = all(passes(c) for c in out["per_corpus"].values())  # every tuning corpus, not just the mean
    return out


def rank_key(t: dict):
    g = t["mean"]
    # gates first, then F1 (ties -> fewer pairs scored = cheaper)
    return (not t["gates_pass"], -(g["f1"]), g["pairs_scored"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tune", nargs="+", required=True, help="corpus dirs used to choose the config")
    ap.add_argument("--confirm", nargs="*", default=[], help="held-out corpus dirs used only to confirm the top configs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--max-trials", type=int, default=None)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tune = [(Path(p).name, *load_corpus(Path(p))) for p in a.tune]
    confirm = [(Path(p).name, *load_corpus(Path(p))) for p in a.confirm]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "aurora_cdp"], cwd=HERE, capture_output=True, text=True).stdout.strip())
    grid = [dict(zip(SPACE, vals, strict=True)) for vals in itertools.product(*SPACE.values())]
    if a.max_trials:
        grid = grid[: a.max_trials]
    trials: list[dict] = []
    log = (out / "trials.jsonl").open("w")
    t_all = time.time()
    for i, trial in enumerate(grid, 1):
        r = run_trial(trial, tune)
        r["i"] = i
        trials.append(r)
        log.write(json.dumps(r) + "\n")
        log.flush()
        g = r["mean"]
        print(f"[{i}/{len(grid)}] {trial} -> P {g['precision']} R {g['recall']} F1 {g['f1']} BR {g['blocking_recall']} FM {g['false_merge_clusters']} pairs {int(g['pairs_scored'])} {'PASS' if r['gates_pass'] else 'fail'}", flush=True)
    log.close()
    ranked = sorted(trials, key=rank_key)
    top = ranked[: a.top]
    f1s = [t["mean"]["f1"] for t in ranked if t["gates_pass"]] or [t["mean"]["f1"] for t in ranked]
    noise = {"top_f1": f1s[: a.top], "spread_top": round(max(f1s[: a.top]) - min(f1s[: a.top]), 4) if len(f1s) > 1 else 0.0,
             "within_noise": bool(len(f1s) > 1 and (max(f1s[: a.top]) - min(f1s[: a.top])) < 0.005)}
    confirmation = []
    for t in top:
        c = run_trial(t["trial"], confirm) if confirm else None
        confirmation.append({"trial": t["trial"], "tune_mean": t["mean"], "confirm": c["per_corpus"] if c else None,
                             "confirm_mean": c["mean"] if c else None, "confirm_gates_pass": c["gates_pass"] if c else None})
    chosen = top[0]["trial"]
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "engine_commit": commit, "engine_dirty": dirty,
              "search_space": SPACE, "trials": len(grid), "gates": GATES,
              "tune_corpora": [{"name": n, "seed": m["config"]["seed"], "tier": m["config"]["tier"], "profiles": m["counts"]["profiles"], "fingerprint": m["fingerprint"]} for n, _, _, m in tune],
              "confirm_corpora": [{"name": n, "seed": m["config"]["seed"], "tier": m["config"]["tier"], "profiles": m["counts"]["profiles"], "fingerprint": m["fingerprint"]} for n, _, _, m in confirm],
              "ranked": [{"i": t["i"], "trial": t["trial"], "mean": t["mean"], "gates_pass": t["gates_pass"]} for t in ranked],
              "top": confirmation, "noise": noise, "chosen": chosen, "wall_s": round(time.time() - t_all, 1),
              "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)}
    (out / "sweep.json").write_text(json.dumps(result, indent=2))
    (out / "sweep.md").write_text(markdown(result))
    print(f"chosen: {chosen}; noise band of top {a.top}: {noise}; wrote {out / 'sweep.md'}")
    return 0


def markdown(r: dict) -> str:
    L = [f"# Blocking / threshold sweep (held-out seeds)", "",
         f"_Generated {r['generated_at']} · engine `{r['engine_commit']}`{' (dirty)' if r['engine_dirty'] else ''} · {r['trials']} trials · wall {r['wall_s']} s · peak RSS {r['peak_rss_mb']} MB_", "",
         "## Protocol", "",
         "Tuned on: " + ", ".join(f"`{c['name']}` (tier {c['tier']}, seed {c['seed']}, {c['profiles']:,} profiles)" for c in r["tune_corpora"]) + ".  ",
         "Confirmed on: " + (", ".join(f"`{c['name']}` (tier {c['tier']}, seed {c['seed']}, {c['profiles']:,} profiles)" for c in r["confirm_corpora"]) or "—") + ".  ",
         "Reported tiers (seed 42: small / medium / large) are never read by this sweep; they are evaluated afterwards by the harness with the chosen config.", "",
         "## Search space", "", "| parameter | values |", "|---|---|"]
    L += [f"| `{k}` | {v} |" for k, v in r["search_space"].items()]
    L += ["", f"Gates (means over tuning corpora): precision ≥ {r['gates']['precision']}, F1 ≥ {r['gates']['f1']}, blocking recall ≥ {r['gates']['blocking_recall']}, false-merge clusters ≤ {r['gates']['false_merge_clusters']}.", "",
          "## Ranking (gates first, then F1, then fewer scored pairs)", "",
          "| # | scorer | threshold | name budget | max_pairs_per_block | sn_window | P | R | F1 | B³ F1 | blocking R | false-merge | pairs | wall s | gates (all tune corpora) |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in r["ranked"]:
        tr, g = t["trial"], t["mean"]
        L.append(f"| {t['i']} | {tr.get('matcher.scorer', 'rules')} | {tr['matcher.match_threshold']} | {tr['blocking.name_budget']:,} | {tr['blocking.max_pairs_per_block']:,} | {tr['blocking.sn_window']} | {g['precision']} | {g['recall']} | {g['f1']} | {g['bcubed_f1']} | {g['blocking_recall']} | {g['false_merge_clusters']} | {int(g['pairs_scored']):,} | {g['wall_s']} | {'✅' if t['gates_pass'] else '❌'} |")
    n = r["noise"]
    L += ["", f"**Noise band:** top-{len(n['top_f1'])} F1 = {n['top_f1']}, spread {n['spread_top']} → " + ("the top configs are within noise of each other; the chosen one is the cheapest of them, not a clear winner." if n["within_noise"] else "the top config is separated from the runners-up by more than the noise band."), "",
          "## Confirmation on held-out corpora", "", "| config | tune F1 / blocking R / false-merge | confirm F1 / blocking R / false-merge | gates on confirm |", "|---|---|---|---|"]
    for c in r["top"]:
        tm, cm = c["tune_mean"], c["confirm_mean"]
        L.append(f"| {c['trial']} | {tm['f1']} / {tm['blocking_recall']} / {tm['false_merge_clusters']} | " + (f"{cm['f1']} / {cm['blocking_recall']} / {cm['false_merge_clusters']} | {'✅' if c['confirm_gates_pass'] else '❌'} |" if cm else "— | — |"))
    L += ["", f"**Chosen config:** `{r['chosen']}` → written to `aurora_cdp/config/defaults.yaml` by hand (documented as swept), then evaluated on the reported seed-42 tiers by the harness.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
