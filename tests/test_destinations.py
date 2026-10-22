"""Webhook destination: legacy single payload by default, opt-in batching, retries with backoff, auth headers,
failure logging; exercised against a local HTTP server on a loopback port."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import duckdb
import pandas as pd
import pytest

from aurora_cdp.audiences.destinations import (
    LEGACY_PAYLOAD_LIMIT,
    WEBHOOK_OPTIONS,
    WebhookDeliveryError,
    send_webhook,
    webhook_headers,
    webhook_payloads,
)
from aurora_cdp.storage.duck import init_schema


class _Server:
    """Records every request; answers with the next status from ``plan`` (default 200)."""

    def __init__(self, plan: list[int] | None = None):
        self.requests: list[dict] = []
        self.plan = list(plan or [])
        srv = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n)
                srv.requests.append(
                    {"headers": {k: v for k, v in self.headers.items()}, "body": json.loads(body)}
                )
                status = srv.plan.pop(0) if srv.plan else 200
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):  # silence
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/hook"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def server():
    s = _Server()
    yield s
    s.close()


@pytest.fixture()
def con():
    c = duckdb.connect(":memory:")
    init_schema(c)
    return c


def _members(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "aurora_id": [f"id{i}" for i in range(n)],
            "email": [f"u{i}@x.org" for i in range(n)],
            "junk": 1,
        }
    )


def _runs(con):
    return con.execute(
        "SELECT kind, row_count, status FROM destination_runs ORDER BY created_at"
    ).fetchall()


def test_payloads_legacy_and_batched():
    m = _members(5)
    legacy = webhook_payloads("seg", m, None)
    assert (
        len(legacy) == 1
        and legacy[0]["count"] == 5
        and len(legacy[0]["profiles"]) == 5
        and "batch_index" not in legacy[0]
    )
    assert set(legacy[0]["profiles"][0]) == {"aurora_id", "email"}, "only export columns are sent"
    big = webhook_payloads("seg", _members(LEGACY_PAYLOAD_LIMIT + 5), None)
    assert (
        len(big[0]["profiles"]) == LEGACY_PAYLOAD_LIMIT
        and big[0]["count"] == LEGACY_PAYLOAD_LIMIT + 5
    )
    batched = webhook_payloads("seg", m, 2)
    assert [len(p["profiles"]) for p in batched] == [2, 2, 1]
    assert [p["batch_index"] for p in batched] == [0, 1, 2] and all(
        p["batch_count"] == 3 for p in batched
    )
    assert webhook_payloads("seg", _members(0), 2)[0]["profiles"] == []


def test_headers_and_auth_token(monkeypatch):
    assert webhook_headers(None, None) == {"Content-Type": "application/json"}
    monkeypatch.setenv("HOOK_TOKEN", "s3cret")
    h = webhook_headers({"X-Api-Key": "k"}, "HOOK_TOKEN")
    assert h["Authorization"] == "Bearer s3cret" and h["X-Api-Key"] == "k"
    assert webhook_headers(None, "HOOK_TOKEN", "X-Token", None)["X-Token"] == "s3cret"
    monkeypatch.delenv("HOOK_TOKEN")
    with pytest.raises(ValueError, match="HOOK_TOKEN"):
        webhook_headers(None, "HOOK_TOKEN")


def test_dry_run_default_sends_nothing(con, server):
    out = send_webhook(con, "seg", _members(3), server.url)
    assert (
        out["status"] == "dry_run"
        and out["batches"] == 1
        and out["profiles_sent"] == 0
        and out["attempts"] == 0
    )
    assert server.requests == [] and _runs(con) == [("webhook", 3, "dry_run")]


def test_send_legacy_single_payload(con, server, monkeypatch):
    monkeypatch.setenv("HOOK_TOKEN", "t0k")
    out = send_webhook(
        con,
        "seg",
        _members(3),
        server.url,
        dry_run=False,
        auth_token_env="HOOK_TOKEN",
        headers={"X-Api-Key": "k"},
    )
    assert (
        out["status"] == "http_200"
        and out["batches"] == 1
        and out["profiles_sent"] == 3
        and out["attempts"] == 1
    )
    assert len(server.requests) == 1
    req = server.requests[0]
    assert req["headers"]["Authorization"] == "Bearer t0k" and req["headers"]["X-Api-Key"] == "k"
    assert req["headers"]["Content-Type"] == "application/json" and req["body"]["count"] == 3
    assert _runs(con) == [("webhook", 3, "http_200")]


def test_batching_and_retry_with_backoff(con):
    srv = _Server(
        plan=[503, 200, 429, 429, 200, 200]
    )  # batch 0: fail, ok; batch 1: fail, fail, ok; batch 2: ok
    try:
        delays: list[float] = []
        out = send_webhook(
            con,
            "seg",
            _members(5),
            srv.url,
            dry_run=False,
            batch_size=2,
            max_retries=2,
            backoff_base=0.1,
            backoff_max=0.15,
            sleep=delays.append,
        )
        assert (
            out["status"] == "http_200"
            and out["batches"] == 3
            and out["profiles_sent"] == 5
            and out["attempts"] == 6
        )
        assert delays == [0.1, 0.1, 0.15], "exponential backoff capped at backoff_max"
        bodies = [r["body"] for r in srv.requests]
        assert [b["batch_index"] for b in bodies] == [0, 0, 1, 1, 1, 2]
        assert bodies[0] == bodies[1], "a retried batch is re-sent unchanged"
        assert _runs(con) == [("webhook", 5, "http_200")]
    finally:
        srv.close()


def test_exhausted_retries_and_non_retryable_errors_fail_loudly(con):
    srv = _Server(plan=[503, 503, 200, 400])
    try:
        with pytest.raises(WebhookDeliveryError) as exc:
            send_webhook(
                con,
                "seg",
                _members(4),
                srv.url,
                dry_run=False,
                batch_size=2,
                max_retries=1,
                sleep=lambda _d: None,
            )
        assert exc.value.batch_index == 0 and exc.value.attempts == 2 and exc.value.status == 503
        assert _runs(con) == [("webhook", 0, "failed")]
        with pytest.raises(
            WebhookDeliveryError
        ) as exc2:  # 200 for batch 0, then a 400 is not retried
            send_webhook(
                con,
                "seg",
                _members(4),
                srv.url,
                dry_run=False,
                batch_size=2,
                max_retries=3,
                sleep=lambda _d: None,
            )
        assert exc2.value.batch_index == 1 and exc2.value.attempts == 2 and exc2.value.status == 400
        assert _runs(con)[-1] == (
            "webhook",
            2,
            "failed",
        ), "profiles delivered before the failure are recorded"
    finally:
        srv.close()


def test_connection_error_is_retried_then_raised(con):
    calls: list[int] = []

    def flaky(url, body, headers, timeout):
        calls.append(1)
        raise ConnectionError("refused")

    with pytest.raises(WebhookDeliveryError, match="ConnectionError"):
        send_webhook(
            con,
            "seg",
            _members(1),
            "http://127.0.0.1:9/x",
            dry_run=False,
            max_retries=2,
            sleep=lambda _d: None,
            post=flaky,
        )
    assert len(calls) == 3


def test_pipeline_passes_webhook_options_through():
    from aurora_cdp.orchestration import pipeline

    src = open(pipeline.__file__, encoding="utf-8").read()
    assert "WEBHOOK_OPTIONS" in src and {
        "batch_size",
        "max_retries",
        "headers",
        "auth_token_env",
        "timeout",
    } <= set(WEBHOOK_OPTIONS)
