"""Hardening de seguridad: rate limiting por paths, security headers,
payload limit, CORS validation.
"""
import os
import re
import logging
import time
from collections import defaultdict, deque
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# Pattern, max_requests, window_seconds. Primer match gana.
RATE_LIMIT_RULES = [
    (re.compile(r"^/api/auth/(login|register)$"),              10, 60),
    (re.compile(r"^/api/auth/forgot-password"),                 5, 300),
    (re.compile(r"^/api/onboarding/auto-setup$"),               5, 60),
    (re.compile(r"^/api/commissions/resolve-promo$"),          30, 60),
    (re.compile(r"^/api/public/"),                             60, 60),
    (re.compile(r"^/api/leads/[^/]+/ai-summary$"),             30, 60),
    (re.compile(r"^/api/bot-config/ai-edit"),                  20, 60),
    (re.compile(r"^/api/flow/ai-edit"),                        20, 60),
    (re.compile(r"^/api/webhook"),                            300, 60),
    (re.compile(r"^/api/billing/webhook"),                    300, 60),
]


class _RateLimiter:
    def __init__(self):
        self._buckets = defaultdict(deque)

    def check(self, ip, path):
        now = time.monotonic()
        for idx, (pattern, max_req, window) in enumerate(RATE_LIMIT_RULES):
            if not pattern.match(path):
                continue
            key = (ip, idx)
            bucket = self._buckets[key]
            cutoff = now - window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max_req:
                retry_after = int(bucket[0] + window - now) + 1
                return False, retry_after, max_req, window
            bucket.append(now)
            return True, None, max_req, window
        return True, None, None, None


_limiter = _RateLimiter()


def _client_ip(request):
    xff = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path in ("/api/health", "/api/health/ping", "/health") or request.method == "OPTIONS":
            return await call_next(request)
        ip = _client_ip(request)
        allowed, retry_after, max_req, window = _limiter.check(ip, path)
        if not allowed:
            logger.warning(f"Rate limit hit: ip={ip} path={path} ({max_req}/{window}s)")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Demasiadas solicitudes. Esperá unos segundos e intentá de nuevo.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_req),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        if max_req is not None:
            response.headers["X-RateLimit-Limit"] = str(max_req)
            response.headers["X-RateLimit-Window"] = str(window)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Frame-Options", "SAMEORIGIN")
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(self)",
        )
        # HSTS — confiar en X-Forwarded-Proto del proxy/ingress
        proto = (
            request.headers.get("x-forwarded-proto", "").lower()
            or request.url.scheme
        )
        if proto == "https":
            h.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        h.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self' https:; "
                "img-src 'self' data: blob: https:; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
                "style-src 'self' 'unsafe-inline' https: data:; "
                "font-src 'self' data: https:; "
                "connect-src 'self' https: wss:; "
                "frame-src 'self' https:; "
                "frame-ancestors 'self';"
            ),
        )
        if "server" in h:
            del h["server"]
        return response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes=5 * 1024 * 1024):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith("/api/upload") or "/logo" in path or "/audio" in path:
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Payload demasiado grande (límite: {self.max_bytes // 1024}KB)",
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


def setup_security_middleware(app):
    """Registra middlewares. Starlette los ejecuta en orden INVERSO al registro."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(PayloadSizeLimitMiddleware, max_bytes=5 * 1024 * 1024)
    app.add_middleware(RateLimitMiddleware)
    logger.info("✅ Security middlewares registrados (rate limit + payload + headers)")


def validate_cors_origins():
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    env_name = os.environ.get("SENTRY_ENVIRONMENT", "production").lower()
    if not raw or raw == "*":
        if env_name == "production":
            logger.warning(
                "⚠️ CORS_ORIGINS='*' en producción es INSEGURO."
            )
        return ["*"] if raw == "*" else []
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins and env_name == "production":
        logger.warning("⚠️ CORS_ORIGINS contiene '*' en producción.")
    return origins
