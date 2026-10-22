"""Importable identity-resolution adapter with a fixed signature.

    from aurora_cdp.adapters import resolve_records
    result = resolve_records(records, config=None, previous=None)
    result.assignments   # DataFrame: source_record_id, unified_id, run_date, datasource, pk, cluster_id, run_id
    result.scores        # DataFrame: pair-level scores (all scored candidate pairs)
    result.metrics       # dict: run metrics incl. jitter

Also runnable as a module:  python -m aurora_cdp.adapters.resolver --input in.jsonl --output out.csv [--config aurora.yaml]
The CLI `aurora resolve ...` is the same code path. Contract: docs/interfaces.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from aurora_cdp.config import Config, load_config

ASSIGNMENT_COLUMNS = ["source_record_id", "unified_id", "run_date", "datasource", "pk", "cluster_id", "run_id"]
SCORE_COLUMNS = ["left_datasource", "left_record_id", "right_datasource", "right_record_id", "score", "match_category", "match_type", "is_edge"]


@dataclass
class ResolveResult:
    assignments: pd.DataFrame
    scores: pd.DataFrame
    metrics: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    @property
    def clusters(self) -> dict[str, list[str]]:
        """unified_id -> [source_record_id] (datasource-qualified as 'datasource|pk')."""
        out: dict[str, list[str]] = {}
        for r in self.assignments.itertuples(index=False):
            out.setdefault(r.unified_id, []).append(f"{r.datasource}|{r.pk}")
        return out

    def to_jsonl(self, path: str | Path) -> Path:
        path = Path(path)
        with path.open("w", encoding="utf-8") as fh:
            for r in self.assignments.to_dict(orient="records"):
                fh.write(json.dumps(r, default=str) + "\n")
        return path


def _as_frame(records: Any) -> pd.DataFrame:
    if isinstance(records, pd.DataFrame):
        df = records.copy()
    elif isinstance(records, (str, Path)):
        from aurora_cdp.ingestion.landing import read_any

        df = read_any(records)
    else:
        df = pd.DataFrame(list(records))
    df.columns = [str(c) for c in df.columns]
    if "source_record_id" not in df.columns and "pk" not in df.columns:
        raise ValueError("records need a 'source_record_id' (or 'pk') column")
    return df


def resolve_records(
    records: pd.DataFrame | list[dict] | str | Path,
    config: Config | dict | str | Path | None = None,
    previous: pd.DataFrame | str | Path | None = None,
    mapping: dict | str | Path | None = None,
    datasource: str = "input",
    threshold: float | None = None,
    workspace: str | Path | None = None,
) -> ResolveResult:
    """Resolve identities for a batch of source records. Pure function w.r.t. the caller's workspace:
    state lives in a temporary directory unless `workspace` is given.

    records : DataFrame / list of dicts / path (csv, parquet, jsonl, json). Columns: source_record_id (or pk),
              optional datasource, semantic columns (given_name, surname, email, phone, address, address2, city,
              state, postal, country, birthdate, loy_id, ck, update_dt, fk_<ns>) or raw columns + `mapping`.
    config  : Config, dict overrides, or path to an aurora.yaml overlay. None = packaged defaults.
    previous: prior assignments (DataFrame or file with unified_id + source_record_id[/datasource]) used to
              inherit stable IDs and compute churn.
    """
    import yaml

    from aurora_cdp.adapter import run_on_file

    if isinstance(config, Config):
        cfg = config
    elif isinstance(config, dict):
        cfg = load_config(overrides=config, use_last_best=False)
    elif config is not None:
        cfg = load_config(str(config), use_last_best=False)
    else:
        cfg = load_config(use_last_best=False)
    if threshold is not None:
        cfg = Config({**cfg, "matcher": {**cfg["matcher"], "match_threshold": float(threshold)}})

    tmp = Path(tempfile.mkdtemp(prefix="aurora-resolve-"))
    try:
        df = _as_frame(records)
        inp = tmp / "records.parquet"
        df.astype(object).where(pd.notnull(df), None).to_parquet(inp, index=False)
        prev_path = None
        if previous is not None:
            prev_path = tmp / "previous.csv"
            prev_df = previous if isinstance(previous, pd.DataFrame) else _as_frame(previous)
            if "unified_id" not in prev_df.columns:  # AmpID compatibility: accept the external id column
                for alt in ((cfg.get("identity") or {}).get("external_id_name", "amperity_id"), "aurora_id"):
                    if alt in prev_df.columns:
                        prev_df = prev_df.rename(columns={alt: "unified_id"})
                        break
            prev_df.to_csv(prev_path, index=False)
        map_path = None
        if mapping is not None:
            if isinstance(mapping, (str, Path)):
                map_path = Path(mapping)
            else:
                map_path = tmp / "mapping.yaml"
                map_path.write_text(yaml.safe_dump(mapping), encoding="utf-8")
        ws = Path(workspace) if workspace else tmp / "ws"
        out = run_on_file(
            cfg, inp, tmp / "assignments.csv", scores_out=tmp / "scores.csv", mapping_path=map_path,
            datasource=datasource, workspace=ws, keep_workspace=True, previous_assignments=prev_path,
        )
        assignments = pd.read_csv(tmp / "assignments.csv", dtype=str)
        scores = pd.read_csv(tmp / "scores.csv", dtype={"left_record_id": str, "right_record_id": str}) if (tmp / "scores.csv").exists() else pd.DataFrame(columns=SCORE_COLUMNS)
        extra = [c for c in assignments.columns if c not in ASSIGNMENT_COLUMNS]  # e.g. amperity_id (identity.ampid_mode)
        return ResolveResult(assignments[ASSIGNMENT_COLUMNS + extra], scores, out["metrics"], out["run_id"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def resolve_file(
    input_path: str | Path,
    output_path: str | Path,
    config: str | Path | None = None,
    scores_path: str | Path | None = None,
    previous: str | Path | None = None,
    mapping: str | Path | None = None,
    datasource: str = "input",
    threshold: float | None = None,
) -> ResolveResult:
    """File-in / file-out wrapper. Output format follows the extension: .csv, .parquet, .jsonl."""
    res = resolve_records(input_path, config, previous, mapping, datasource, threshold)
    _write(res.assignments, Path(output_path))
    if scores_path:
        _write(res.scores, Path(scores_path))
    return res


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suf = path.suffix.lower()
    if suf in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
    elif suf in {".jsonl", ".ndjson"}:
        with path.open("w", encoding="utf-8") as fh:
            for r in df.to_dict(orient="records"):
                fh.write(json.dumps(r, default=str) + "\n")
    else:
        df.to_csv(path, index=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aurora_cdp.adapters.resolver", description="Resolve identities for a file of source records.")
    ap.add_argument("--input", "-i", required=True, help="csv | parquet | jsonl | json")
    ap.add_argument("--output", "-o", required=True, help="assignments: csv | parquet | jsonl (by extension)")
    ap.add_argument("--config", "-c", default=None, help="aurora.yaml overlay")
    ap.add_argument("--scores", default=None, help="optional pair-level scores output")
    ap.add_argument("--previous", default=None, help="previous assignments for stable IDs / churn")
    ap.add_argument("--mapping", default=None, help="semantic mapping yaml for raw column names")
    ap.add_argument("--datasource", default="input")
    ap.add_argument("--threshold", type=float, default=None)
    args = ap.parse_args(argv)
    res = resolve_file(args.input, args.output, args.config, args.scores, args.previous, args.mapping, args.datasource, args.threshold)
    m = res.metrics
    print(
        f"resolved {len(res.assignments)} records -> clusters={m.get('clusters')} edges={m.get('edges')} "
        f"jitter={m.get('jitter', {}).get('jitter_pct')}% run={res.run_id} ; assignments -> {args.output}"
        + (f" ; scores -> {args.scores}" if args.scores else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
