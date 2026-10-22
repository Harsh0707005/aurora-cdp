#!/usr/bin/env python
"""Train the ordinal-regression scorer label-free on a held-out corpus and save the model file.

    tools/train_ordinal.py --train <corpus-dir> --out reports/<date>/ordinal --model configs/learned/ordinal.json

Positives/negatives come from the deterministic rules and random non-candidate pairs of the training corpus
(no truth labels are read for training). If the corpus carries ``truth.parquet`` the tool additionally reports
pairwise P/R/F1 of a full resolve on the training corpus with the rule scorer vs the ordinal scorer (training-set
numbers; the held-out evaluation is the harness run on seeds this tool never saw). The overlay YAML switches
``matcher.scorer: ordinal`` with ``retrain: never`` and the saved model.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from aurora_cdp.adapters import resolve_records  # noqa: E402
from aurora_cdp.config import Config, load_config  # noqa: E402
from aurora_cdp.stitch.blocking import build_candidate_pairs, load_records_table  # noqa: E402
from aurora_cdp.stitch.ordinal import corpus_context, train_from_candidates  # noqa: E402
from tools.learn_dnf import load_corpus  # noqa: E402
from tools.sweep_blocking import SEMANTIC_MAP, metrics  # noqa: E402


def harness_records(path: Path) -> tuple[pd.DataFrame, pd.Series, dict]:
    prof = pd.read_parquet(path / "profiles.parquet").merge(pd.read_parquet(path / "truth.parquet"), on="profile_id")
    rec = pd.DataFrame({"source_record_id": prof["profile_id"].astype(str), "datasource": prof["source"].astype(str)})
    for col, sem in SEMANTIC_MAP.items():
        if col in prof.columns:
            v = prof[col]
            rec[sem] = v.dt.strftime("%Y-%m-%d %H:%M:%S") if pd.api.types.is_datetime64_any_dtype(v.dtype) else v.astype(str)
    rec = rec.astype(object)
    for c in rec.columns:
        if c in ("source_record_id", "datasource"):
            continue
        s = rec[c].astype(str)
        rec[c] = rec[c].where((s.str.strip() != "") & (s != "nan") & (s != "NaT") & (s != "None"), None)
    return rec, prof["person_id"].astype(str).reset_index(drop=True), json.loads((path / "manifest.json").read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True, help="model json to write")
    ap.add_argument("--overlay", default=None, help="overlay yaml (default: <model>.yaml)")
    a = ap.parse_args()
    cfg = load_config(use_last_best=False)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    df, truth, man = load_corpus(Path(a.train), cfg)
    con = duckdb.connect(":memory:")
    load_records_table(con, df.drop(columns=[c for c in ("email_local", "house_no", "given_sdx", "surname_sdx") if c in df.columns]))
    bst = build_candidate_pairs(con, cfg.blocking)
    ctx = corpus_context(con)
    model, rep = train_from_candidates(con, cfg, ctx)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "engine_commit": commit,
              "train_corpus": {"name": Path(a.train).name, "seed": man["config"]["seed"], "tier": man["config"]["tier"], "fingerprint": man["fingerprint"], "records": int(len(df))},
              "blocking": {"pairs": bst.pairs, "records_dropped_by_blocking": bst.records_dropped_by_blocking},
              "training": rep.as_metrics(), "config": cfg.matcher.get("ordinal")}
    if model is None:
        report["result"] = "fallback"
        (out / "ordinal.json").write_text(json.dumps(report, indent=2, default=str))
        print(f"no model: {rep.fallback_reason}")
        return 1
    model.meta.update({"train_corpus": report["train_corpus"], "engine_commit": commit, "generated_at": report["generated_at"]})
    model.save(a.model)
    overlay_path = Path(a.overlay or str(Path(a.model).with_suffix(".yaml")))
    overlay = {"matcher": {"scorer": "ordinal", "ordinal": {"model_file": str(Path(a.model).resolve()), "retrain": "never"}}}
    overlay_path.write_text(yaml.safe_dump(overlay, sort_keys=False))
    report["weights"] = dict(zip(model.feature_names + [f"{f}_missing" for f in model.feature_names], [round(float(x), 4) for x in model.w], strict=True))
    report["thresholds"] = [round(float(t), 4) for t in model.thresholds]
    # training-set comparison (rules vs ordinal) on the full corpus: NOT a held-out number
    rec, tr, _ = harness_records(Path(a.train))
    comp = {}
    for name, overlay_cfg in (("rules", {"matcher": {"scorer": "rules"}}), ("ordinal", overlay)):
        res = resolve_records(rec, config=overlay_cfg, datasource="input")
        comp[name] = metrics(res, tr, rec["source_record_id"], man["counts"]["true_pairs"])
        comp[name]["scorer_used"] = res.metrics.get("scorer_used")
    report["train_corpus_comparison"] = comp
    report["wall_s"] = round(time.time() - t0, 1)
    (out / "ordinal.json").write_text(json.dumps(report, indent=2, default=str))
    L = [f"# Ordinal scorer, label-free training on `{report['train_corpus']['name']}` (tier {report['train_corpus']['tier']}, seed {report['train_corpus']['seed']})", "",
         f"_engine `{commit}` · positives {rep.positives:,} · negatives {rep.negatives:,} · unlabeled {rep.unlabeled:,} · rounds {len(rep.rounds)} · thresholds {report['thresholds']} · wall {report['wall_s']} s_", "",
         "## Self-training rounds", "", "| round | train pairs | added pos | added neg | loss |", "|---|---|---|---|---|"]
    L += [f"| {r['round']} | {r['train']:,} | {r['added_pos']} | {r['added_neg']} | {r.get('loss')} |" for r in rep.rounds]
    L += ["", "## Weights (standardised features; `_missing` = presence indicators)", "", "| feature | weight |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(report["weights"].items(), key=lambda kv: -abs(kv[1]))]
    L += ["", "## Training-corpus comparison (same seed the model was trained on — NOT held-out)", "", "| scorer | P | R | F1 | false-merge clusters | blocking recall |", "|---|---|---|---|---|---|"]
    L += [f"| {k} | {m['precision']} | {m['recall']} | {m['f1']} | {m['false_merge_clusters']} | {m['blocking_recall']} |" for k, m in comp.items()]
    L += ["", f"Model: `{a.model}` · overlay: `{overlay_path}` → evaluate with the harness on seeds never used here.", ""]
    (out / "ordinal.md").write_text("\n".join(L))
    print(f"trained: positives={rep.positives} negatives={rep.negatives} thresholds={report['thresholds']} train F1 rules {comp['rules']['f1']} vs ordinal {comp['ordinal']['f1']}; wrote {out / 'ordinal.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
