"""
Tests para el sistema de embeddings semánticos del bot learning.

Cubre:
- embeddings_service: lazy-load, embed_text, embed_batch, cosine.
- bot_learning_service.find_learned_answer con embeddings.
- bot_learning_service.find_agent_suggestions re-rankea con cosine.
- Endpoints /bot-learning/embeddings-status y /backfill-embeddings.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import embeddings_service as es
from bot_learning_service import (
    save_learned_response,
    find_learned_answer,
    find_agent_suggestions,
    backfill_embeddings,
)


@pytest.mark.asyncio
async def test_embedding_service_loads_model():
    """El modelo se carga en el primer uso."""
    vec = await es.embed_text("hola mundo")
    assert vec is not None, "El modelo de embeddings no cargó"
    assert len(vec) == es.EMBEDDING_DIM == 384
    assert es.is_available() is True


@pytest.mark.asyncio
async def test_embedding_empty_input_returns_none():
    assert await es.embed_text("") is None
    assert await es.embed_text("   ") is None


@pytest.mark.asyncio
async def test_embed_batch_preserves_order_and_handles_empty():
    res = await es.embed_batch(["uno", "", "tres"])
    assert len(res) == 3
    assert res[0] is not None and len(res[0]) == 384
    assert res[1] is None  # vacío
    assert res[2] is not None and len(res[2]) == 384


@pytest.mark.asyncio
async def test_cosine_similarity_paraphrase_higher_than_unrelated():
    """Una paráfrasis debe tener cosine más alto que una pregunta no relacionada."""
    q = await es.embed_text("Cuanto cuesta el alquiler del depto?")
    paraphrase = await es.embed_text("Que precio tiene el departamento?")
    unrelated = await es.embed_text("Como va a estar el clima manana?")
    cos_para = es.cosine_similarity(q, paraphrase)
    cos_unrel = es.cosine_similarity(q, unrelated)
    assert cos_para > cos_unrel, f"paraphrase {cos_para} debería ser > unrelated {cos_unrel}"
    assert cos_para > 0.45, f"paraphrase cosine {cos_para} debajo del threshold típico"


def test_cosine_edge_cases():
    assert es.cosine_similarity([], [1.0]) == 0.0
    assert es.cosine_similarity([1.0, 2.0], [1.0]) == 0.0  # dim mismatch
    assert es.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero norm


# --- Tests con DB mock ---

class FakeMongoCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find(self, query, projection=None):
        # Filtra docs por query (simplificado: solo $or, $exists, $ne, igualdad directa)
        filtered = []
        for d in self.docs:
            if self._match(d, query):
                filtered.append(self._project(d, projection))
        return _FakeCursor(filtered)

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if self._match(d, query):
                return self._project(d, projection)
        return None

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def update_one(self, query, update):
        for d in self.docs:
            if self._match(d, query):
                if "$set" in update:
                    d.update(update["$set"])
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        d[k] = d.get(k, 0) + v
                return type("R", (), {"modified_count": 1})()
        return type("R", (), {"modified_count": 0})()

    async def count_documents(self, query):
        return sum(1 for d in self.docs if self._match(d, query))

    def _match(self, doc, query):
        for k, v in query.items():
            if k == "$or":
                if not any(self._match(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                if "$exists" in v:
                    has = k in doc
                    if v["$exists"] != has:
                        return False
                if "$ne" in v:
                    if doc.get(k) == v["$ne"]:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    def _project(self, doc, projection):
        if not projection:
            return dict(doc)
        # Soporte mínimo: exclusión
        excludes = {k for k, v in projection.items() if v == 0}
        return {k: v for k, v in doc.items() if k not in excludes}


class _FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self.docs):
            raise StopAsyncIteration
        d = self.docs[self._i]
        self._i += 1
        return d

    async def to_list(self, n):
        return self.docs[:n]


class FakeDB:
    def __init__(self):
        self.learned_responses = FakeMongoCollection()
        self.leads = FakeMongoCollection()


@pytest.mark.asyncio
async def test_save_learned_response_includes_embedding():
    db = FakeDB()
    res = await save_learned_response(
        db=db,
        tenant_id="t1",
        question="Cuanto sale el alquiler del depto?",
        answer="$850.000 con expensas aparte.",
        created_by="agent@test.com",
    )
    # La respuesta NO debe incluir el vector (ruido) pero el doc en DB sí.
    assert "embedding" not in res
    saved = await db.learned_responses.find_one({"id": res["id"]})
    assert saved.get("embedding") is not None
    assert len(saved["embedding"]) == 384
    assert saved.get("embedding_model")


@pytest.mark.asyncio
async def test_find_learned_answer_uses_embedding_for_paraphrase():
    """Verifica que una paráfrasis matchee gracias a embeddings, donde Jaccard
    no podría."""
    db = FakeDB()
    await save_learned_response(
        db=db,
        tenant_id="t2",
        question="Cuanto sale el alquiler del depto en Palermo?",
        answer="850 mil pesos por mes.",
    )
    # Query con vocabulario distinto (rentar/inmueble/precio/zona)
    match = await find_learned_answer(
        db, "t2", "Que precio tiene rentar el departamento de Palermo?",
    )
    assert match is not None, "El match semántico debería detectar la paráfrasis"
    assert match["match_method"] == "embedding"
    assert match["score"] >= 0.50
    assert "850 mil" in match["answer"]


@pytest.mark.asyncio
async def test_find_learned_answer_no_match_for_unrelated():
    db = FakeDB()
    await save_learned_response(
        db=db,
        tenant_id="t3",
        question="Cuanto sale el alquiler?",
        answer="850k",
    )
    match = await find_learned_answer(db, "t3", "Como va a estar el clima manana?")
    assert match is None


@pytest.mark.asyncio
async def test_backfill_embeddings():
    """Entradas legacy sin embedding deben procesarse en bulk."""
    db = FakeDB()
    # Insertamos 2 docs sin embedding directamente (simulando legacy)
    now = datetime.now(timezone.utc).isoformat()
    db.learned_responses.docs.extend([
        {
            "id": "legacy1", "tenant_id": "t4", "question": "Hola que tal?",
            "answer": "Bien gracias", "active": True, "created_at": now,
        },
        {
            "id": "legacy2", "tenant_id": "t4", "question": "A que hora abren?",
            "answer": "9 a 18hs", "active": True, "created_at": now,
        },
    ])
    res = await backfill_embeddings(db, tenant_id="t4")
    assert res["processed"] == 2
    assert res["failed"] == 0
    # Verificamos que ahora tienen embedding
    for doc_id in ["legacy1", "legacy2"]:
        d = await db.learned_responses.find_one({"id": doc_id})
        assert d.get("embedding") is not None
        assert len(d["embedding"]) == 384

    # Re-correr backfill: nada para procesar (idempotente)
    res2 = await backfill_embeddings(db, tenant_id="t4")
    assert res2["total_pending"] == 0


@pytest.mark.asyncio
async def test_find_agent_suggestions_combines_learned_and_history():
    db = FakeDB()
    # Una learned response confiable
    await save_learned_response(
        db=db,
        tenant_id="t5",
        question="Cuanto cuesta el alquiler del depto en Palermo?",
        answer="850 mil pesos mensuales",
    )
    # Un lead distinto con conversación que tiene un par customer→agent relevante
    now = datetime.now(timezone.utc).isoformat()
    db.leads.docs.append({
        "tenant_id": "t5",
        "phone": "+5491111111111",
        "name": "Juan",
        "last_message_at": now,
        "conversation_history": [
            {"from": "customer", "text": "Cual es el precio del alquiler del depto?", "timestamp": now},
            {"from": "agent", "text": "Está en 850 mil pesos por mes con expensas aparte y cochera incluida.", "timestamp": now},
        ],
    })
    # Query del asesor que está escribiendo a OTRO lead
    suggestions = await find_agent_suggestions(
        db, "t5", "Cuanto vale rentar el departamento?", exclude_lead_phone="+5499999",
    )
    assert len(suggestions) >= 1
    # El learned debe aparecer primero (alta confianza)
    assert suggestions[0]["source"] == "learned"
    # match_method debe estar presente
    assert "match_method" in suggestions[0]
