"""Evaluation suite: pairwise and cluster metrics against planted truth, plus
stable-ID churn between two runs.

Reads ``Unified_Customer`` (which carries ``truth_id`` for synthetic data) and
``Stitch_Scores`` from the lake, writes ``data/eval/<job_id>.json`` and
refreshes ``docs/evaluation.md`` with the latest numbers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from aurora.config.schema import load_config
from aurora.data.schemas import TABLES
from aurora.io.deltaio import read_table_pandas


def pair_metrics_from_scores(scores: pd.DataFrame, thresholds: list[float]) -> list[dict]:
    """Pair precision/recall/F1 among *candidate* pairs at several keep thresholds."""
    truth = (scores["truth_id_l"] == scores["truth_id_r"]).to_numpy()
    out = []
    for t in thresholds:
        pred = (scores["score"] >= t).to_numpy() & (scores["match_type"] != "hard_conflict").to_numpy()
        tp = int(np.sum(pred & truth))
        fp = int(np.sum(pred & ~truth))
        fn = int(np.sum(~pred & truth))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        out.append({"threshold": t, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
                    "tp": tp, "fp": fp, "fn": fn})
    return out


def bcubed(pred: pd.Series, truth: pd.Series) -> dict[str, float]:
    """B-cubed precision/recall/F1 over records."""
    pred_groups: dict = defaultdict(list)
    truth_groups: dict = defaultdict(list)
    for i, (p, t) in enumerate(zip(pred, truth, strict=True)):
        pred_groups[p].append(i)
        truth_groups[t].append(i)
    truth_arr = truth.to_numpy()
    pred_arr = pred.to_numpy()
    prec = rec = 0.0
    n = len(pred)
    for members in pred_groups.values():
        c = Counter(truth_arr[members])
        prec += sum(v * v for v in c.values()) / len(members)
    for members in truth_groups.values():
        c = Counter(pred_arr[members])
        rec += sum(v * v for v in c.values()) / len(members)
    prec, rec = prec / n, rec / n
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}


def pair_recall_global(pred: pd.Series, truth: pd.Series) -> dict[str, float]:
    """Pairwise P/R over *all* true pairs (captures blocking misses)."""
    def n_pairs(groups: pd.Series) -> int:
        c = groups.value_counts()
        return int((c * (c - 1) // 2).sum())
    both = pd.Series(list(zip(pred, truth, strict=True)))
    tp = n_pairs(both)
    pp = n_pairs(pred)
    tpairs = n_pairs(truth)
    p = tp / pp if pp else 0.0
    r = tp / tpairs if tpairs else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4), "true_pairs": tpairs,
            "pred_pairs": pp, "tp": tp}


def churn(prev: pd.DataFrame, cur: pd.DataFrame) -> dict[str, float]:
    m = prev.merge(cur, on=["datasource", "pk"], suffixes=("_prev", "_cur"))
    moved = int((m["aurora_id_prev"] != m["aurora_id_cur"]).sum())
    return {"common_records": len(m), "moved": moved,
            "churn_pct": round(100.0 * moved / len(m), 3) if len(m) else 0.0}


def evaluate(lake_root: str, out_dir: str, prev_assignments: str | None = None) -> dict:
    uc = read_table_pandas(lake_root, TABLES["unified_customer"],
                           columns=["datasource", "pk", "aurora_id", "truth_id", "job_id"])
    if uc.empty:
        raise SystemExit("no Unified_Customer table; run the pipeline first")
    job_id = str(uc["job_id"].iloc[0])
    report: dict = {"job_id": job_id, "records": len(uc), "clusters": int(uc["aurora_id"].nunique()),
                    "generated_at": datetime.now(timezone.utc).isoformat()}
    has_truth = uc["truth_id"].notna().all()
    if has_truth:
        report["truth_clusters"] = int(uc["truth_id"].nunique())
        report["bcubed"] = bcubed(uc["aurora_id"], uc["truth_id"])
        report["pairs_global"] = pair_recall_global(uc["aurora_id"], uc["truth_id"])
        sc = read_table_pandas(lake_root, TABLES["stitch_scores"],
                               columns=["datasource_l", "pk_l", "datasource_r", "pk_r", "score", "match_type"])
        t = uc[["datasource", "pk", "truth_id"]]
        sc = sc.merge(t.rename(columns={"datasource": "datasource_l", "pk": "pk_l", "truth_id": "truth_id_l"}),
                      on=["datasource_l", "pk_l"])
        sc = sc.merge(t.rename(columns={"datasource": "datasource_r", "pk": "pk_r", "truth_id": "truth_id_r"}),
                      on=["datasource_r", "pk_r"])
        report["pairs_candidates"] = pair_metrics_from_scores(sc, [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])
    if prev_assignments:
        prev = pd.read_parquet(prev_assignments)
        report["churn"] = churn(prev, uc[["datasource", "pk", "aurora_id"]])
    mapping = read_table_pandas(lake_root, TABLES["unified_changes_clusters"])
    if not mapping.empty:
        latest = mapping[mapping["job_id"] == job_id]
        report["jitter_events"] = latest["change_type"].value_counts().to_dict()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out = Path(out_dir) / f"{job_id}.json"
    out.write_text(json.dumps(report, indent=2))
    report["_path"] = str(out)
    return report


def render_markdown(report: dict) -> str:
    lines = ["# Evaluation", "", f"Latest job: `{report['job_id']}` ({report['generated_at']})", "",
             f"- records: {report['records']}", f"- clusters: {report['clusters']}"]
    if "truth_clusters" in report:
        lines.append(f"- truth clusters: {report['truth_clusters']}")
        b = report["bcubed"]
        lines += ["", "## B-cubed (cluster-level)", "", "| precision | recall | f1 |", "|---|---|---|",
                  f"| {b['precision']} | {b['recall']} | {b['f1']} |"]
        g = report["pairs_global"]
        lines += ["", "## Pairwise over all true pairs (includes blocking misses)", "",
                  "| precision | recall | f1 | true pairs | predicted pairs |", "|---|---|---|---|---|",
                  f"| {g['precision']} | {g['recall']} | {g['f1']} | {g['true_pairs']} | {g['pred_pairs']} |"]
        lines += ["", "## Pairwise among candidate pairs by keep threshold", "",
                  "| threshold | precision | recall | f1 | tp | fp | fn |", "|---|---|---|---|---|---|---|"]
        for r in report["pairs_candidates"]:
            lines.append(f"| {r['threshold']} | {r['precision']} | {r['recall']} | {r['f1']} | {r['tp']} | {r['fp']} | {r['fn']} |")
    if "churn" in report:
        c = report["churn"]
        lines += ["", "## Stable-ID churn vs previous run", "",
                  f"- common records: {c['common_records']}", f"- moved to a different aurora_id: {c['moved']}",
                  f"- churn: {c['churn_pct']}%"]
    if "jitter_events" in report:
        lines += ["", "## Jitter events (this job)", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(report["jitter_events"].items())]
    lines += ["", "## Method", "",
              "- **Pair P/R/F1** compares scored candidate pairs against `truth_id` equality; the *global* "
              "variant counts every true pair, so recall there also reflects blocking misses.",
              "- **B-cubed** averages per-record precision/recall of its predicted cluster vs its truth cluster.",
              "- **Churn** = share of records present in both runs whose `aurora_id` changed (jitter).",
              "", "Regenerate with `make eval` (optionally `PREV=data/eval/prev_assignments.parquet`)."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate the latest identity run")
    ap.add_argument("--config", default="configs/tenants/demo.yaml")
    ap.add_argument("--prev", default=None, help="parquet of previous (datasource, pk, aurora_id) for churn")
    ap.add_argument("--doc", default="docs/aurora/evaluation.md")
    args = ap.parse_args()
    cfg = load_config(args.config)
    report = evaluate(cfg.storage.lake_root, cfg.storage.eval_root, args.prev)
    Path(args.doc).parent.mkdir(parents=True, exist_ok=True)
    Path(args.doc).write_text(render_markdown(report))
    print(json.dumps({k: v for k, v in report.items() if k not in ("pairs_candidates",)}, indent=2))
    print(f"wrote {report['_path']} and {args.doc}")


if __name__ == "__main__":
    main()
