"""
Bot Learning Service
====================

Permite que el bot aprenda de respuestas humanas marcadas como buenas por
los asesores. Cuando un asesor encuentra una respuesta del bot incorrecta
(o cuando el flow derivó a humano), corrige al lead y luego marca esa
respuesta humana como "respuesta válida del bot" desde la UI de chat.

Antes de llamar al LLM, el bot busca en `learned_responses` del tenant
una respuesta validada para una pregunta similar. Si la encuentra con
score suficiente, la usa literal (sin gastar tokens LLM y con lenguaje
más natural del negocio).

Algoritmo de similarity (sin embeddings):
- Normalización: lowercase, sin acentos, sin signos.
- Tokenización por palabras de >= 3 chars.
- Set de keywords del query nuevo vs cada learned.question.
- Score = Jaccard(set1, set2) + bonus por substring exacto.
- Threshold default: 0.55 (configurable por env).
"""
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Stopwords en español + algunas inglés básicas
_STOPWORDS = {
    "que", "como", "con", "para", "por", "una", "uno", "los", "las", "del",
    "tienen", "tienes", "tenes", "tenés", "hay", "este", "esta", "esto",
    "ese", "esa", "eso", "porque", "pero", "tambien", "también", "pueden",
    "puede", "puedo", "soy", "que", "the", "and", "for", "you", "your",
    "necesito", "quiero", "quisiera", "busco", "yo", "mi", "me", "lo",
    "le", "se", "su", "sus", "es", "ser", "son", "fue", "ya", "ahi", "ahí",
}


def _normalize(text: str) -> str:
    """Lower + sin acentos + un espacio entre palabras."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.lower().strip()


def _stem(token: str) -> str:
    """Stemming muy simple en español: saca plurales y conjugaciones verbales
    comunes para que 'hacé'/'hacen'/'hacer', 'envío'/'envíos', 'pregunta'/
    'preguntas' / 'preguntan' matcheen.
    """
    # Plurales
    if len(token) > 5 and token.endswith("es"):
        token = token[:-2]
    elif len(token) > 4 and token.endswith("s"):
        token = token[:-1]
    # Conjugaciones verbales comunes (3a persona)
    elif len(token) > 4 and (token.endswith("an") or token.endswith("en")):
        token = token[:-2]
    # Infinitivos -ar/-er/-ir
    elif len(token) > 4 and token[-2:] in ("ar", "er", "ir"):
        token = token[:-2]
    return token


def _tokens(text: str) -> set:
    """Set de tokens significativos (>=3 chars, no stopwords, stemmed)."""
    norm = _normalize(text)
    raw = re.findall(r"[a-z0-9]+", norm)
    return {_stem(t) for t in raw if len(t) >= 3 and t not in _STOPWORDS}


def similarity_score(query: str, learned_question: str) -> float:
    """Score 0.0-1.5: Jaccard con bonus por substring exacto."""
    q_tokens = _tokens(query)
    l_tokens = _tokens(learned_question)
    if not q_tokens or not l_tokens:
        return 0.0
    inter = q_tokens & l_tokens
    union = q_tokens | l_tokens
    jaccard = len(inter) / len(union) if union else 0.0

    # Bonus si la learned_question (normalizada) está incluida dentro del
    # query (o viceversa para queries cortos)
    nq = _normalize(query)
    nl = _normalize(learned_question)
    bonus = 0.0
    if len(nl) >= 8 and nl in nq:
        bonus = 0.3
    elif len(nq) >= 8 and nq in nl:
        bonus = 0.2

    return jaccard + bonus


async def find_learned_answer(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    user_message: str,
    threshold: float = 0.45,
) -> Optional[dict]:
    """Busca una respuesta aprendida para `user_message` en este tenant.

    Returns:
        dict con {answer, source_id, score, learned_question} si hay match,
        None si no.
    """
    if not tenant_id or not user_message:
        return None

    cursor = db.learned_responses.find(
        {"tenant_id": tenant_id, "active": True},
        {"_id": 0},
    )
    best = None
    best_score = 0.0
    async for entry in cursor:
        score = similarity_score(user_message, entry.get("question", ""))
        if score > best_score:
            best_score = score
            best = entry

    if not best or best_score < threshold:
        return None

    # Increment used_count + last_used_at (best-effort, no bloqueamos al caller)
    try:
        await db.learned_responses.update_one(
            {"id": best.get("id")},
            {
                "$inc": {"used_count": 1},
                "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()},
            },
        )
    except Exception as e:
        logger.warning(f"[learned] inc used_count failed: {e}")

    return {
        "answer": best.get("answer", ""),
        "source_id": best.get("id"),
        "score": round(best_score, 3),
        "learned_question": best.get("question", ""),
    }


async def save_learned_response(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    question: str,
    answer: str,
    created_by: str = "",
    lead_phone: str = "",
    notes: str = "",
) -> dict:
    """Guarda una nueva learned response. Si ya existe una con la misma
    question normalizada, actualiza la answer (overwrite)."""
    norm_q = _normalize(question)
    existing = await db.learned_responses.find_one(
        {"tenant_id": tenant_id, "question_normalized": norm_q},
        {"_id": 0},
    )
    now = datetime.now(timezone.utc).isoformat()

    if existing:
        await db.learned_responses.update_one(
            {"id": existing["id"]},
            {"$set": {
                "answer": answer,
                "updated_at": now,
                "active": True,
                "notes": notes or existing.get("notes", ""),
            }},
        )
        return await db.learned_responses.find_one(
            {"id": existing["id"]}, {"_id": 0},
        )

    doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "question": question,
        "question_normalized": norm_q,
        "answer": answer,
        "active": True,
        "created_by": created_by,
        "lead_phone": lead_phone,
        "notes": notes,
        "used_count": 0,
        "last_used_at": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.learned_responses.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


async def list_learned_responses(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    include_inactive: bool = False,
) -> List[dict]:
    """Lista todas las learned responses del tenant ordenadas por used_count desc."""
    query = {"tenant_id": tenant_id}
    if not include_inactive:
        query["active"] = True
    return await db.learned_responses.find(query, {"_id": 0}).sort(
        "used_count", -1
    ).to_list(500)
