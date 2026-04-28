"""Rate limiting helper con backend Redis (multi-replica) y fallback in-memory.

Si REDIS_URL esta seteado y la conexion funciona, usa Redis con sliding window.
Sino, usa un dict in-memory (solo apto para single-instance).
"""
import os
import time
import logging
from collections import defaultdict, deque
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_initialized = False
_in_memory_buckets = defaultdict(deque)


async def _get_redis():
    """Lazy init del cliente Redis. None si no esta disponible."""
    global _redis_client, _redis_initialized
    if _redis_initialized:
        return _redis_client

    _redis_initialized = True
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        logger.info("REDIS_URL no configurado: usando rate-limit in-memory")
        return None

    try:
        # Usar redis.asyncio (libreria oficial) sin agregar al requirements si no se usa
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info(f"Rate-limit usando Redis: {redis_url}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis no disponible ({e}): fallback in-memory")
        return None


async def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> tuple[bool, int]:
    """Sliding window rate limit. Retorna (allowed, remaining_calls).

    Backend: Redis si esta disponible, sino dict in-memory.
    Key recomendado: "<scope>:<tenant_id>" o "<scope>:<ip>"
    """
    redis = await _get_redis()
    now = time.time()
    cutoff = now - window_seconds

    if redis is not None:
        try:
            # Sliding window con sorted set
            redis_key = f"ratelimit:{key}"
            # Pipeline atomico: limpia viejos, cuenta, agrega
            async with redis.pipeline(transaction=False) as pipe:
                pipe.zremrangebyscore(redis_key, 0, cutoff)
                pipe.zcard(redis_key)
                pipe.zadd(redis_key, {str(now): now})
                pipe.expire(redis_key, window_seconds + 10)
                results = await pipe.execute()
            current_count = results[1] + 1  # incluye el que acabamos de agregar
            if current_count > max_calls:
                # Rollback: removemos el que acabamos de agregar
                await redis.zrem(redis_key, str(now))
                return False, 0
            return True, max_calls - current_count
        except Exception as e:
            logger.warning(f"Redis fallo en rate-limit, fallback memoria: {e}")
            # cae al fallback in-memory

    # Fallback in-memory
    bucket = _in_memory_buckets[key]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max_calls:
        return False, 0
    bucket.append(now)
    # GC dicts grandes
    if len(_in_memory_buckets) > 5000:
        for k in list(_in_memory_buckets.keys())[:1000]:
            if not _in_memory_buckets[k] or _in_memory_buckets[k][-1] < now - window_seconds * 2:
                _in_memory_buckets.pop(k, None)
    return True, max_calls - len(bucket)


async def get_retry_after(key: str, window_seconds: int) -> int:
    """Segundos hasta que se libere el primer slot. Soporta Redis y fallback."""
    redis = await _get_redis()
    now = time.time()
    if redis is not None:
        try:
            oldest = await redis.zrange(f"ratelimit:{key}", 0, 0, withscores=True)
            if oldest:
                _, score = oldest[0]
                return max(1, int(window_seconds - (now - score)))
        except Exception:
            pass
    bucket = _in_memory_buckets.get(key)
    if bucket:
        return max(1, int(window_seconds - (now - bucket[0])))
    return window_seconds
