"""Minimal local scheduler: run a pipeline YAML every N seconds, append run history to runs.jsonl.

Amperity analogue: workflows / couriers on a schedule (§4.4). No APScheduler dependency; a plain loop.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from aurora_cdp.config import Config
from aurora_cdp.storage.duck import connection

from .pipeline import append_run_history, load_pipeline, run_pipeline

log = logging.getLogger(__name__)


def run_forever(cfg: Config, pipeline_path: str | Path, interval_seconds: int = 300, max_runs: int | None = None) -> int:
    spec = load_pipeline(pipeline_path)
    runs = 0
    while max_runs is None or runs < max_runs:
        with connection(cfg.db_path) as con:
            try:
                result = run_pipeline(con, cfg, spec)
            except Exception as exc:  # noqa: BLE001
                log.error("scheduled run failed: %s", exc)
                result = None
        if result is not None:
            path = append_run_history(cfg, result)
            log.info("%s (history: %s)", result.summary(), path)
        runs += 1
        if max_runs is not None and runs >= max_runs:
            break
        time.sleep(interval_seconds)
    return runs
