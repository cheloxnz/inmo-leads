"""Logging estructurado en JSON para producción.

- JsonFormatter: emite cada record como una línea JSON parseable
  (Datadog/ELK/CloudWatch friendly).
- RequestLoggingMiddleware: agrega un `request_id` por request, lo expone en
  el header `X-Request-ID` y emite un log estructurado de acceso al final.
- setup_logging(): aplica el formatter al root logger y a uvicorn.

Uso:
    from logging_config import setup_logging, RequestLoggingMiddleware
    setup_logging()                          # antes de instanciar FastAPI
    app.add_middleware(RequestLoggingMiddleware)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware

# ContextVar para que el formatter pueda inyectar request_id en cualquier log
# que ocurra dentro del scope de la request (incluso desde libs internas).
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


# Atributos estándar de LogRecord que NO queremos duplicar como "extra"
_RESERVED_LOG_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formatter que serializa cada record a JSON.

    Campos: timestamp (ISO8601 UTC), level, logger, message, module, line.
    Si hay request_id en el ContextVar lo agrega. Si el record trae kwargs
    extra (e.g. `logger.info("x", extra={"tenant_id": "abc"})`), los incluye.
    Si hay excepción la serializa en `exc`.
    """

    def __init__(self, service: str = "inmobot-backend"):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "service": self.service,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        rid = _request_id_ctx.get()
        if rid:
            payload["request_id"] = rid

        # Extra fields (whatever user pased via `extra=`)
        for k, v in record.__dict__.items():
            if k in _RESERVED_LOG_ATTRS or k.startswith("_"):
                continue
            if k in payload:
                continue
            try:
                json.dumps(v, default=str)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = str(v)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fallback ultraseguro: nunca debe romper logging
            return json.dumps({
                "timestamp": ts,
                "level": record.levelname,
                "message": record.getMessage(),
            })


def setup_logging(level: str | None = None, service: str = "inmobot-backend"):
    """Configura el root logger + uvicorn en formato JSON.

    Idempotente: si se llama 2 veces, reemplaza handlers en lugar de duplicar.
    Se desactiva con env LOG_FORMAT=text (útil para desarrollo local).
    """
    log_level = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    use_json = os.environ.get("LOG_FORMAT", "json").lower() != "text"

    if use_json:
        formatter: logging.Formatter = JsonFormatter(service=service)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    # uvicorn usa loggers separados; reattach al mismo handler para uniformidad
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
        lg.setLevel(log_level)

    return root


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Asigna un request_id por request + emite un log de acceso estructurado.

    - Si el cliente manda `X-Request-ID` lo respeta (truncado a 64 chars),
      sino genera un uuid4 corto (hex de 12 chars).
    - Lo expone en el header `X-Request-ID` de la respuesta.
    - Al finalizar la request, emite un log con method/path/status/duration_ms.
    - Health endpoints se loggean a DEBUG (no spamear con UptimeRobot pings).
    """

    HEALTH_PATHS = {"/api/health", "/api/health/ping", "/health"}

    async def dispatch(self, request, call_next):
        incoming = (request.headers.get("x-request-id") or "").strip()
        rid = incoming[:64] if incoming else uuid.uuid4().hex[:12]
        token = _request_id_ctx.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            path = request.url.path
            log_level = logging.DEBUG if path in self.HEALTH_PATHS else logging.INFO
            logging.getLogger("inmobot.access").log(
                log_level,
                f"{request.method} {path} {status} {duration_ms}ms",
                extra={
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "duration_ms": duration_ms,
                    "client_ip": (
                        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                        or (request.client.host if request.client else None)
                    ),
                    "user_agent": request.headers.get("user-agent"),
                },
            )
            _request_id_ctx.reset(token)
