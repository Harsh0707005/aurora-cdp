"""Threshold sweep on the demo dataset: precision / recall / false-merge / ID churn per threshold.

Writes a markdown table into docs/tuning.md (between the AUTOGEN markers) and the best threshold (by F1,
ties broken by lower ID churn) into <workspace>/last_best.yaml, which load_config() overlays by default.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from aurora_cdp.config import Config, load_config
from aurora_cdp.demo import EVENTS_CFG, pipeline_spec, write_demo_data
from aurora_cdp.evaluation import pairwise_metrics
from aurora_cdp.orchestration.pipeline import run_pipeline
from aurora_cdp.storage.duck import connect, init_schema, read_df

AUTOGEN_START = "<!-- AUTOGEN:tuning-start -->"
AUTOGEN_END = "<!-- AUTOGEN:tuning-end -->"


def sweep(cfg: Config | None = None, thresholds: list[float] | None = None, people: int = 400, seed: int = 11, quick: bool = True) -> pd.DataFrame:
    cfg = cfg or load_config(use_last_best=False)
    thresholds = thresholds or list(cfg.tuning.get("thresholds", [2.0, 2.5, 3.0, 3.5, 4.0]))
    if quick:
        people = min(people, 400)
    ws = cfg.workspace_path / "tuning"
    if ws.exists():
        shutil.rmtree(ws)
    data_dir = ws / "demo"
    write_demo_data(data_dir, people, seed)
    labels = pd.read_csv(data_dir / "labels.csv", dtype=str)
    rows = []
    for thr in thresholds:
        run_cfg = Config({**cfg, "workspace": str(ws / f"thr_{thr}"), "events": EVENTS_CFG, "matcher": {**cfg["matcher"], "match_threshold": float(thr)}})
        Path(run_cfg["workspace"]).mkdir(parents=True, exist_ok=True)
        con = connect(run_cfg.db_path)
        try:
            init_schema(con)
            spec1 = pipeline_spec(data_dir, ws / "out", batch=1, mode="full")
            spec2 = pipeline_spec(data_dir, ws / "out", batch=2, mode="incremental")
            spec1["segments"], spec1["destinations"], spec1["profile"] = [], [], False
            spec2["segments"], spec2["destinations"], spec2["profile"] = [], [], False
            r1 = run_pipeline(con, run_cfg, spec1)
            r2 = run_pipeline(con, run_cfg, spec2)
            assign = read_df(con, "SELECT datasource, pk, aurora_id FROM id_ledger WHERE is_current")
        finally:
            con.close()
        m = pairwise_metrics(assign, labels)
        rows.append(
            {
                "threshold": float(thr), **m,
                "id_churn_pct": r2.metrics["jitter"]["jitter_pct"], "ids_minted_run2": r2.metrics["jitter"]["ids_minted"],
                "clusters_run1": r1.metrics["clusters"], "edges_run1": r1.metrics["edges"],
                "seconds": round(sum(s["seconds"] for s in r1.steps + r2.steps), 2),
            }
        )
    return pd.DataFrame(rows)


def pick_best(table: pd.DataFrame) -> float:
    ordered = table.sort_values(["f1", "id_churn_pct", "threshold"], ascending=[False, True, True])
    return float(ordered.iloc[0]["threshold"])


def write_results(table: pd.DataFrame, best: float, docs_path: Path, last_best_path: Path, people: int) -> None:
    cols = ["threshold", "precision", "recall", "f1", "false_merge_rate", "id_churn_pct", "ids_minted_run2", "clusters_run1", "edges_run1", "seconds"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in table.iterrows():
        lines.append("| " + " | ".join(("**%s**" % r[c]) if (c == "threshold" and float(r[c]) == best) else str(r[c]) for c in cols) + " |")
    block = "\n".join(
        [AUTOGEN_START, f"_Last sweep: {datetime.utcnow():%Y-%m-%d %H:%M} UTC, synthetic demo ({people} people, two runs: full + incremental). Best threshold (F1, then lowest churn): **{best}**._", "", *lines, AUTOGEN_END]
    )
    text = docs_path.read_text(encoding="utf-8") if docs_path.exists() else "# Tuning\n\n"
    if AUTOGEN_START in text and AUTOGEN_END in text:
        text = re.sub(re.escape(AUTOGEN_START) + ".*?" + re.escape(AUTOGEN_END), lambda _m: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    docs_path.write_text(text, encoding="utf-8")
    last_best_path.parent.mkdir(parents=True, exist_ok=True)
    last_best_path.write_text(
        yaml.safe_dump({"matcher": {"match_threshold": best}, "_tuned_at": datetime.utcnow().isoformat(), "_source": "aurora tune"}, sort_keys=False),
        encoding="utf-8",
    )
