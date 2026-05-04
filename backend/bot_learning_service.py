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
from datetime import datetime, timezone, timedelta
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



async def find_coaching_opportunity(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    customer_question: str,
    exclude_lead_phone: str = "",
    days: int = 30,
    min_count_to_recommend: int = 3,
    similarity_threshold: float = 0.45,
    dedup_threshold: float = 0.85,
    max_candidates: int = 80,
) -> dict:
    """Detecta oportunidades de "coaching proactivo": mide cuántas preguntas
    de OTROS leads (últimos `days` días) son semánticamente similares a
    `customer_question` y NO están cubiertas por una learned_response del bot.

    Si el asesor respondió manualmente a una pregunta, y la misma pregunta
    aparece 3+ veces sin respuesta aprendida del bot, vale la pena enseñarla
    para que el bot la responda automáticamente la próxima vez.

    Returns:
        {
          "already_taught": bool,            # Ya existe una learned_response que matchea
          "similar_pending_count": int,      # Cuántas preguntas sin cubrir se parecen
          "sample_questions": [              # Top 3 preguntas reales para mostrar al asesor
            {"question": str, "lead_name": str, "days_ago": int}
          ],
          "recommendation": "teach" | "already_taught" | "not_enough",
          "reason": str,
        }
    """
    import embeddings_service as embed_svc

    if not tenant_id or not customer_question.strip():
        return {
            "already_taught": False,
            "similar_pending_count": 0,
            "sample_questions": [],
            "recommendation": "not_enough",
            "reason": "pregunta vacía",
        }

    # 1. ¿Ya existe una learned response que matchee esta pregunta?
    existing_match = await find_learned_answer(
        db, tenant_id, customer_question, embedding_threshold=0.52,
    )
    if existing_match:
        return {
            "already_taught": True,
            "similar_pending_count": 0,
            "sample_questions": [],
            "recommendation": "already_taught",
            "reason": f"el bot ya tiene una respuesta enseñada (score {existing_match['score']})",
            "existing_learned_id": existing_match.get("source_id"),
        }

    # 2. Buscar preguntas similares en leads recientes
    query_vec = await embed_svc.embed_text(customer_question)
    # Si el modelo de embeddings no está disponible, no podemos hacer coaching
    if not query_vec:
        return {
            "already_taught": False,
            "similar_pending_count": 0,
            "sample_questions": [],
            "recommendation": "not_enough",
            "reason": "modelo de embeddings no disponible",
        }

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    lead_query = {
        "tenant_id": tenant_id,
        "conversation_history.0": {"$exists": True},
        "last_message_at": {"$gte": cutoff_date},
    }
    if exclude_lead_phone:
        lead_query["phone"] = {"$ne": exclude_lead_phone}

    cursor = db.leads.find(
        lead_query,
        {"_id": 0, "phone": 1, "name": 1, "conversation_history": 1, "last_message_at": 1},
    ).sort("last_message_at", -1).limit(max_candidates)

    now = datetime.now(timezone.utc)
    raw_questions = []  # lista de {text, lead_name, lead_phone, ts}
    async for lead in cursor:
        history = lead.get("conversation_history") or []
        for msg in history:
            if msg.get("from") != "customer":
                continue
            text = (msg.get("text") or "").strip()
            if len(text) < 8 or len(text) > 400:
                continue
            # Pre-filter ligero por Jaccard (ahorra embeddings)
            jscore = similarity_score(customer_question, text)
            if jscore < 0.10:
                continue
            ts = msg.get("timestamp") or lead.get("last_message_at") or ""
            raw_questions.append({
                "text": text,
                "lead_name": lead.get("name") or lead.get("phone"),
                "lead_phone": lead.get("phone"),
                "timestamp": ts,
                "jaccard": jscore,
            })

    if not raw_questions:
        return {
            "already_taught": False,
            "similar_pending_count": 0,
            "sample_questions": [],
            "recommendation": "not_enough",
            "reason": "no hay preguntas similares recientes",
        }

    # Tomamos top 40 por Jaccard para embeber (evita explotar el batch)
    raw_questions.sort(key=lambda x: x["jaccard"], reverse=True)
    raw_questions = raw_questions[:40]

    texts = [q["text"] for q in raw_questions]
    vecs = await embed_svc.embed_batch(texts)

    similar = []  # con score cosine
    for q, vec in zip(raw_questions, vecs):
        if vec is None:
            continue
        cos = embed_svc.cosine_similarity(query_vec, vec)
        if cos < similarity_threshold:
            continue
        similar.append({**q, "cosine": cos, "vec": vec})

    if not similar:
        return {
            "already_taught": False,
            "similar_pending_count": 0,
            "sample_questions": [],
            "recommendation": "not_enough",
            "reason": "ninguna pregunta similar alcanza el umbral semántico",
        }

    # Deduplicación solo para las muestras visuales (evitar mostrar 3 veces
    # la misma pregunta). El count sigue siendo el TOTAL de leads distintos
    # afectados, porque esa es la medida de demanda que vale para coaching.
    similar.sort(key=lambda x: x["cosine"], reverse=True)

    # Contamos leads únicos (una misma persona puede haber preguntado 2 veces)
    unique_phones = {s["lead_phone"] for s in similar if s.get("lead_phone")}
    count = len(unique_phones) if unique_phones else len(similar)

    # Clustering para las 3 muestras visibles (variedad)
    unique_clusters: List[dict] = []
    for s in similar:
        duplicated = False
        for cluster in unique_clusters:
            if embed_svc.cosine_similarity(s["vec"], cluster["vec"]) >= dedup_threshold:
                duplicated = True
                break
        if not duplicated:
            unique_clusters.append(s)

    # Armamos las 3 mejores muestras para mostrar al asesor
    sample_questions = []
    for c in unique_clusters[:3]:
        days_ago = 0
        try:
            ts = c.get("timestamp") or ""
            if ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days_ago = max(0, (now - dt).days)
        except Exception:
            pass
        sample_questions.append({
            "question": c["text"],
            "lead_name": c["lead_name"],
            "days_ago": days_ago,
            "score": round(c["cosine"], 3),
        })

    recommendation = "teach" if count >= min_count_to_recommend else "not_enough"
    reason = (
        f"hay {count} pregunta(s) similar(es) en los últimos {days} días sin respuesta del bot"
        if recommendation == "teach"
        else f"solo {count} pregunta(s) similar(es) — necesita ≥ {min_count_to_recommend}"
    )
    return {
        "already_taught": False,
        "similar_pending_count": count,
        "sample_questions": sample_questions,
        "recommendation": recommendation,
        "reason": reason,
    }



