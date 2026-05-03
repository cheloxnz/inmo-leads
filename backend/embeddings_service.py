"""
Embeddings Service
==================

Convierte textos cortos (preguntas, mensajes) en vectores numéricos densos
de 384 dimensiones usando un modelo multilingüe (Spanish-friendly) ejecutado
localmente vía ONNX Runtime (fastembed). Permite búsqueda semántica por
similitud coseno: detecta paráfrasis, sinónimos y preguntas reformuladas que
los algoritmos lexicográficos (Jaccard) no atrapan.

Modelo: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- 384 dims
- ~225 MB (descarga única, on-demand al primer uso)
- Soporta 50+ idiomas (incluido español, italiano, portugués)
- ONNX runtime: CPU only, ~25ms por texto en hardware típico

Diseño:
- Singleton lazy-loaded: el modelo NO se carga al import, sino al primer
  embed_text(). Esto permite que la app arranque rápido aunque el modelo
  no esté descargado todavía.
- Encoding/cosine se delega a `asyncio.to_thread` para no bloquear el event
  loop de FastAPI.
- Si la inicialización falla (sin internet, disco lleno, etc.), `is_available()`
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
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
EMBEDDING_DIM = 384

_model = None
_model_load_attempted = False
_model_load_error: Optional[str] = None
_model_lock = asyncio.Lock()


async def _ensure_model():
    """Lazy-load del modelo en el primer uso. Idempotente, thread-safe."""
    global _model, _model_load_attempted, _model_load_error
    if _model is not None:
        return _model
    async with _model_lock:
        if _model is not None:
            return _model
        if _model_load_attempted and _model_load_error:
            return None  # Falló antes, no reintentar en cada call
        _model_load_attempted = True
        try:
            def _load():
                from fastembed import TextEmbedding
                return TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
            _model = await asyncio.to_thread(_load)
            logger.info(f"[embeddings] modelo cargado: {EMBEDDING_MODEL_NAME}")
            return _model
        except Exception as e:
            _model_load_error = str(e)
            logger.warning(f"[embeddings] no se pudo cargar modelo: {e}. Fallback a Jaccard.")
            return None


def is_available() -> bool:
    """Retorna True si el modelo se cargó correctamente alguna vez."""
    return _model is not None


async def embed_text(text: str) -> Optional[List[float]]:
    """Devuelve un vector de 384 floats para `text`, o None si el modelo no
    está disponible o el input es vacío."""
    if not text or not text.strip():
        return None
    model = await _ensure_model()
    if model is None:
        return None
    try:
        def _run():
            # fastembed.embed() retorna un generator de np.ndarray
            vecs = list(model.embed([text.strip()]))
            return vecs[0].tolist() if vecs else None
        return await asyncio.to_thread(_run)
    except Exception as e:
        logger.warning(f"[embeddings] embed_text fallo: {e}")
        return None


async def embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Embed batch (más eficiente que llamar embed_text N veces).

    Devuelve una lista del mismo largo que `texts`. Posiciones con texto
    vacío o errores devuelven None en esa posición.
    """
    if not texts:
        return []
    model = await _ensure_model()
    if model is None:
        return [None] * len(texts)

    # Filtramos vacíos pero conservamos índices originales
    valid_idx = [i for i, t in enumerate(texts) if t and t.strip()]
    valid_texts = [texts[i].strip() for i in valid_idx]
    if not valid_texts:
        return [None] * len(texts)

    try:
        def _run():
            return [v.tolist() for v in model.embed(valid_texts)]
        valid_vecs = await asyncio.to_thread(_run)
    except Exception as e:
        logger.warning(f"[embeddings] embed_batch fallo: {e}")
        return [None] * len(texts)

    result: List[Optional[List[float]]] = [None] * len(texts)
    for pos, vec in zip(valid_idx, valid_vecs):
        result[pos] = vec
    return result


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity entre dos vectores. Devuelve 0.0 si alguno es vacío
    o si las dimensiones no coinciden."""
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
