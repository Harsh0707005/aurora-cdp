"""YAML-defined pipeline DAG: databases -> feeds -> stitch -> profile -> segments -> destinations.

Pipeline file format (see .aurora/demo/pipeline.yaml written by the demo):

    name: demo
    databases: [init]                       # schema init (Amperity: database build)
    feeds:
      - source: crm
        feed: customers
        path: .aurora/demo/crm_customers.csv
        load_mode: full                     # full | incremental
        semantics: {pk: customer_id, fields: {...}, fk: {...}}
    stitch: {mode: full}
    profile: true
    segments:
      - {name: ..., filters: [...]}
    destinations:
      - {segment: ..., kind: csv}
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb
import yaml

from aurora_cdp.audiences.destinations import FILE_FORMATS, WEBHOOK_OPTIONS, export_csv, export_file, send_webhook
from aurora_cdp.audiences.segmenter import evaluate_segment, save_segment
from aurora_cdp.config import Config
from aurora_cdp.ingestion.landing import ingest_file, landing_frame
from aurora_cdp.ingestion.normalize import preprocess_records
from aurora_cdp.ingestion.semantics import apply_semantics
from aurora_cdp.profile.builder import build_profiles
from aurora_cdp.stitch.run import run_stitch
from aurora_cdp.storage.duck import init_schema, write_df

log = logging.getLogger(__name__)

STEP_ORDER = ["databases", "feeds", "stitch", "profile", "households", "segments", "destinations"]


@dataclass
class PipelineResult:
    name: str
    started_at: datetime
    steps: list[dict] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    stitch_run_id: str | None = None
    metrics: dict = field(default_factory=dict)

    def summary(self) -> str:
        ok = sum(1 for s in self.steps if s["status"] == "ok")
        return f"pipeline '{self.name}': {ok}/{len(self.steps)} steps ok, stitch_run={self.stitch_run_id}, outputs={len(self.outputs)}"

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "steps": self.steps,
            "outputs": self.outputs,
            "stitch_run_id": self.stitch_run_id,
            "metrics": self.metrics,
        }


def load_pipeline(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def tag_feed(
    con: duckdb.DuckDBPyConnection, cfg: Config, source: str, feed: str, semantics: dict
) -> int:
    """Rebuild silver rows for a source from its current bronze rows (semantic tagging + preprocessing)."""
    df = landing_frame(con, source, feed)
    raw = apply_semantics(df, source, semantics)
    con.execute("DELETE FROM silver_unified_raw WHERE datasource = ?", [source])
    con.execute("DELETE FROM silver_unified_preprocessed WHERE datasource = ?", [source])
    if raw.empty:
        return 0
    write_df(con, "silver_unified_raw", raw)
    pre = preprocess_records(raw, cfg)
    write_df(con, "silver_unified_preprocessed", pre)
    return len(raw)


def run_pipeline(con: duckdb.DuckDBPyConnection, cfg: Config, spec: dict) -> PipelineResult:
    result = PipelineResult(name=spec.get("name", "pipeline"), started_at=datetime.utcnow())

    def step(name: str, fn):
        t = time.perf_counter()
        try:
            detail = fn()
            result.steps.append(
                {
                    "step": name,
                    "status": "ok",
                    "seconds": round(time.perf_counter() - t, 3),
                    "detail": detail,
                }
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("pipeline step %s failed", name)
            result.steps.append(
                {
                    "step": name,
                    "status": "failed",
                    "seconds": round(time.perf_counter() - t, 3),
                    "detail": str(exc),
                }
            )
            raise

    if spec.get("databases"):
        step("databases", lambda: {"applied_versions": init_schema(con)})

    for feed in spec.get("feeds", []):

        def _ingest(feed=feed):
            r = ingest_file(
                con,
                feed["path"],
                feed["source"],
                feed["feed"],
                feed.get("load_mode", "incremental"),
            )
            tagged = 0
            if feed.get("semantics"):
                tagged = tag_feed(con, cfg, feed["source"], feed["feed"], feed["semantics"])
            return {
                "batch_id": r.batch_id,
                "rows_loaded": r.rows_loaded,
                "rows_deduped": r.rows_deduped,
                "tagged": tagged,
            }

        step(f"feed:{feed['source']}/{feed['feed']}", _ingest)

    if spec.get("stitch"):
        mode = (
            (spec["stitch"] or {}).get("mode", "full")
            if isinstance(spec["stitch"], dict)
            else "full"
        )

        def _stitch():
            r = run_stitch(con, cfg, mode=mode)
            result.stitch_run_id = r.run_id
            result.metrics = r.metrics
            return {
                "run_id": r.run_id,
                "clusters": r.metrics["clusters"],
                "jitter_pct": r.metrics["jitter"].get("jitter_pct"),
            }

        step("stitch", _stitch)

    if spec.get("profile"):
        step("profile", lambda: build_profiles(con, cfg).__dict__)

    if spec.get("households", (cfg.get("household") or {}).get("build_with_profile", True) and bool(spec.get("profile"))):
        from aurora_cdp.profile.households import build_households

        step("households", lambda: build_households(con, cfg).metrics)

    for seg in spec.get("segments", []):

        def _seg(seg=seg):
            save_segment(con, seg)
            return {"name": seg["name"], "members": len(evaluate_segment(con, seg).members)}

        step(f"segment:{seg['name']}", _seg)

    for dest in spec.get("destinations", []):

        def _dest(dest=dest):
            from aurora_cdp.audiences.segmenter import load_segment

            seg = load_segment(con, dest["segment"])
            members = evaluate_segment(con, seg, persist=False).members
            kind = dest.get("kind", "csv")
            if kind in FILE_FORMATS:
                path = export_file(
                    con, dest["segment"], members, dest.get("dir") or cfg.outputs_path, kind, dest.get("columns")
                )
                result.outputs.append(str(path))
                return {"path": str(path), "rows": len(members)}
            if kind != "webhook":
                raise ValueError(f"destination kind must be one of {FILE_FORMATS + ('webhook',)}, got {kind!r}")
            options = {k: dest[k] for k in WEBHOOK_OPTIONS if k in dest}
            return send_webhook(
                con,
                dest["segment"],
                members,
                dest["url"],
                dry_run=dest.get("dry_run", True),
                **options,
            )

        step(f"destination:{dest['segment']}", _dest)

    return result


def append_run_history(cfg: Config, result: PipelineResult) -> Path:
    path = cfg.workspace_path / "runs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result.as_dict(), default=str) + "\n")
    return path
