"""Cache TTL en memoria para reducir lookups frecuentes a MongoDB.

Uso:
    from cache_util import ttl_cache_get, ttl_cache_set

    cached = ttl_cache_get("tenants", tenant_id)
    if cached is None:
        doc = await db.tenants.find_one(...)
        ttl_cache_set("tenants", tenant_id, doc, ttl=60)
    else:
        doc = cached

NO usar para datos sensibles que cambian frecuentemente (precios, balances).
Apropiado para: tenant config, branding, template metadata.
"""
import time
from typing import Any, Optional

# Estructura: {namespace: {key: (value, expires_at)}}
_buckets: dict[str, dict[str, tuple[Any, float]]] = {}


def ttl_cache_get(namespace: str, key: str) -> Optional[Any]:
    """Devuelve el valor cacheado si esta vigente, o None."""
    bucket = _buckets.get(namespace)
    if not bucket:
        return None
    entry = bucket.get(key)
    if not entry:
        return None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        bucket.pop(key, None)
        return None
    return value


def ttl_cache_set(namespace: str, key: str, value: Any, ttl: float = 60.0) -> None:
    """Guarda value bajo (namespace, key) con TTL en segundos."""
    bucket = _buckets.setdefault(namespace, {})
    bucket[key] = (value, time.monotonic() + ttl)


def ttl_cache_invalidate(namespace: str, key: Optional[str] = None) -> None:
    """Invalida una key especifica o el namespace entero (key=None)."""
    if key is None:
        _buckets.pop(namespace, None)
    else:
        bucket = _buckets.get(namespace)
        if bucket:
            bucket.pop(key, None)


def ttl_cache_stats() -> dict:
    """Stats simples para debug/monitoring."""
    return {ns: len(b) for ns, b in _buckets.items()}