async def discover_coaching_opportunities(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    days: int = 30,
    min_cluster_size: int = 2,
    cluster_threshold: float = 0.75,
    max_questions: int = 500,
    max_clusters: int = 20,
) -> dict:
    """Dashboard global: descubre TODAS las oportunidades de coaching del tenant
    en una sola llamada. Escanea preguntas de clientes, filtra las cubiertas
    por learned_responses existentes, y clusteriza las restantes por similitud
    semántica. Devuelve clusters ordenados por volumen.

    Útil para la vista "/config → Oportunidades de coaching" donde el admin
    ve en bulk qué temas no cubre el bot y puede enseñar respuestas una tras
    otra sin tener que abrir lead por lead.

    Returns:
      {
        model_available: bool,
        total_customer_questions: int,
        already_covered: int,
        uncovered: int,
        clusters: [{
          canonical_question: str,        # la pregunta más representativa
          cluster_size: int,              # cuántos leads únicos
          sample_questions: [             # hasta 5 ejemplos
            {question, lead_name, lead_phone, days_ago, timestamp}
          ],
          last_seen_days_ago: int,
          first_seen_days_ago: int,
        }]
      }
    """
    import embeddings_service as embed_svc

    # Forzar load del modelo
    probe = await embed_svc.embed_text("ping")
    if probe is None:
        return {
            "model_available": False,
            "total_customer_questions": 0,
            "already_covered": 0,
            "uncovered": 0,
            "clusters": [],
            "error": "Modelo de embeddings no disponible",
        }

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # 1. Recolectar preguntas de clientes de los últimos N días
    lead_query = {
        "tenant_id": tenant_id,
        "conversation_history.0": {"$exists": True},
        "last_message_at": {"$gte": cutoff_date},
    }
    cursor = db.leads.find(
        lead_query,
        {"_id": 0, "phone": 1, "name": 1, "conversation_history": 1, "last_message_at": 1},
    ).sort("last_message_at", -1).limit(500)

    raw_questions = []
    seen_phone_texts = set()  # dedup mismo lead con misma pregunta repetida
    async for lead in cursor:
        history = lead.get("conversation_history") or []
        for msg in history:
            if msg.get("from") != "customer":
                continue
            text = (msg.get("text") or "").strip()
            if len(text) < 8 or len(text) > 400:
                continue
            # Dedup intra-lead
            dedup_key = (lead.get("phone", ""), _normalize(text)[:80])
            if dedup_key in seen_phone_texts:
                continue
            seen_phone_texts.add(dedup_key)
            raw_questions.append({
                "text": text,
                "lead_name": lead.get("name") or lead.get("phone"),
                "lead_phone": lead.get("phone"),
                "timestamp": msg.get("timestamp") or lead.get("last_message_at") or "",
            })
            if len(raw_questions) >= max_questions:
                break
        if len(raw_questions) >= max_questions:
            break

    total = len(raw_questions)
    if total == 0:
        return {
            "model_available": True,
            "total_customer_questions": 0,
            "already_covered": 0,
            "uncovered": 0,
            "clusters": [],
        }

    # 2. Precargar learned_responses CON embedding del tenant
    learned = await db.learned_responses.find(
        {"tenant_id": tenant_id, "active": True,
         "embedding": {"$exists": True, "$ne": None}},
        {"_id": 0, "id": 1, "question": 1, "embedding": 1},
    ).to_list(500)

    # 3. Embed todas las preguntas en batch
    texts = [q["text"] for q in raw_questions]
    vecs = await embed_svc.embed_batch(texts)

    # 4. Filtrar las ya cubiertas por learned_responses (cosine ≥ 0.52)
    uncovered = []
    already_covered = 0
    for q, v in zip(raw_questions, vecs):
        if v is None:
            continue
        is_covered = False
        for lr in learned:
            if embed_svc.cosine_similarity(v, lr["embedding"]) >= 0.52:
                is_covered = True
                break
        if is_covered:
            already_covered += 1
        else:
            uncovered.append({**q, "vec": v})

    if not uncovered:
        return {
            "model_available": True,
            "total_customer_questions": total,
            "already_covered": already_covered,
            "uncovered": 0,
            "clusters": [],
        }

    # 5. Clustering greedy: recorre preguntas, asigna a cluster existente si
    #    cosine ≥ threshold contra el "centroide" (el primer elemento), sino
    #    crea cluster nuevo.
    clusters: List[dict] = []
    for q in uncovered:
        assigned = False
        for c in clusters:
            if embed_svc.cosine_similarity(q["vec"], c["centroid_vec"]) >= cluster_threshold:
                c["members"].append(q)
                assigned = True
                break
        if not assigned:
            clusters.append({"centroid_vec": q["vec"], "members": [q]})

    # 6. Filtrar clusters chicos, ordenar por volumen desc
    now = datetime.now(timezone.utc)

    def _days_ago(ts: str) -> int:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0, (now - dt).days)
        except Exception:
            return 0

    result_clusters = []
    for c in clusters:
        # Leads únicos dentro del cluster
        unique_phones = {m["lead_phone"] for m in c["members"] if m.get("lead_phone")}
        cluster_size = len(unique_phones) if unique_phones else len(c["members"])
        if cluster_size < min_cluster_size:
            continue

        # Elegimos la "canonical question" como la más corta y clara del cluster
        # (usualmente la más representativa: ni demasiado larga ni muy corta)
        sorted_members = sorted(c["members"], key=lambda m: abs(len(m["text"]) - 40))
        canonical = sorted_members[0]["text"]

        samples = []
        seen_texts = set()
        for m in c["members"]:
            norm = _normalize(m["text"])[:60]
            if norm in seen_texts:
                continue
            seen_texts.add(norm)
            samples.append({
                "question": m["text"],
                "lead_name": m["lead_name"],
                "lead_phone": m["lead_phone"],
                "days_ago": _days_ago(m["timestamp"]),
                "timestamp": m["timestamp"],
            })
            if len(samples) >= 5:
                break

        days_ago_list = [_days_ago(m["timestamp"]) for m in c["members"]]
        result_clusters.append({
            "canonical_question": canonical,
            "cluster_size": cluster_size,
            "sample_questions": samples,
            "last_seen_days_ago": min(days_ago_list) if days_ago_list else 0,
            "first_seen_days_ago": max(days_ago_list) if days_ago_list else 0,
        })

    result_clusters.sort(key=lambda x: x["cluster_size"], reverse=True)
    result_clusters = result_clusters[:max_clusters]

    return {
        "model_available": True,
        "total_customer_questions": total,
        "already_covered": already_covered,
        "uncovered": len(uncovered),
        "clusters": result_clusters,
    }
