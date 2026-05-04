"""
Embeddings Service
==================

Convierte textos cortos (preguntas, mensajes) en vectores numéricos densos
de 1536 dimensiones usando OpenAI `text-embedding-3-small`.

Por qué OpenAI y no un modelo local:
- Cero overhead de RAM (en producción serverless con poca RAM, fastembed
  causaba OOM en cold start).
- Cero descarga al startup (~225 MB) → no más timeout 520 en Cloudflare.
- Calidad superior: 1536 dims vs 384, mejor multilingual.
- Costo: $0.02 por 1M tokens ≈ insignificante para nuestro volumen.

Si la API falla (sin internet, key inválida, rate limit), `is_available()`
retorna False y el caller hace fallback al algoritmo Jaccard tradicional.
"""
import asyncio
import logging
import math
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME",
    "text-embedding-3-small",
)
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))

_client = None
_client_load_error: Optional[str] = None
_client_lock = asyncio.Lock()


async def _ensure_client():
    """Lazy-init del cliente OpenAI. Idempotente."""
    global _client, _client_load_error
    if _client is not None:
        return _client
    if _client_load_error:
        return None
    async with _client_lock:
        if _client is not None:
            return _client
        try:
            from openai import AsyncOpenAI
            api_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not api_key:
                _client_load_error = "OPENAI_API_KEY no configurada"
                logger.warning(f"[embeddings] {_client_load_error}. Fallback a Jaccard.")
                return None
            _client = AsyncOpenAI(api_key=api_key)
            logger.info(f"[embeddings] cliente OpenAI listo, modelo {EMBEDDING_MODEL_NAME}")
            return _client
        except Exception as e:
            _client_load_error = str(e)
            logger.warning(f"[embeddings] no se pudo inicializar OpenAI: {e}. Fallback a Jaccard.")
            return None


def is_available() -> bool:
    """Retorna True si el cliente está inicializado."""
    return _client is not None


async def embed_text(text: str) -> Optional[List[float]]:
    """Devuelve un vector de embeddings para `text`, o None si no se pudo."""
    if not text or not text.strip():
        return None
    client = await _ensure_client()
    if client is None:
        return None
    try:
        resp = await client.embeddings.create(
            model=EMBEDDING_MODEL_NAME,
            input=text.strip(),
        )
        return resp.data[0].embedding
    except Exception as e:
        logger.warning(f"[embeddings] embed_text fallo: {e}")
        return None


async def embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Embed batch en una sola llamada API.

    Devuelve una lista del mismo largo que `texts`. Posiciones con texto
    vacío devuelven None. Si la API falla, todas devuelven None y el caller
    cae al algoritmo Jaccard.
    """
    if not texts:
        return []
    client = await _ensure_client()
    if client is None:
        return [None] * len(texts)

    valid_idx = [i for i, t in enumerate(texts) if t and t.strip()]
    valid_texts = [texts[i].strip() for i in valid_idx]
    if not valid_texts:
        return [None] * len(texts)

    try:
        resp = await client.embeddings.create(
            model=EMBEDDING_MODEL_NAME,
            input=valid_texts,
        )
        valid_vecs = [d.embedding for d in resp.data]
    except Exception as e:
        logger.warning(f"[embeddings] embed_batch fallo: {e}")
        return [None] * len(texts)

    result: List[Optional[List[float]]] = [None] * len(texts)
    for pos, vec in zip(valid_idx, valid_vecs):
        result[pos] = vec
    return result


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity entre dos vectores."""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))
