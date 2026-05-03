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


def _fuzzy_overlap(set_a: set, set_b: set) -> tuple:
    """Cuenta tokens que matchean exacto O por prefix (≥4 chars).

    Ej: 'estacion' (de stem de 'estacionar') matchea con 'estacionamiento'
    porque uno es prefijo del otro y ambos tienen ≥4 chars.

    Retorna (count_match, total_unique) para calcular un Jaccard-fuzzy.
    """
    matched_b = set()
    matches = 0
    for a in set_a:
        if a in set_b:
            matches += 1
            matched_b.add(a)
            continue
        # Buscar prefix match
        for b in set_b:
            if b in matched_b:
                continue
            if len(a) >= 4 and len(b) >= 4 and (a.startswith(b[:4]) or b.startswith(a[:4])):
                matches += 1
                matched_b.add(b)
                break
    total = len(set_a) + len(set_b) - matches
    return matches, total


def similarity_score(query: str, learned_question: str) -> float:
    """Score 0.0-1.5: Jaccard-fuzzy con bonus por substring exacto.

    El 'fuzzy' permite que tokens con prefijo común de 4+ chars matcheen
    (captura familias morfológicas que el stemmer simple no atrapa, ej.
    'estacion' ↔ 'estacionamiento').
    """
    q_tokens = _tokens(query)
    l_tokens = _tokens(learned_question)
    if not q_tokens or not l_tokens:
        return 0.0
    matches, total = _fuzzy_overlap(q_tokens, l_tokens)
    jaccard = matches / total if total else 0.0

    # Bonus si una pregunta (normalizada) está incluida en la otra
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


async def find_agent_suggestions(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    query: str,
    exclude_lead_phone: str = "",
    limit: int = 3,
) -> List[dict]:
    """Busca respuestas que ASESORES escribieron en otras conversaciones
    cerradas para preguntas similares al `query`.

    Útil para sugerirle al asesor que está escribiendo: "respondiste algo
    parecido a Juan hace 3 días, ¿querés usar esa misma respuesta?".

    Estrategia:
    - Recorre las últimas N leads del tenant (excluye el actual).
    - Para cada lead, busca pares (mensaje_cliente → siguiente_mensaje_asesor)
      en `conversation_history`.
    - Calcula similarity con el query y devuelve top K respuestas.
    - Deduplica por respuesta normalizada (evita 3 sugerencias idénticas).

    También merge-ea con `learned_responses` activas como fallback de mayor
    confianza.
    """
    if not tenant_id or not query.strip():
        return []

    suggestions = []
    seen_answers = set()

    # 1. Learned responses (alta confianza, ya validadas)
    learned_match = await find_learned_answer(db, tenant_id, query, threshold=0.40)
    if learned_match:
        ans = (learned_match["answer"] or "").strip()
        if ans:
            seen_answers.add(_normalize(ans)[:120])
            suggestions.append({
                "answer": ans,
                "score": learned_match["score"],
                "source": "learned",
                "context": f"Respuesta enseñada al bot: \"{learned_match['learned_question'][:60]}\"",
            })

    # 2. Históricos de conversaciones reales del tenant
    lead_query = {"tenant_id": tenant_id, "conversation_history.0": {"$exists": True}}
    if exclude_lead_phone:
        lead_query["phone"] = {"$ne": exclude_lead_phone}

    # Limitamos a 100 leads más recientes para que sea rápido
    cursor = db.leads.find(
        lead_query,
        {"_id": 0, "phone": 1, "name": 1, "conversation_history": 1},
    ).sort("last_message_at", -1).limit(100)

    candidates = []
    async for lead in cursor:
        history = lead.get("conversation_history") or []
        if len(history) < 2:
            continue
        # Buscar pares (customer → outbound)
        for i in range(len(history) - 1):
            cur = history[i]
            nxt = history[i + 1]
            if cur.get("from") != "customer":
                continue
            if nxt.get("from") == "customer":
                continue
            cust_msg = (cur.get("text") or "").strip()
            agent_msg = (nxt.get("text") or "").strip()
            if not cust_msg or not agent_msg:
                continue
            # Filtros de calidad: no sugerir respuestas muy cortas o muy largas
            if len(agent_msg) < 20 or len(agent_msg) > 600:
                continue
            score = similarity_score(query, cust_msg)
            if score < 0.40:
                continue
            candidates.append({
                "answer": agent_msg,
                "score": score,
                "source": "history",
                "context": (
                    f"Le respondiste así a {lead.get('name') or lead.get('phone')} "
                    f"que preguntó: \"{cust_msg[:60]}\""
                ),
            })

    # Ordenar por score desc y deduplicar respuestas similares
    candidates.sort(key=lambda x: x["score"], reverse=True)
    for c in candidates:
        if len(suggestions) >= limit:
            break
        norm_ans = _normalize(c["answer"])[:120]
        if norm_ans in seen_answers:
            continue
        seen_answers.add(norm_ans)
        suggestions.append({**c, "score": round(c["score"], 3)})

    return suggestions[:limit]
