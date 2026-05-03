"""Router de Bot Learning: endpoints para que admin/asesor gestione las
respuestas aprendidas del bot."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from auth_routes import get_current_user, get_db
from models import User
from bot_learning_service import (
    save_learned_response, list_learned_responses, find_learned_answer,
)

router = APIRouter(tags=["bot-learning"])

_db_holder = {"db": None}


def init_router(db):
    _db_holder["db"] = db


def _get_db():
    return _db_holder["db"]


class SaveLearnedBody(BaseModel):
    question: str
    answer: str
    lead_phone: Optional[str] = ""
    notes: Optional[str] = ""


class UpdateLearnedBody(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    active: Optional[bool] = None
    notes: Optional[str] = None


@router.post("/bot-learning")
async def save_learned(
    body: SaveLearnedBody,
    current_user: User = Depends(get_current_user),
):
    """Asesor o admin: guarda una respuesta humana como respuesta válida del bot.

    El bot la va a usar literal cuando reciba preguntas similares de otros
    leads del mismo tenant. Si ya existía una con la misma pregunta normalizada,
    sobrescribe la answer.
    """
    if not body.question.strip() or not body.answer.strip():
        raise HTTPException(status_code=400, detail="Pregunta y respuesta son obligatorias")
    db = _get_db()
    doc = await save_learned_response(
        db=db,
        tenant_id=current_user.tenant_id,
        question=body.question.strip(),
        answer=body.answer.strip(),
        created_by=current_user.email or current_user.id,
        lead_phone=body.lead_phone or "",
        notes=body.notes or "",
    )
    return doc


@router.get("/bot-learning")
async def list_learned(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
):
    """Lista las respuestas aprendidas del tenant."""
    db = _get_db()
    items = await list_learned_responses(
        db, current_user.tenant_id, include_inactive=include_inactive,
    )
    return {"items": items, "count": len(items)}


@router.put("/bot-learning/{item_id}")
async def update_learned(
    item_id: str,
    body: UpdateLearnedBody,
    current_user: User = Depends(get_current_user),
):
    """Editar/desactivar una entrada."""
    db = _get_db()
    existing = await db.learned_responses.find_one(
        {"id": item_id, "tenant_id": current_user.tenant_id}, {"_id": 0},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="No existe")

    update_fields = {}
    if body.question is not None:
        update_fields["question"] = body.question
        from bot_learning_service import _normalize
        update_fields["question_normalized"] = _normalize(body.question)
    if body.answer is not None:
        update_fields["answer"] = body.answer
    if body.active is not None:
        update_fields["active"] = body.active
    if body.notes is not None:
        update_fields["notes"] = body.notes

    if not update_fields:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")

    from datetime import datetime, timezone
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.learned_responses.update_one(
        {"id": item_id, "tenant_id": current_user.tenant_id},
        {"$set": update_fields},
    )
    return await db.learned_responses.find_one(
        {"id": item_id}, {"_id": 0},
    )


@router.delete("/bot-learning/{item_id}")
async def delete_learned(
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    """Borra una entrada definitivamente. Para desactivar (preservar audit),
    usar PUT con active=false."""
    db = _get_db()
    res = await db.learned_responses.delete_one(
        {"id": item_id, "tenant_id": current_user.tenant_id},
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No existe")
    return {"deleted": True}


@router.post("/bot-learning/test")
async def test_learned(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Útil para que el admin pruebe si una pregunta hace match con alguna
    respuesta aprendida (debug)."""
    msg = (body or {}).get("message", "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Falta 'message'")
    db = _get_db()
    threshold = float((body or {}).get("threshold", 0.45))
    match = await find_learned_answer(
        db, current_user.tenant_id, msg, threshold=threshold,
    )
    return {"matched": bool(match), "match": match}
