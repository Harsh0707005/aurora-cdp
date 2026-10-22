"""FastAPI service: health, pipeline runs, metrics, profiles, clusters, change feed and a minimal UI.

Amperity analogues: Profile API (read-only profile lookup), Unified Changes feeds, Stitch QA dashboard.
DuckDB is single-writer: read endpoints open short-lived read-only connections; the run endpoint takes
the write lock for the duration of the pipeline run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import duckdb
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from aurora_cdp import __version__
from aurora_cdp.config import Config, load_config
from aurora_cdp.storage.duck import connect, init_schema, latest_run_id, read_df, table_exists

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))

app = FastAPI(title="Aurora CDP", version=__version__)


def get_config() -> Config:
    return load_config(os.environ.get("AURORA_CONFIG"))


def _open(cfg: Config, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    path = cfg.db_path
    if not path.exists():
        if read_only:
            raise HTTPException(status_code=503, detail=f"database not initialised: {path} (run `aurora init-db`)")
        con = connect(path)
        init_schema(con)
        return con
    try:
        return connect(path, read_only=read_only)
    except duckdb.IOException as exc:
        raise HTTPException(status_code=503, detail=f"database busy: {exc}") from exc


def _df_records(df) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


@app.get("/health")
def health() -> dict:
    cfg = get_config()
    return {"status": "ok", "version": __version__, "db": str(cfg.db_path), "db_exists": cfg.db_path.exists()}


class RunRequest(BaseModel):
    pipeline: str | None = None  # path to a pipeline YAML; defaults to <workspace>/pipeline.yaml
    mode: str | None = None  # override stitch mode: full | incremental


@app.post("/runs/pipeline")
def run_pipeline_endpoint(req: RunRequest) -> dict:
    from aurora_cdp.orchestration.pipeline import append_run_history, load_pipeline, run_pipeline

    cfg = get_config()
    path = Path(req.pipeline) if req.pipeline else cfg.workspace_path / "pipeline.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"pipeline file not found: {path}")
    spec = load_pipeline(path)
    if req.mode:
        spec["stitch"] = {"mode": req.mode}
    con = _open(cfg, read_only=False)
    try:
        result = run_pipeline(con, cfg, spec)
    finally:
        con.close()
    history = append_run_history(cfg, result)
    return {"summary": result.summary(), "history": str(history), **result.as_dict()}


@app.get("/metrics")
def metrics(run_id: str | None = None) -> dict:
    cfg = get_config()
    con = _open(cfg)
    try:
        if not table_exists(con, "stitch_runs"):
            raise HTTPException(status_code=404, detail="no runs")
        rid = run_id or latest_run_id(con)
        if rid is None:
            raise HTTPException(status_code=404, detail="no successful stitch run yet")
        row = con.execute(
            "SELECT run_id, mode, started_at, finished_at, status, metrics_json FROM stitch_runs WHERE run_id = ?", [rid]
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"run {rid} not found")
        jitter = read_df(con, "SELECT * FROM jitter_reports WHERE run_id = ?", [rid])
        return {
            "run_id": row[0], "mode": row[1], "started_at": str(row[2]), "finished_at": str(row[3]), "status": row[4],
            "metrics": json.loads(row[5]) if row[5] else {},
            "jitter": _df_records(jitter)[0] if len(jitter) else None,
        }
    finally:
        con.close()


@app.get("/runs")
def list_runs(limit: int = 20) -> list[dict]:
    cfg = get_config()
    con = _open(cfg)
    try:
        df = read_df(con, "SELECT run_id, mode, started_at, finished_at, status FROM stitch_runs ORDER BY started_at DESC LIMIT ?", [limit])
        return _df_records(df)
    finally:
        con.close()


@app.get("/profiles")
def list_profiles(limit: int = Query(50, le=1000), offset: int = 0, email: str | None = None, surname: str | None = None) -> dict:
    cfg = get_config()
    con = _open(cfg)
    try:
        where, params = ["TRUE"], []
        if email:
            where.append("lower(email) = lower(?)")
            params.append(email)
        if surname:
            where.append("upper(surname) = upper(?)")
            params.append(surname)
        total = con.execute(f"SELECT COUNT(*) FROM customer_360 WHERE {' AND '.join(where)}", params).fetchone()[0]
        df = read_df(con, f"SELECT * FROM customer_360 WHERE {' AND '.join(where)} ORDER BY aurora_id LIMIT ? OFFSET ?", [*params, limit, offset])
        return {"total": total, "limit": limit, "offset": offset, "profiles": _df_records(df)}
    finally:
        con.close()


@app.get("/profiles/{aurora_id}")
def get_profile(aurora_id: str) -> dict:
    cfg = get_config()
    con = _open(cfg)
    try:
        prof = read_df(con, "SELECT * FROM customer_360 WHERE aurora_id = ?", [aurora_id])
        if not len(prof):
            raise HTTPException(status_code=404, detail="profile not found")
        records = read_df(con, "SELECT * FROM unified_coalesced WHERE aurora_id = ? ORDER BY datasource, pk", [aurora_id])
        events = read_df(con, "SELECT event_type, event_ts, amount, datasource, fk_value FROM gold_profile_events WHERE aurora_id = ? ORDER BY event_ts DESC LIMIT 200", [aurora_id])
        history = read_df(con, "SELECT run_id, aurora_id_prev, change_type, changed_at FROM unified_changes_clusters WHERE aurora_id = ? ORDER BY changed_at", [aurora_id])
        p = _df_records(prof)[0]
        p["provenance"] = json.loads(p.pop("provenance_json") or "{}")
        return {"profile": p, "records": _df_records(records), "events": _df_records(events), "id_history": _df_records(history)}
    finally:
        con.close()


@app.get("/clusters/{aurora_id}")
def get_cluster(aurora_id: str, run_id: str | None = None) -> dict:
    cfg = get_config()
    con = _open(cfg)
    try:
        rid = run_id or latest_run_id(con)
        members = read_df(con, "SELECT datasource, pk, cluster_id, component_id, supersized_id, is_supersized FROM stitch_clusters WHERE run_id = ? AND aurora_id = ? ORDER BY datasource, pk", [rid, aurora_id])
        if not len(members):
            raise HTTPException(status_code=404, detail="cluster not found for run")
        keys = members[["datasource", "pk"]].itertuples(index=False)
        key_set = {(d, p) for d, p in keys}
        scores = read_df(
            con,
            "SELECT left_datasource, left_pk, right_datasource, right_pk, score, match_category, match_type, is_edge FROM stitch_scores WHERE run_id = ?",
            [rid],
        )
        if len(scores):
            mask = [((a, b) in key_set) and ((c, d) in key_set) for a, b, c, d in scores[["left_datasource", "left_pk", "right_datasource", "right_pk"]].itertuples(index=False)]
            scores = scores[mask]
        return {"run_id": rid, "aurora_id": aurora_id, "members": _df_records(members), "scores": _df_records(scores)}
    finally:
        con.close()


@app.get("/changes")
def changes(run_id: str | None = None, level: str = "pk", limit: int = Query(500, le=10000)) -> dict:
    cfg = get_config()
    con = _open(cfg)
    try:
        rid = run_id or latest_run_id(con)
        table = "unified_changes_pk" if level == "pk" else "unified_changes_clusters"
        df = read_df(con, f"SELECT * FROM {table} WHERE run_id = ? ORDER BY changed_at LIMIT ?", [rid, limit])
        return {"run_id": rid, "level": level, "changes": _df_records(df)}
    finally:
        con.close()


@app.get("/segments")
def segments() -> list[dict]:
    cfg = get_config()
    con = _open(cfg)
    try:
        df = read_df(
            con,
            "SELECT s.segment_name, s.definition_json, s.updated_at, COUNT(m.aurora_id) AS members FROM segments s LEFT JOIN segment_members m USING (segment_name) GROUP BY ALL ORDER BY s.segment_name",
        )
        out = _df_records(df)
        for row in out:
            row["definition"] = json.loads(row.pop("definition_json"))
        return out
    finally:
        con.close()


# ------------------------------------------------------------------------------------------------
# Minimal UI
# ------------------------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
def dashboard(request: Request):
    cfg = get_config()
    ctx: dict[str, Any] = {"request": request, "version": __version__, "runs": [], "metrics": None, "jitter": None, "segments": [], "profiles_total": 0}
    if cfg.db_path.exists():
        con = _open(cfg)
        try:
            ctx["runs"] = _df_records(read_df(con, "SELECT run_id, mode, started_at, status FROM stitch_runs ORDER BY started_at DESC LIMIT 10"))
            rid = latest_run_id(con)
            if rid:
                row = con.execute("SELECT metrics_json FROM stitch_runs WHERE run_id = ?", [rid]).fetchone()
                ctx["metrics"] = json.loads(row[0]) if row and row[0] else None
                ctx["run_id"] = rid
                j = read_df(con, "SELECT * FROM jitter_reports WHERE run_id = ?", [rid])
                ctx["jitter"] = _df_records(j)[0] if len(j) else None
            ctx["profiles_total"] = con.execute("SELECT COUNT(*) FROM customer_360").fetchone()[0]
            ctx["segments"] = segments()
            ctx["largest"] = _df_records(read_df(con, "SELECT aurora_id, COUNT(*) AS n FROM stitch_clusters WHERE run_id = ? GROUP BY aurora_id ORDER BY n DESC, aurora_id LIMIT 10", [rid])) if rid else []
        finally:
            con.close()
    return TEMPLATES.TemplateResponse(request, "dashboard.html", ctx)


@app.get("/ui/clusters/{aurora_id}", response_class=HTMLResponse)
def cluster_review(request: Request, aurora_id: str):
    data = get_cluster(aurora_id)
    profile = None
    try:
        profile = get_profile(aurora_id)
    except HTTPException:
        pass
    return TEMPLATES.TemplateResponse(request, "cluster.html", {"aurora_id": aurora_id, "cluster": data, "profile": profile})
