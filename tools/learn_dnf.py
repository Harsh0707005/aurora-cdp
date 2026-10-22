#!/usr/bin/env python
"""Learn DNF blocking strategies and write them as the YAML that ``blocking.learned_strategies_file`` points at.

Input (exactly one):

    --train <corpus-dir>            evaluation corpus (profiles.parquet + truth.parquet + manifest.json)
    --csv <file.csv>                semantic columns (docs/interfaces.md §3: given_name, surname, email, phone,
                                    address, postal, birthdate, loy_id, ck, datasource, source_record_id|pk)
    --duckdb <db> --table <name>    the same semantic columns read from a DuckDB table / view

    tools/learn_dnf.py --csv records.csv --overlay configs/learned/dnf.yaml [--labels self|truth]
        [--truth-column truth_id] [--seed 0] [--config overlay.yaml] [--out reports/<date>/dnf] [--confirm <corpus-dir> ...]

* ``--labels self``  : label-free, the deterministic rules supply the positives (production setting; default).
* ``--labels truth`` : positives from an entity label per record (``--truth-column``, default ``truth_id``;
                       ``person_id`` for evaluation corpora) — evaluation only.

Outputs: the strategies YAML ``<overlay>.strategies.yaml`` (``{schema_version, generated_at, engine_commit,
labels, seed, train: {...}, strategies: [...]}``), the overlay ``<overlay>`` (``blocking.strategy_source: learned``
+ an **absolute** ``blocking.learned_strategies_file``) and, under ``--out`` (default ``<overlay dir>/<stem>-report``),
``dnf.json`` (predicate table with cost / pairwise completeness, chosen conjunctions, budget) and ``dnf.md``
(learned-vs-fixed comparison on the training sample and on every ``--confirm`` corpus).

Deterministic for a given input, config and ``--seed`` (sampling seed; the learner itself has no randomness).
Corpora used here must be seeds the reported evaluations never use (see docs/tuning.md).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from aurora_cdp.config import Config, load_config  # noqa: E402
from aurora_cdp.ingestion.normalize import (  # noqa: E402
    canonical_address,
    canonical_birthdate,
    canonical_email,
    canonical_given_name,
    canonical_name,
    canonical_phone,
    canonical_postal,
    load_nicknames,
)
from aurora_cdp.stitch.dnf import (  # noqa: E402
    derive_columns,
    evaluate_strategies,
    learn_dnf,
    self_label_positives,
    strategies_document,
    truth_positives,
)

SEMANTIC_COLUMNS = (
    "given_name",
    "surname",
    "email",
    "phone",
    "address",
    "postal",
    "birthdate",
    "loy_id",
    "ck",
)
CORPUS_COLUMN_MAP = {
    "first_name": "given_name",
    "last_name": "surname",
    "email": "email",
    "phone": "phone",
    "address": "address",
    "postal_code": "postal",
    "dob": "birthdate",
    "source": "datasource",
    "profile_id": "pk",
    "person_id": "truth_id",
}


def _nn(v):
    return None if v is None or (isinstance(v, float) and v != v) or v == "" else v


def frame_from_semantic(
    raw: pd.DataFrame, cfg: Config, truth_column: str | None
) -> tuple[pd.DataFrame, np.ndarray | None]:
    """Semantic-column records -> the normalised attribute frame the learner works on (+ optional truth labels)."""
    ncfg = cfg.normalize
    cols = {
        c: raw[c] if c in raw.columns else pd.Series([None] * len(raw), index=raw.index)
        for c in SEMANTIC_COLUMNS
    }
    pk = raw["pk"] if "pk" in raw.columns else raw["source_record_id"]
    ds = (
        raw["datasource"].astype(str)
        if "datasource" in raw.columns
        else pd.Series(["input"] * len(raw), index=raw.index)
    )
    nicknames = load_nicknames(ncfg.get("nickname_file"))
    abbr = ncfg.get("address_abbreviations")
    parse_addr = bool(ncfg.get("address_parsing", False))
    region = ncfg.get("default_region", "US")
    df = pd.DataFrame(
        {
            "datasource": ds.to_numpy(),
            "pk": pk.astype(str).to_numpy(),
            "given_name_norm": [_nn(canonical_name(_nn(v))) for v in cols["given_name"]],
            "given_name_canon": [
                _nn(canonical_given_name(_nn(v), nicknames)) for v in cols["given_name"]
            ],
            "surname_norm": [_nn(canonical_name(_nn(v))) for v in cols["surname"]],
            "email_norm": [_nn(canonical_email(_nn(v), ncfg)) for v in cols["email"]],
            "phone_match": [_nn(canonical_phone(_nn(v), region)[1]) for v in cols["phone"]],
            "address_norm": [
                _nn(canonical_address(_nn(v), abbr, parse_addr)) for v in cols["address"]
            ],
            "postal_norm": [_nn(canonical_postal(_nn(v))) for v in cols["postal"]],
            "birthdate_norm": [_nn(canonical_birthdate(_nn(v))) for v in cols["birthdate"]],
            "loy_id_norm": [
                (_nn(canonical_name(_nn(v))) or "").replace(" ", "") or None for v in cols["loy_id"]
            ],
            "ck": [_nn(v) for v in cols["ck"]],
        }
    )
    truth = None
    if truth_column and truth_column in raw.columns:
        truth = raw[truth_column].astype(str).to_numpy()
    return derive_columns(df), truth


def load_corpus(path: Path, cfg: Config) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """Evaluation corpus directory (profiles.parquet + truth.parquet + manifest.json)."""
    prof = pd.read_parquet(path / "profiles.parquet").merge(
        pd.read_parquet(path / "truth.parquet"), on="profile_id"
    )
    man = json.loads((path / "manifest.json").read_text())
    raw = prof.rename(columns=CORPUS_COLUMN_MAP)
    df, truth = frame_from_semantic(raw, cfg, "truth_id")
    assert truth is not None
    return df, truth, man


def load_input(a: argparse.Namespace, cfg: Config) -> tuple[pd.DataFrame, np.ndarray | None, dict]:
    """(frame, truth labels or None, description of the training input)."""
    if a.train:
        df, truth, man = load_corpus(Path(a.train), cfg)
        return (
            df,
            truth,
            {
                "kind": "corpus",
                "name": Path(a.train).name,
                "seed": man["config"]["seed"],
                "tier": man["config"]["tier"],
                "fingerprint": man["fingerprint"],
            },
        )
    if a.csv:
        raw = pd.read_csv(a.csv, dtype=str, keep_default_na=False).replace({"": None})
        df_csv, truth_csv = frame_from_semantic(raw, cfg, a.truth_column)
        return df_csv, truth_csv, {"kind": "csv", "name": str(Path(a.csv).resolve())}
    import duckdb

    con = duckdb.connect(a.duckdb, read_only=True)
    try:
        raw = con.execute(f"SELECT * FROM {a.table}").df()
    finally:
        con.close()
    raw = raw.astype(object).where(pd.notna(raw), None)
    df_db, truth_db = frame_from_semantic(raw, cfg, a.truth_column)
    return df_db, truth_db, {"kind": "duckdb", "name": f"{Path(a.duckdb).resolve()}::{a.table}"}


def sample(
    df: pd.DataFrame, truth: np.ndarray | None, n: int, seed: int
) -> tuple[pd.DataFrame, np.ndarray | None]:
    if len(df) <= n:
        return df.reset_index(drop=True), truth
    idx = np.sort(np.random.default_rng(seed).choice(len(df), n, replace=False))
    return df.iloc[idx].reset_index(drop=True), (truth[idx] if truth is not None else None)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--train", help="evaluation corpus directory")
    src.add_argument("--csv", help="CSV with semantic columns")
    src.add_argument("--duckdb", help="DuckDB database file (with --table)")
    ap.add_argument("--table", help="table/view in --duckdb")
    ap.add_argument(
        "--confirm",
        nargs="*",
        default=[],
        help="held-out corpus directories for the learned-vs-fixed report",
    )
    ap.add_argument(
        "--labels", choices=["self", "truth"], default=None, help="default: blocking.dnf.labels"
    )
    ap.add_argument(
        "--truth-column",
        default="truth_id",
        help="entity label column for --labels truth (csv/duckdb)",
    )
    ap.add_argument(
        "--seed", type=int, default=None, help="sampling seed (default: blocking.dnf.sample_seed)"
    )
    ap.add_argument(
        "--config",
        default=None,
        help="config overlay YAML (aurora.yaml format) applied over the defaults",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="report directory (default: <overlay dir>/<overlay stem>-report)",
    )
    ap.add_argument(
        "--overlay", required=True, help="overlay YAML to write (strategy_source: learned)"
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.duckdb and not a.table:
        raise SystemExit("--duckdb needs --table")
    cfg = load_config(a.config, use_last_best=False)
    dcfg = dict(cfg.blocking["dnf"])
    labels = a.labels or dcfg.get("labels", "self")
    seed = int(a.seed if a.seed is not None else dcfg.get("sample_seed", 0))
    rng = np.random.default_rng(seed)
    overlay_path = Path(a.overlay).resolve()
    out = Path(a.out) if a.out else overlay_path.parent / f"{overlay_path.stem}-report"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    df, truth, train_desc = load_input(a, cfg)
    if labels == "truth" and truth is None:
        raise SystemExit(
            f"--labels truth needs a {a.truth_column!r} column (or an evaluation corpus)"
        )
    sdf, struth = sample(df, truth, int(dcfg.get("sample_records", 20000)), seed)
    max_pos = int(dcfg.get("sample_positive_pairs", 5000))
    if labels == "truth":
        assert struth is not None
        pos = truth_positives(struth, max_pos, rng)
    else:
        pos = self_label_positives(sdf, cfg.matcher, max_pos, rng)
    res = learn_dnf(sdf, pos, dcfg)
    # independent check of label quality on self-labels (how clean the bootstrap is) when truth is available
    label_purity = (
        float(np.mean([struth[i] == struth[j] for i, j in pos]))
        if (len(pos) and struth is not None)
        else None
    )
    eval_pos = (
        truth_positives(struth, max_pos, np.random.default_rng(seed + 1))
        if struth is not None
        else pos
    )
    fixed_train = evaluate_strategies(sdf, eval_pos, cfg.blocking["strategies"])
    learned_train = evaluate_strategies(sdf, eval_pos, res.strategies) if res.strategies else None
    confirms = []
    for c in a.confirm:
        cdf, ctruth, cman = load_corpus(Path(c), cfg)
        csdf, cstruth = sample(cdf, ctruth, int(dcfg.get("sample_records", 20000)), seed + 7)
        assert cstruth is not None
        cpos = truth_positives(cstruth, max_pos, np.random.default_rng(seed + 2))
        confirms.append(
            {
                "corpus": Path(c).name,
                "seed": cman["config"]["seed"],
                "tier": cman["config"]["tier"],
                "fixed": evaluate_strategies(csdf, cpos, cfg.blocking["strategies"]),
                "learned": (
                    evaluate_strategies(csdf, cpos, res.strategies) if res.strategies else None
                ),
            }
        )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True
    ).stdout.strip()
    strategies_path = overlay_path.with_suffix(".strategies.yaml")
    overlay = {
        "blocking": {"strategy_source": "learned", "learned_strategies_file": str(strategies_path)}
    }
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    doc = strategies_document(
        res.strategies,
        generated_at=generated_at,
        engine_commit=commit,
        labels=labels,
        seed=seed,
        train={
            **train_desc,
            "records": int(len(df)),
            "records_sampled": int(len(sdf)),
            "positives": int(len(pos)),
        },
        fallback_reason=res.fallback_reason,
    )
    strategies_path.write_text(yaml.safe_dump(doc, sort_keys=False))
    overlay_path.write_text(yaml.safe_dump(overlay, sort_keys=False))
    report = {
        "generated_at": generated_at,
        "engine_commit": commit,
        "labels": labels,
        "seed": seed,
        "config": dcfg,
        "train": {
            "input": train_desc,
            "records_sampled": int(len(sdf)),
            "positives": int(len(pos)),
            "label_purity_vs_truth": label_purity,
        },
        "result": res.as_metrics(),
        "chosen": res.chosen,
        "predicates": [p.__dict__ for p in res.predicates],
        "comparison_train_pairs": {
            "fixed": fixed_train,
            "learned": learned_train,
            "pairs": "truth" if struth is not None else labels,
        },
        "confirm": confirms,
        "wall_s": round(time.time() - t0, 1),
        "overlay": str(overlay_path),
        "strategies_file": str(strategies_path),
    }
    (out / "dnf.json").write_text(json.dumps(report, indent=2, default=str))
    (out / "dnf.md").write_text(markdown(report))
    print(
        f"learned {len(res.strategies)} strategies, PC(train,{labels}) {res.pc:.3f}, cost {res.cost:,}/{res.budget:,}; "
        f"fallback={res.fallback_reason}; wrote {strategies_path}, {overlay_path} and {out / 'dnf.md'}"
    )
    return 0


def markdown(r: dict) -> str:
    tr = r["train"]
    name = tr["input"]["name"]
    L = [
        f"# Learned DNF blocking ({r['labels']} labels)",
        "",
        f"_Generated {r['generated_at']} · engine `{r['engine_commit']}` · seed {r['seed']} · trained on `{name}` ({tr['input']['kind']}"
        + (
            f", tier {tr['input']['tier']}, seed {tr['input']['seed']}"
            if tr["input"].get("tier")
            else ""
        )
        + f"), {tr['records_sampled']:,} sampled records, {tr['positives']:,} positive pairs"
        + (
            f", self-label purity vs truth {tr['label_purity_vs_truth']:.3f}"
            if tr["label_purity_vs_truth"] is not None
            else ""
        )
        + f" · wall {r['wall_s']} s_",
        "",
        f"Result: `{json.dumps(r['result'])}`",
        "",
        "## Chosen conjunctions (greedy red-blue set cover)",
        "",
        "| # | conjunction | PC | cost (sample pairs) | new positives | cumulative PC |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(r["chosen"], 1):
        L.append(
            f"| {i} | "
            + " ∧ ".join(f"{t['attr']}.{t['transform']}" for t in c["terms"])
            + f" | {c['pc']} | {c['cost']:,} | {c['new_pairs']} | {c['cum_pc']} |"
        )
    L += [
        "",
        "## Unary predicates",
        "",
        "| attribute | transform | blocks | cost | PC | pruned |",
        "|---|---|---|---|---|---|",
    ]
    for p in sorted(r["predicates"], key=lambda p: -p["pc"]):
        L.append(
            f"| {p['attr']} | {p['transform']} | {p['blocks']:,} | {p['cost']:,} | {p['pc']} | {p['pruned'] or ''} |"
        )
    ct = r["comparison_train_pairs"]
    L += [
        "",
        f"## Learned vs fixed strategies (pairwise completeness on {ct['pairs']} pairs / candidate pairs on the sample)",
        "",
        "| corpus | role | fixed PC | fixed cost | learned PC | learned cost |",
        "|---|---|---|---|---|---|",
        f"| {name} | train | {ct['fixed']['pc']} | {ct['fixed']['cost']:,} | "
        + (f"{ct['learned']['pc']} | {ct['learned']['cost']:,} |" if ct["learned"] else "— | — |"),
    ]
    for c in r["confirm"]:
        L.append(
            f"| {c['corpus']} (seed {c['seed']}) | confirm | {c['fixed']['pc']} | {c['fixed']['cost']:,} | "
            + (f"{c['learned']['pc']} | {c['learned']['cost']:,} |" if c["learned"] else "— | — |")
        )
    if r["confirm"] and ct["learned"]:
        gaps = [
            round(ct["learned"]["pc"] - c["learned"]["pc"], 4) for c in r["confirm"] if c["learned"]
        ]
        L += ["", f"Generalisation gap (train PC − confirm PC): {gaps}"]
    L += [
        "",
        f"Strategies written to `{r['strategies_file']}`, overlay to `{r['overlay']}`; evaluate it on the reported tiers with the harness (`--cdp-config`).",
        "",
    ]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
