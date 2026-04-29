"""Sentry initialization & configuration.

Goals:
- Capture unhandled exceptions in FastAPI handlers, scheduler tasks, webhooks.
- NOT send PII (passwords, tokens, full request bodies, full URLs with query params).
- Filter healthchecks and noisy 404/4xx that aren't actionable.
- Keep performance overhead minimal: 10% trace sampling by default, profiling off.

Usage: import & call init_sentry() once at server startup BEFORE creating the FastAPI app.
"""
import os
import logging
import re

logger = logging.getLogger(__name__)

# Endpoints to skip entirely (no events sent)
_HEALTH_PATHS = ("/api/health", "/health", "/api/widget/ping")

# Status codes that we don't want to track (client errors, expected business logic)
_IGNORE_STATUS_CODES = {400, 401, 403, 404, 422}

# Headers/query params that contain PII (will be scrubbed)
_PII_QUERY_KEYS = {"token", "access_token", "api_key", "password", "secret", "key"}
_PII_HEADERS = {"authorization", "cookie", "x-api-key", "x-auth-token"}


def _scrub_url(url: str) -> str:
    """Strip query params completamente para evitar leaks de tokens en URLs."""
    if not url or "?" not in url:
        return url
    return url.split("?", 1)[0]


def _scrub_headers(headers: dict) -> dict:
    """Mask PII headers (Authorization, Cookie, etc.)."""
    if not isinstance(headers, dict):
        return headers
    out = {}
    for k, v in headers.items():
        if k.lower() in _PII_HEADERS:
            out[k] = "[scrubbed]"
        else:
            out[k] = v
    return out


def _before_send(event, hint):
    """Hook que filtra/limpia cada evento antes de enviarlo a Sentry."""
    try:
        request = event.get("request") or {}
        url = request.get("url", "") or ""

        # Skip healthchecks
        for p in _HEALTH_PATHS:
            if url.endswith(p) or url.endswith(p + "/"):
                return None

        # Scrub URL & headers
        if url:
            request["url"] = _scrub_url(url)
        if "query_string" in request:
            request.pop("query_string", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = _scrub_headers(headers)
        elif isinstance(headers, list):
            # Sentry a veces manda como lista de tuples
            request["headers"] = [
                (k, "[scrubbed]" if k.lower() in _PII_HEADERS else v)
                for k, v in headers
            ]

        # Scrub user data (we don't want emails)
        if "user" in event:
            u = event["user"] or {}
            event["user"] = {"id": u.get("id")} if u.get("id") else {}

        # If response status is 4xx and not 5xx -> drop
        contexts = event.get("contexts", {}) or {}
        response_ctx = contexts.get("response") or {}
        status_code = response_ctx.get("status_code")
        if isinstance(status_code, int) and status_code in _IGNORE_STATUS_CODES:
            return None
    except Exception:
        # Si algo falla scrubbing, mejor dropear el evento que filtrar PII
        return None
    return event


def init_sentry():
    """Initialize Sentry SDK if SENTRY_DSN is set. No-op otherwise."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        logger.info("SENTRY_DSN no configurado — skip Sentry init")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.pymongo import PyMongoIntegration
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
    except Exception as e:
        logger.warning(f"sentry-sdk no instalado: {e}")
        return False

    env = os.environ.get("SENTRY_ENVIRONMENT", "production")
    traces = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1") or 0.1)
    profiles = float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.0") or 0.0)
    release = os.environ.get("SENTRY_RELEASE") or os.environ.get("APP_RELEASE")

    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        release=release,
        traces_sample_rate=traces,
        profiles_sample_rate=profiles,
        send_default_pii=False,
        attach_stacktrace=True,
        max_breadcrumbs=50,
        before_send=_before_send,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            PyMongoIntegration(),
            AsyncioIntegration(),
        ],
        # Reduce ruido: ignorar errores que no son nuestros
        ignore_errors=[
            "KeyboardInterrupt",
        ],
    )
    logger.info(
        f"✅ Sentry initialized (env={env}, traces={traces}, profiles={profiles})"
    )
    return True
