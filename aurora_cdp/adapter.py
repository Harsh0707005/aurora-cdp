"""Scoring-harness adapter: run Stitch on an arbitrary input file and emit an assignment table.

Contract (docs/adapter-contract.md):
  aurora stitch run --input records.csv --out assignments.csv [--scores-out scores.csv] [--mapping map.yaml]
Input: CSV/Parquet with one row per source record. Columns are either already semantic
(source_record_id or pk, optional datasource, given_name, surname, email, phone, address, address2, city,
state, postal, country, birthdate, loy_id, ck, update_dt, fk_<namespace>...) or mapped via --mapping.
Output: source_record_id, unified_id, run_date, datasource, pk, cluster_id, run_id.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from aurora_cdp.config import Config
from aurora_cdp.ingestion.landing import ingest_frame, landing_frame, read_any
from aurora_cdp.ingestion.normalize import preprocess_records
from aurora_cdp.ingestion.semantics import PROFILE_SEMANTICS, apply_semantics
from aurora_cdp.stitch.run import run_stitch
from aurora_cdp.storage.duck import connect, init_schema, read_df, write_df

ASSIGNMENT_COLUMNS = ["source_record_id", "unified_id", "run_date", "datasource", "pk", "cluster_id", "run_id"]


def default_mapping(columns: list[str]) -> dict:
    """Identity mapping for inputs that already use semantic column names."""
    pk = "source_record_id" if "source_record_id" in columns else "pk"
    fields = {c: c for c in columns if c in PROFILE_SEMANTICS}
    if "update_dt" in columns:
        fields["update_dt"] = "update_dt"
    fk = {c: c.removeprefix("fk_").removeprefix("fk-") for c in columns if c.startswith(("fk_", "fk-"))}
    return {"pk": pk, "ck": "ck" if "ck" in columns else None, "fields": fields, "fk": fk}


def run_on_file(
    cfg: Config,
    input_path: str | Path,
    out_path: str | Path,
    scores_out: str | Path | None = None,
    mapping_path: str | Path | None = None,
    datasource: str = "input",
    workspace: str | Path | None = None,
    keep_workspace: bool = False,
    previous_assignments: str | Path | None = None,
) -> dict:
    """Stitch a standalone file in a throwaway workspace and write the assignment table."""
    input_path = Path(input_path)
    ws = Path(workspace) if workspace else cfg.workspace_path / "adapter" / datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    ws.mkdir(parents=True, exist_ok=True)
    df = read_any(input_path)
    df.columns = [str(c) for c in df.columns]
    mapping = yaml.safe_load(Path(mapping_path).read_text(encoding="utf-8")) if mapping_path else default_mapping(list(df.columns))
    con = connect(ws / "adapter.duckdb")
    try:
        init_schema(con)
        if previous_assignments:
            _seed_ledger(con, Path(previous_assignments))
        sources = sorted(df["datasource"].unique()) if "datasource" in df.columns else [datasource]
        for src in sources:
            part = df[df["datasource"] == src] if "datasource" in df.columns else df
            ingest_frame(con, part.drop(columns=[c for c in ["datasource"] if c in part.columns]), src, "records", "full", str(input_path))
            raw = apply_semantics(landing_frame(con, src, "records"), src, mapping)
            write_df(con, "silver_unified_raw", raw)
            write_df(con, "silver_unified_preprocessed", preprocess_records(raw, cfg))
        result = run_stitch(con, cfg, mode="full")
        assign = read_df(
            con,
            "SELECT pk AS source_record_id, aurora_id AS unified_id, datasource, pk, cluster_id, run_id FROM stitch_clusters WHERE run_id = ? ORDER BY datasource, pk",
            [result.run_id],
        )
        assign["run_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        assign = assign[ASSIGNMENT_COLUMNS]
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write(assign, out_path)
        written = {"assignments": str(out_path), "rows": int(len(assign)), "run_id": result.run_id, "metrics": result.metrics}
        if scores_out:
            scores = read_df(
                con,
                "SELECT left_datasource, left_pk AS left_record_id, right_datasource, right_pk AS right_record_id, score, match_category, match_type, is_edge FROM stitch_scores WHERE run_id = ? ORDER BY score DESC",
                [result.run_id],
            )
            _write(scores, Path(scores_out))
            written["scores"] = str(scores_out)
            written["score_rows"] = int(len(scores))
    finally:
        con.close()
    if not keep_workspace and not workspace:
        shutil.rmtree(ws, ignore_errors=True)
    return written


def _seed_ledger(con, path: Path) -> None:
    """Seed id_ledger from a previous assignment table so stable IDs / jitter are computed across runs."""
    prev = read_any(path)
    cols = {c.lower(): c for c in prev.columns}
    ledger = pd.DataFrame(
        {
            "aurora_id": prev[cols["unified_id"]].astype(str),
            "datasource": prev[cols["datasource"]].astype(str) if "datasource" in cols else "input",
            "pk": prev[cols.get("source_record_id", cols.get("pk"))].astype(str),
            "run_id": "seed",
            "valid_from": datetime.utcnow(),
            "valid_to": None,
            "is_current": True,
        }
    )
    write_df(con, "id_ledger", ledger)
    con.execute("INSERT INTO stitch_runs (run_id, mode, started_at, finished_at, status) VALUES ('seed', 'full', ?, ?, 'succeeded')", [datetime(1970, 1, 1), datetime(1970, 1, 1)])


def export_assignments(cfg: Config, out_path: str | Path, run_id: str | None = None, scores_out: str | Path | None = None) -> dict:
    """Export the assignment table for a run from the main workspace DB."""
    from aurora_cdp.storage.duck import latest_run_id

    con = connect(cfg.db_path, read_only=True)
    try:
        rid = run_id or latest_run_id(con)
        if rid is None:
            raise RuntimeError("no successful stitch run in workspace")
        run_date = con.execute("SELECT started_at FROM stitch_runs WHERE run_id = ?", [rid]).fetchone()[0]
        assign = read_df(
            con,
            "SELECT pk AS source_record_id, aurora_id AS unified_id, datasource, pk, cluster_id, run_id FROM stitch_clusters WHERE run_id = ? ORDER BY datasource, pk",
            [rid],
        )
        assign["run_date"] = pd.Timestamp(run_date).strftime("%Y-%m-%d")
        assign = assign[ASSIGNMENT_COLUMNS]
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write(assign, out_path)
        out = {"assignments": str(out_path), "rows": int(len(assign)), "run_id": rid}
        if scores_out:
            scores = read_df(
                con,
                "SELECT left_datasource, left_pk AS left_record_id, right_datasource, right_pk AS right_record_id, score, match_category, match_type, is_edge FROM stitch_scores WHERE run_id = ? ORDER BY score DESC",
                [rid],
            )
            _write(scores, Path(scores_out))
            out["scores"] = str(scores_out)
        return out
    finally:
        con.close()


def _write(df: pd.DataFrame, path: Path) -> None:
    if path.suffix.lower() in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
