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
    embedding_threshold: float = 0.52,
) -> Optional[dict]:
    """Busca una respuesta aprendida para `user_message` en este tenant.

    Estrategia de scoring (en orden de prioridad):
      1. **Embeddings (semantic search)**: si la entrada tiene embedding y el
         modelo está disponible, calcula cosine similarity con el query.
         Threshold default 0.55 (paraphrase-MiniLM tiende a 0.5-0.7 para
         paráfrasis claras). Detecta sinónimos, reordenamientos, etc.
      2. **Jaccard fuzzy (fallback)**: para entradas SIN embedding (legacy)
         o cuando el modelo no está disponible. Threshold 0.45.

    Devuelve la mejor coincidencia normalizada a un único score 0-1, indicando
    el método via `match_method` ("embedding" | "lexical").

    Returns:
        dict con {answer, source_id, score, learned_question, match_method}
        si hay match, None si no.
    """
    if not tenant_id or not user_message:
        return None

    import embeddings_service as embed_svc
    query_vec = await embed_svc.embed_text(user_message)

    cursor = db.learned_responses.find(
        {"tenant_id": tenant_id, "active": True},
        {"_id": 0},
    )
    best = None
    best_score = 0.0
    best_method = "lexical"
    async for entry in cursor:
        entry_emb = entry.get("embedding")
        if query_vec and entry_emb:
            score = embed_svc.cosine_similarity(query_vec, entry_emb)
            method = "embedding"
            cutoff = embedding_threshold
        else:
            score = similarity_score(user_message, entry.get("question", ""))
            method = "lexical"
            cutoff = threshold
        # Normalizamos: solo consideramos candidatos que pasaron su propio cutoff.
        if score < cutoff:
            continue
        if score > best_score:
            best_score = score
            best = entry
            best_method = method

    if not best:
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
        "match_method": best_method,
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
    question normalizada, actualiza la answer (overwrite). Computa también
    el embedding semántico de la pregunta (best-effort: si falla, queda
    None y el sistema sigue usando Jaccard para esa entrada)."""
    norm_q = _normalize(question)

    # Compute embedding (best-effort)
    import embeddings_service as embed_svc
    embedding = await embed_svc.embed_text(question)

    existing = await db.learned_responses.find_one(
        {"tenant_id": tenant_id, "question_normalized": norm_q},
        {"_id": 0},
    )
    now = datetime.now(timezone.utc).isoformat()

    if existing:
        update_set = {
            "answer": answer,
            "updated_at": now,
            "active": True,
            "notes": notes or existing.get("notes", ""),
        }
        if embedding is not None:
            update_set["embedding"] = embedding
            update_set["embedding_model"] = embed_svc.EMBEDDING_MODEL_NAME
        await db.learned_responses.update_one(
            {"id": existing["id"]},
            {"$set": update_set},
        )
        return await db.learned_responses.find_one(
            {"id": existing["id"]}, {"_id": 0, "embedding": 0},
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
        "embedding": embedding,  # None si el modelo no está disponible
        "embedding_model": embed_svc.EMBEDDING_MODEL_NAME if embedding else None,
    }
    await db.learned_responses.insert_one(doc)
    # Excluimos embedding de la respuesta (lista de 384 floats es ruidosa).
    return {k: v for k, v in doc.items() if k not in ("_id", "embedding")}


async def list_learned_responses(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    include_inactive: bool = False,
) -> List[dict]:
    """Lista todas las learned responses del tenant ordenadas por used_count desc."""
    query = {"tenant_id": tenant_id}
    if not include_inactive:
        query["active"] = True
    return await db.learned_responses.find(
        query,
        {"_id": 0, "embedding": 0},  # Excluimos vector (384 floats) del listado UI
    ).sort("used_count", -1).to_list(500)


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

    Estrategia híbrida:
    1. **Learned responses** (alta confianza ya validada) → cosine si hay
       embedding, Jaccard si no.
    2. **Históricos de conversaciones reales** del tenant:
       - Pre-filtra por Jaccard ligero (recall amplio, threshold 0.15).
       - Toma top 40 candidatos.
       - Si hay embeddings disponibles, los re-rankea por cosine similarity
         (precisión: detecta paráfrasis). Threshold final 0.45 cosine.
       - Si no, usa el score Jaccard tal cual con threshold 0.40.
    - Deduplica por respuesta normalizada para no mostrar 3 sugerencias
      idénticas.
    """
    if not tenant_id or not query.strip():
        return []

    import embeddings_service as embed_svc
    query_vec = await embed_svc.embed_text(query)

    suggestions = []
    seen_answers = set()

    # 1. Learned responses (alta confianza, ya validadas)
    learned_match = await find_learned_answer(
        db, tenant_id, query, threshold=0.40, embedding_threshold=0.42,
    )
    if learned_match:
        ans = (learned_match["answer"] or "").strip()
        if ans:
            seen_answers.add(_normalize(ans)[:120])
            suggestions.append({
                "answer": ans,
                "score": learned_match["score"],
                "source": "learned",
                "match_method": learned_match.get("match_method", "lexical"),
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

    raw_candidates = []
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
            jaccard = similarity_score(query, cust_msg)
            # Pre-filtro lexical amplio (recall) — luego re-rankeamos
            if jaccard < 0.15:
                continue
            raw_candidates.append({
                "answer": agent_msg,
                "cust_msg": cust_msg,
                "lead_label": lead.get("name") or lead.get("phone"),
                "jaccard": jaccard,
            })

    # Top 40 por Jaccard para mantener acotado el batch de embeddings
    raw_candidates.sort(key=lambda x: x["jaccard"], reverse=True)
    raw_candidates = raw_candidates[:40]

    # Re-ranking semántico con embeddings (si están disponibles)
    final_candidates = []
    if query_vec and raw_candidates:
        cust_msgs = [c["cust_msg"] for c in raw_candidates]
        cust_vecs = await embed_svc.embed_batch(cust_msgs)
        for c, vec in zip(raw_candidates, cust_vecs):
            if vec is None:
                # Caer al Jaccard si no se pudo embed (raro)
                if c["jaccard"] < 0.40:
                    continue
                final_candidates.append({
                    "answer": c["answer"],
                    "score": c["jaccard"],
                    "source": "history",
                    "match_method": "lexical",
                    "context": (
                        f"Le respondiste así a {c['lead_label']} "
                        f"que preguntó: \"{c['cust_msg'][:60]}\""
                    ),
                })
                continue
            cos = embed_svc.cosine_similarity(query_vec, vec)
            if cos < 0.40:
                continue
            final_candidates.append({
                "answer": c["answer"],
                "score": cos,
                "source": "history",
                "match_method": "embedding",
                "context": (
                    f"Le respondiste así a {c['lead_label']} "
                    f"que preguntó: \"{c['cust_msg'][:60]}\""
                ),
            })
    else:
        # Sin embeddings: usar Jaccard tal cual
        for c in raw_candidates:
            if c["jaccard"] < 0.40:
                continue
            final_candidates.append({
                "answer": c["answer"],
                "score": c["jaccard"],
                "source": "history",
                "match_method": "lexical",
                "context": (
                    f"Le respondiste así a {c['lead_label']} "
                    f"que preguntó: \"{c['cust_msg'][:60]}\""
                ),
            })

    # Ordenar por score desc y deduplicar respuestas similares
    final_candidates.sort(key=lambda x: x["score"], reverse=True)
    for c in final_candidates:
        if len(suggestions) >= limit:
            break
        norm_ans = _normalize(c["answer"])[:120]
        if norm_ans in seen_answers:
            continue
        seen_answers.add(norm_ans)
        suggestions.append({**c, "score": round(c["score"], 3)})

    return suggestions[:limit]


async def backfill_embeddings(
    db: AsyncIOMotorDatabase,
    tenant_id: Optional[str] = None,
    batch_size: int = 32,
) -> dict:
    """Computa embeddings para learned_responses que aún no los tienen.

    Útil para migrar entradas guardadas antes de habilitar el sistema de
    embeddings. Idempotente: solo procesa entradas con `embedding=None`.

    Args:
        tenant_id: si se pasa, restringe al tenant. None = todos.
        batch_size: cantidad por lote para embed_batch (más rápido).

    Returns:
        {processed, skipped, failed, total_pending}
    """
    import embeddings_service as embed_svc

    query = {
        "$or": [
            {"embedding": None},
            {"embedding": {"$exists": False}},
        ]
    }
    if tenant_id:
        query["tenant_id"] = tenant_id

    pending = await db.learned_responses.find(
        query, {"_id": 0, "id": 1, "question": 1}
    ).to_list(5000)

    if not pending:
        return {"processed": 0, "skipped": 0, "failed": 0, "total_pending": 0}

    processed = 0
    failed = 0

    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        questions = [(p.get("question") or "") for p in batch]
        vecs = await embed_svc.embed_batch(questions)
        for entry, vec in zip(batch, vecs):
            if vec is None:
                failed += 1
                continue
            await db.learned_responses.update_one(
                {"id": entry["id"]},
                {"$set": {
                    "embedding": vec,
                    "embedding_model": embed_svc.EMBEDDING_MODEL_NAME,
                }},
            )
            processed += 1

    return {
        "processed": processed,
        "skipped": 0,
        "failed": failed,
        "total_pending": len(pending),
    }
