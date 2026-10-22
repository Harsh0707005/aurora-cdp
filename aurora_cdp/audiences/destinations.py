"""Destinations: CSV export and a JSON webhook (Amperity: destinations / orchestration, §4.2).

The webhook POSTs segment members as JSON. Defaults reproduce the original stub exactly (``dry_run=True``;
when sending, one payload with the first 1000 profiles); everything else is opt-in per destination:

* ``batch_size``   — deliver *every* profile in batches of this size (one POST per batch, ``batch_index`` /
                     ``batch_count`` in the payload);
* ``max_retries``  — retry a batch on 429 / 5xx / connection errors with exponential backoff
                     (``backoff_base * 2**attempt`` seconds, capped at ``backoff_max``); other HTTP errors fail
                     immediately; a batch that still fails is logged in ``destination_runs`` with status
                     ``failed`` and the error is raised so the pipeline step fails;
* ``headers``      — extra request headers (e.g. ``X-Api-Key``);
* ``auth_token_env`` — name of an environment variable whose value is sent as
                     ``<auth_header>: <auth_scheme> <token>`` (default ``Authorization: Bearer …``); the token is
                     read at send time and never logged or persisted;
* ``timeout``      — per-request timeout in seconds.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

log = logging.getLogger(__name__)

EXPORT_COLUMNS = [
    "aurora_id",
    "given_name",
    "surname",
    "email",
    "phone",
    "address",
    "city",
    "state",
    "postal",
    "country",
    "birthdate",
    "order_count",
    "total_spend",
    "last_order_ts",
    "datasources",
    "record_count",
]
RETRY_STATUSES = (429, 500, 502, 503, 504)
LEGACY_PAYLOAD_LIMIT = (
    1000  # the original stub sent at most this many profiles in its single payload
)
WEBHOOK_OPTIONS = (
    "batch_size",
    "max_retries",
    "backoff_base",
    "backoff_max",
    "headers",
    "auth_token_env",
    "auth_header",
    "auth_scheme",
    "timeout",
)


def _log(con, destination_id, segment_name, kind, target, rows, status):
    con.execute(
        "INSERT INTO destination_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
        [destination_id, segment_name, kind, target, rows, status, datetime.utcnow()],
    )


def export_csv(
    con: duckdb.DuckDBPyConnection,
    segment_name: str,
    members: pd.DataFrame,
    outputs_dir: str | Path,
) -> Path:
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    cols = [c for c in EXPORT_COLUMNS if c in members.columns]
    stamped = outputs_dir / f"{segment_name}_{stamp}.csv"
    latest = outputs_dir / f"{segment_name}.csv"
    members[cols].to_csv(stamped, index=False)
    members[cols].to_csv(latest, index=False)
    _log(con, uuid.uuid4().hex[:16], segment_name, "csv", str(stamped), len(members), "succeeded")
    return latest


FILE_FORMATS = ("csv", "jsonl", "parquet")


def export_file(
    con: duckdb.DuckDBPyConnection,
    segment_name: str,
    members: pd.DataFrame,
    outputs_dir: str | Path,
    fmt: str = "jsonl",
    columns: list[str] | None = None,
) -> Path:
    """File connector: ``jsonl`` (one profile per line) or ``parquet`` (columnar, for warehouses / S3 drops).
    Writes a timestamped file plus a ``<segment>.<fmt>`` "latest" copy, like :func:`export_csv`."""
    if fmt == "csv":
        return export_csv(con, segment_name, members, outputs_dir)
    if fmt not in FILE_FORMATS:
        raise ValueError(f"destination kind must be one of {FILE_FORMATS}, got {fmt!r}")
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    cols = [c for c in (columns or EXPORT_COLUMNS) if c in members.columns]
    frame = members[cols]
    stamped = outputs_dir / f"{segment_name}_{stamp}.{fmt}"
    latest = outputs_dir / f"{segment_name}.{fmt}"
    for target in (stamped, latest):
        if fmt == "jsonl":
            with target.open("w", encoding="utf-8") as fh:
                for rec in frame.to_dict(orient="records"):
                    fh.write(json.dumps(rec, default=str) + "\n")
        else:
            frame.to_parquet(target, index=False)
    _log(con, uuid.uuid4().hex[:16], segment_name, fmt, str(stamped), len(members), "succeeded")
    return latest


class WebhookDeliveryError(RuntimeError):
    """A webhook batch failed after the configured retries (or with a non-retryable error)."""

    def __init__(self, message: str, batch_index: int, attempts: int, status: int | None = None):
        super().__init__(message)
        self.batch_index = batch_index
        self.attempts = attempts
        self.status = status


def webhook_payloads(
    segment_name: str, members: pd.DataFrame, batch_size: int | None
) -> list[dict]:
    """JSON payloads for a segment: one legacy payload (first ``LEGACY_PAYLOAD_LIMIT`` profiles) when
    ``batch_size`` is None, otherwise every profile in batches of ``batch_size``."""
    cols = [c for c in EXPORT_COLUMNS if c in members.columns]
    records = members[cols].to_dict(orient="records")
    if not batch_size:
        return [
            {
                "segment": segment_name,
                "count": len(members),
                "profiles": records[:LEGACY_PAYLOAD_LIMIT],
            }
        ]
    size = max(1, int(batch_size))
    chunks = [records[i : i + size] for i in range(0, len(records), size)] or [[]]
    return [
        {
            "segment": segment_name,
            "count": len(members),
            "batch_index": i,
            "batch_count": len(chunks),
            "profiles": chunk,
        }
        for i, chunk in enumerate(chunks)
    ]


def webhook_headers(
    headers: dict[str, str] | None,
    auth_token_env: str | None,
    auth_header: str = "Authorization",
    auth_scheme: str | None = "Bearer",
) -> dict[str, str]:
    out = {
        "Content-Type": "application/json",
        **{str(k): str(v) for k, v in (headers or {}).items()},
    }
    if auth_token_env:
        token = os.environ.get(auth_token_env)
        if not token:
            raise ValueError(f"webhook auth: environment variable {auth_token_env!r} is not set")
        out[auth_header] = f"{auth_scheme} {token}" if auth_scheme else token
    return out


def _post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> int:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return int(resp.status)


def send_webhook(
    con: duckdb.DuckDBPyConnection,
    segment_name: str,
    members: pd.DataFrame,
    url: str,
    dry_run: bool = True,
    *,
    batch_size: int | None = None,
    max_retries: int = 0,
    backoff_base: float = 0.5,
    backoff_max: float = 30.0,
    headers: dict[str, str] | None = None,
    auth_token_env: str | None = None,
    auth_header: str = "Authorization",
    auth_scheme: str | None = "Bearer",
    timeout: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
    post: Callable[[str, bytes, dict[str, str], float], int] = _post,
) -> dict:
    """POST the segment to ``url`` (see the module docstring for the options). Returns a summary dict:
    ``status`` (``dry_run`` | ``http_<code>`` of the last batch), ``batches``, ``profiles_sent``, ``attempts``
    (total POSTs) and ``bytes``. ``sleep`` / ``post`` are injectable for tests."""
    payloads = webhook_payloads(segment_name, members, batch_size)
    bodies = [json.dumps(p, default=str).encode("utf-8") for p in payloads]
    total_bytes = sum(len(b) for b in bodies)
    profiles = sum(len(p["profiles"]) for p in payloads)
    destination_id = uuid.uuid4().hex[:16]
    if dry_run:
        _log(con, destination_id, segment_name, "webhook", url, len(members), "dry_run")
        return {
            "status": "dry_run",
            "bytes": total_bytes,
            "batches": len(payloads),
            "profiles_sent": 0,
            "profiles_in_payload": profiles,
            "attempts": 0,
        }
    hdrs = webhook_headers(headers, auth_token_env, auth_header, auth_scheme)
    attempts = 0
    last_status = 0
    sent = 0
    for i, body in enumerate(bodies):
        attempt = 0
        while True:
            attempts += 1
            try:
                last_status = post(url, body, hdrs, float(timeout))
                sent += len(payloads[i]["profiles"])
                break
            except urllib.error.HTTPError as exc:
                retryable = exc.code in RETRY_STATUSES
                reason: str = f"HTTP {exc.code}"
                status_code: int | None = int(exc.code)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                retryable = True
                reason = f"{type(exc).__name__}: {exc}"
                status_code = None
            if not retryable or attempt >= int(max_retries):
                _log(con, destination_id, segment_name, "webhook", url, sent, "failed")
                log.error(
                    "webhook %s batch %d/%d failed after %d attempt(s): %s",
                    url,
                    i + 1,
                    len(bodies),
                    attempt + 1,
                    reason,
                )
                raise WebhookDeliveryError(
                    f"webhook batch {i + 1}/{len(bodies)} to {url} failed after {attempt + 1} attempt(s): {reason}",
                    batch_index=i,
                    attempts=attempts,
                    status=status_code,
                )
            delay = min(float(backoff_max), float(backoff_base) * (2**attempt))
            log.warning(
                "webhook %s batch %d/%d: %s; retry %d/%d in %.1fs",
                url,
                i + 1,
                len(bodies),
                reason,
                attempt + 1,
                max_retries,
                delay,
            )
            sleep(delay)
            attempt += 1
    _log(con, destination_id, segment_name, "webhook", url, len(members), f"http_{last_status}")
    return {
        "status": f"http_{last_status}",
        "bytes": total_bytes,
        "batches": len(payloads),
        "profiles_sent": sent,
        "profiles_in_payload": profiles,
        "attempts": attempts,
    }
