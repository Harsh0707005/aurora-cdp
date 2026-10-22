#!/usr/bin/env python
"""Learn DNF blocking strategies on a held-out corpus and write them as a config overlay.

    tools/learn_dnf.py --train <corpus-dir> [--confirm <corpus-dir> ...] --labels self|truth \
        --out reports/<date>/dnf --overlay configs/learned/dnf.yaml

* ``--labels self``  : label-free (deterministic rules supply the positives) — the production setting.
* ``--labels truth`` : positives from the corpus' entity labels (evaluation only).

Outputs: ``<out>/dnf.json`` (predicate table with cost / pairwise completeness, chosen conjunctions, budget),
``<out>/dnf.md`` (learned-vs-fixed comparison on the training sample and on every confirm corpus) and the overlay
YAML (``blocking.strategy_source: learned`` + ``blocking.learned_strategies_file``) that the harness / engine can load.
Corpora used here must be seeds the reported evaluations never use (see docs/tuning.md).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from aurora_cdp.config import load_config  # noqa: E402
from aurora_cdp.ingestion.normalize import (  # noqa: E402
    canonical_address, canonical_birthdate, canonical_email, canonical_given_name, canonical_name, canonical_phone, canonical_postal,
)
from aurora_cdp.stitch.dnf import derive_columns, evaluate_strategies, learn_dnf, self_label_positives, truth_positives  # noqa: E402


def _nn(v):
    return None if v is None or (isinstance(v, float) and v != v) or v == "" else v


def load_corpus(path: Path, cfg) -> tuple[pd.DataFrame, np.ndarray, dict]:
    prof = pd.read_parquet(path / "profiles.parquet").merge(pd.read_parquet(path / "truth.parquet"), on="profile_id")
    man = json.loads((path / "manifest.json").read_text())
    ncfg = cfg.normalize
    df = pd.DataFrame({
        "datasource": prof["source"].astype(str), "pk": prof["profile_id"].astype(str),
        "given_name_norm": [_nn(canonical_name(_nn(v))) for v in prof["first_name"]],
        "given_name_canon": [_nn(canonical_given_name(_nn(v))) for v in prof["first_name"]],
        "surname_norm": [_nn(canonical_name(_nn(v))) for v in prof["last_name"]],
        "email_norm": [_nn(canonical_email(_nn(v), ncfg)) for v in prof["email"]],
        "phone_match": [_nn(canonical_phone(_nn(v))[1]) for v in prof["phone"]],
        "address_norm": [_nn(canonical_address(_nn(v), ncfg.get("address_abbreviations"))) for v in prof["address"]],
        "postal_norm": [_nn(canonical_postal(_nn(v))) for v in prof["postal_code"]],
        "birthdate_norm": [_nn(canonical_birthdate(_nn(v))) for v in prof["dob"]],
        "loy_id_norm": None, "ck": None,
    })
    return derive_columns(df), prof["person_id"].astype(str).to_numpy(), man


def sample(df: pd.DataFrame, truth: np.ndarray, n: int, seed: int) -> tuple[pd.DataFrame, np.ndarray]:
    if len(df) <= n:
        return df.reset_index(drop=True), truth
    idx = np.sort(np.random.default_rng(seed).choice(len(df), n, replace=False))
    return df.iloc[idx].reset_index(drop=True), truth[idx]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", required=True)
    ap.add_argument("--confirm", nargs="*", default=[])
    ap.add_argument("--labels", choices=["self", "truth"], default=None, help="default: blocking.dnf.labels")
    ap.add_argument("--out", required=True)
    ap.add_argument("--overlay", required=True, help="overlay YAML to write (strategy_source: learned)")
    a = ap.parse_args()
    cfg = load_config(use_last_best=False)
    dcfg = dict(cfg.blocking["dnf"])
    labels = a.labels or dcfg.get("labels", "self")
    seed = int(dcfg.get("sample_seed", 0))
    rng = np.random.default_rng(seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    df, truth, man = load_corpus(Path(a.train), cfg)
    sdf, struth = sample(df, truth, int(dcfg.get("sample_records", 20000)), seed)
    max_pos = int(dcfg.get("sample_positive_pairs", 5000))
    pos = truth_positives(struth, max_pos, rng) if labels == "truth" else self_label_positives(sdf, cfg.matcher, max_pos, rng)
    res = learn_dnf(sdf, pos, dcfg)
    # independent check of label quality on self-labels (how clean the bootstrap is) when truth is available
    label_purity = float(np.mean([struth[i] == struth[j] for i, j in pos])) if len(pos) else None
    truth_pos = truth_positives(struth, max_pos, np.random.default_rng(seed + 1))
    fixed_train = evaluate_strategies(sdf, truth_pos, cfg.blocking["strategies"])
    learned_train = evaluate_strategies(sdf, truth_pos, res.strategies) if res.strategies else None
    confirms = []
    for c in a.confirm:
        cdf, ctruth, cman = load_corpus(Path(c), cfg)
        csdf, cstruth = sample(cdf, ctruth, int(dcfg.get("sample_records", 20000)), seed + 7)
        cpos = truth_positives(cstruth, max_pos, np.random.default_rng(seed + 2))
        confirms.append({"corpus": Path(c).name, "seed": cman["config"]["seed"], "tier": cman["config"]["tier"],
                         "fixed": evaluate_strategies(csdf, cpos, cfg.blocking["strategies"]),
                         "learned": evaluate_strategies(csdf, cpos, res.strategies) if res.strategies else None})
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    overlay = {"blocking": {"strategy_source": "learned", "learned_strategies_file": str(Path(a.overlay).with_suffix(".strategies.yaml"))}}
    Path(a.overlay).parent.mkdir(parents=True, exist_ok=True)
    strategies_doc = {"generated_at": datetime.now(timezone.utc).isoformat(), "engine_commit": commit, "labels": labels,
                      "train_corpus": {"name": Path(a.train).name, "seed": man["config"]["seed"], "tier": man["config"]["tier"], "fingerprint": man["fingerprint"]},
                      "strategies": res.strategies}
    Path(overlay["blocking"]["learned_strategies_file"]).write_text(yaml.safe_dump(strategies_doc, sort_keys=False))
    Path(a.overlay).write_text(yaml.safe_dump(overlay, sort_keys=False))
    report = {"generated_at": strategies_doc["generated_at"], "engine_commit": commit, "labels": labels, "config": dcfg,
              "train": {"corpus": strategies_doc["train_corpus"], "records_sampled": int(len(sdf)), "positives": int(len(pos)), "label_purity_vs_truth": label_purity},
              "result": res.as_metrics(), "chosen": res.chosen,
              "predicates": [p.__dict__ for p in res.predicates],
              "comparison_train_truth_pairs": {"fixed": fixed_train, "learned": learned_train},
              "confirm": confirms, "wall_s": round(time.time() - t0, 1), "overlay": str(a.overlay)}
    (out / "dnf.json").write_text(json.dumps(report, indent=2, default=str))
    (out / "dnf.md").write_text(markdown(report))
    print(f"learned {len(res.strategies)} strategies, PC(train,{labels}) {res.pc:.3f}, cost {res.cost:,}/{res.budget:,}; fallback={res.fallback_reason}; wrote {out / 'dnf.md'} and {a.overlay}")
    return 0


def markdown(r: dict) -> str:
    L = [f"# Learned DNF blocking ({r['labels']} labels)", "",
         f"_Generated {r['generated_at']} · engine `{r['engine_commit']}` · trained on `{r['train']['corpus']['name']}` (tier {r['train']['corpus']['tier']}, seed {r['train']['corpus']['seed']}), {r['train']['records_sampled']:,} sampled records, {r['train']['positives']:,} positive pairs"
         + (f", self-label purity vs truth {r['train']['label_purity_vs_truth']:.3f}" if r['train']['label_purity_vs_truth'] is not None else "") + f" · wall {r['wall_s']} s_", "",
         f"Result: `{json.dumps(r['result'])}`", "",
         "## Chosen conjunctions (greedy red-blue set cover)", "", "| # | conjunction | PC | cost (sample pairs) | new positives | cumulative PC |", "|---|---|---|---|---|---|"]
    for i, c in enumerate(r["chosen"], 1):
        L.append(f"| {i} | " + " ∧ ".join(f"{t['attr']}.{t['transform']}" for t in c["terms"]) + f" | {c['pc']} | {c['cost']:,} | {c['new_pairs']} | {c['cum_pc']} |")
    L += ["", "## Unary predicates", "", "| attribute | transform | blocks | cost | PC | pruned |", "|---|---|---|---|---|---|"]
    for p in sorted(r["predicates"], key=lambda p: -p["pc"]):
        L.append(f"| {p['attr']} | {p['transform']} | {p['blocks']:,} | {p['cost']:,} | {p['pc']} | {p['pruned'] or ''} |")
    ct = r["comparison_train_truth_pairs"]
    L += ["", "## Learned vs fixed strategies (pairwise completeness on truth pairs / candidate pairs on the sample)", "",
          "| corpus | role | fixed PC | fixed cost | learned PC | learned cost |", "|---|---|---|---|---|---|",
          f"| {r['train']['corpus']['name']} | train | {ct['fixed']['pc']} | {ct['fixed']['cost']:,} | " + (f"{ct['learned']['pc']} | {ct['learned']['cost']:,} |" if ct["learned"] else "— | — |")]
    for c in r["confirm"]:
        L.append(f"| {c['corpus']} (seed {c['seed']}) | confirm | {c['fixed']['pc']} | {c['fixed']['cost']:,} | " + (f"{c['learned']['pc']} | {c['learned']['cost']:,} |" if c["learned"] else "— | — |"))
    if r["confirm"] and ct["learned"]:
        gaps = [round(ct["learned"]["pc"] - c["learned"]["pc"], 4) for c in r["confirm"] if c["learned"]]
        L += ["", f"Generalisation gap (train PC − confirm PC): {gaps}"]
    L += ["", f"Overlay written to `{r['overlay']}`; evaluate it on the reported tiers with the harness (`--cdp-config`).", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
