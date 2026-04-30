"""Iter26 - Structured logging (JSON) + Health endpoints.
- /api/health: shape correcto, mongo status, version, uptime, ?detailed=1
- /api/health/ping: ultra liviano
- X-Request-ID: respetado si viene del cliente, generado si no
- JsonFormatter: serialización correcta + extras + request_id propagation
"""
import os
import json
import logging
import io
import uuid

import pytest
import requests

from logging_config import (
    JsonFormatter,
    RequestLoggingMiddleware,
    setup_logging,
    get_request_id,
    _request_id_ctx,
)

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


# ============================================================
# /api/health — endpoint integration tests
# ============================================================

def test_health_basic_shape():
    r = requests.get(f"{BASE}/api/health", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mongo"] == "ok"
    assert "timestamp" in body and body["timestamp"].endswith("+00:00")
    assert body["version"]
    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0
    # Default sin ?detailed=1: NO debe incluir mongo_latency_ms
    assert "mongo_latency_ms" not in body


def test_health_detailed_includes_latency():
    r = requests.get(f"{BASE}/api/health?detailed=1", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "mongo_latency_ms" in body
    assert isinstance(body["mongo_latency_ms"], (int, float))
    assert body["mongo_latency_ms"] >= 0


def test_health_ping_lightweight():
    r = requests.get(f"{BASE}/api/health/ping", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert "timestamp" in body
    # No debe tocar mongo: shape minimalista
    assert "mongo" not in body
    assert "uptime_seconds" not in body


def test_health_returns_xrequestid_header():
    r = requests.get(f"{BASE}/api/health", timeout=10)
    assert "x-request-id" in {k.lower() for k in r.headers}
    rid = r.headers.get("x-request-id") or r.headers.get("X-Request-ID")
    # uuid hex truncado a 12 chars
    assert rid and len(rid) <= 64
    assert rid.isalnum()


def test_request_id_is_respected_when_provided():
    custom = "test-rid-" + uuid.uuid4().hex[:6]
    r = requests.get(
        f"{BASE}/api/health/ping",
        headers={"X-Request-ID": custom},
        timeout=10,
    )
    returned = r.headers.get("x-request-id") or r.headers.get("X-Request-ID")
    assert returned == custom


def test_request_id_truncated_when_too_long():
    huge = "x" * 200
    r = requests.get(
        f"{BASE}/api/health/ping",
        headers={"X-Request-ID": huge},
        timeout=10,
    )
    returned = r.headers.get("x-request-id") or r.headers.get("X-Request-ID")
    assert returned and len(returned) <= 64


def test_health_endpoints_not_rate_limited():
    # 50 pings rapidos sobre /api/health/ping no deben gatillar 429
    for _ in range(50):
        r = requests.get(f"{BASE}/api/health/ping", timeout=10)
        assert r.status_code == 200, f"Ping rate-limited: {r.status_code}"


# ============================================================
# JsonFormatter — unit tests
# ============================================================

def _format_with(handler_formatter, level, msg, **extra):
    record = logging.LogRecord(
        name="test", level=level, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return handler_formatter.format(record)


def test_json_formatter_basic_fields():
    fmt = JsonFormatter()
    out = _format_with(fmt, logging.INFO, "hello world")
    parsed = json.loads(out)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    assert parsed["service"] == "inmobot-backend"
    assert parsed["logger"] == "test"
    assert "timestamp" in parsed
    assert parsed["timestamp"].endswith("+00:00")


def test_json_formatter_includes_extras():
    fmt = JsonFormatter()
    out = _format_with(fmt, logging.WARNING, "tenant action",
                       tenant_id="abc", user_email="u@x.com", count=5)
    parsed = json.loads(out)
    assert parsed["tenant_id"] == "abc"
    assert parsed["user_email"] == "u@x.com"
    assert parsed["count"] == 5


def test_json_formatter_serializes_unjsonable_extra_as_str():
    fmt = JsonFormatter()
    class Weird:
        def __repr__(self):
            return "<Weird>"
    out = _format_with(fmt, logging.INFO, "msg", obj=Weird())
    parsed = json.loads(out)
    assert "Weird" in parsed["obj"]


def test_json_formatter_includes_exc_when_exception():
    fmt = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failure", args=(), exc_info=sys.exc_info(),
        )
        out = fmt.format(record)
    parsed = json.loads(out)
    assert "exc" in parsed
    assert "ValueError" in parsed["exc"]
    assert "boom" in parsed["exc"]


def test_json_formatter_includes_request_id_from_contextvar():
    fmt = JsonFormatter()
    token = _request_id_ctx.set("rid-xyz-123")
    try:
        out = _format_with(fmt, logging.INFO, "with rid")
    finally:
        _request_id_ctx.reset(token)
    parsed = json.loads(out)
    assert parsed["request_id"] == "rid-xyz-123"


def test_json_formatter_no_request_id_when_unset():
    fmt = JsonFormatter()
    # Asegurarse que ningun token este seteado
    _request_id_ctx.set(None)
    out = _format_with(fmt, logging.INFO, "no rid")
    parsed = json.loads(out)
    assert "request_id" not in parsed


# ============================================================
# setup_logging — idempotencia
# ============================================================

def test_setup_logging_idempotent():
    setup_logging()
    handlers_first = list(logging.getLogger().handlers)
    setup_logging()
    handlers_second = list(logging.getLogger().handlers)
    # Reemplaza handlers, no acumula
    assert len(handlers_second) == 1
    assert len(handlers_first) == 1


def test_setup_logging_text_mode_when_env_set(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "text")
    setup_logging()
    handler = logging.getLogger().handlers[0]
    assert not isinstance(handler.formatter, JsonFormatter)
    # Restore
    monkeypatch.setenv("LOG_FORMAT", "json")
    setup_logging()


def test_get_request_id_helper():
    token = _request_id_ctx.set("hello-rid")
    try:
        assert get_request_id() == "hello-rid"
    finally:
        _request_id_ctx.reset(token)
    assert get_request_id() is None
