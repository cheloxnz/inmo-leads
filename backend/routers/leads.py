"""Router de leads: CRUD, kanban, stats, tags, AI summary."""
import csv
import io
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from auth_routes import get_current_user, tenant_filter, get_db
from models import Lead, LeadUpdate, User

router = APIRouter(tags=["leads"])

_db = get_db()


def _parse_lead_dates(lead: dict) -> dict:
    """Convierte strings ISO a datetime para los campos del modelo Lead."""
    for field in ("created_at", "last_message_at", "appointment_datetime"):
        val = lead.get(field)
        if isinstance(val, str):
            try:
                lead[field] = datetime.fromisoformat(val)
            except ValueError:
                pass
    return lead


@router.get("/leads", response_model=List[Lead])
async def get_leads(
    status: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """Obtiene lista de leads (filtrado por tenant)"""
    query = tenant_filter(current_user)
    if status:
        query["status"] = status
    leads = await _db.leads.find(
        query, {"_id": 0, "conversation_history": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    for lead in leads:
        _parse_lead_dates(lead)
    return leads


# NOTE: /leads/kanban y /leads/assigned-to-me DEBEN estar antes de /leads/{phone}
@router.get("/leads/kanban")
async def get_kanban_data(current_user: User = Depends(get_current_user)):
    """Obtiene leads organizados para vista Kanban (filtrado por tenant)"""
    match_stage = tenant_filter(current_user)
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$status",
            "leads": {"$push": {
                "phone": "$phone",
                "name": "$name",
                "zone": "$zone",
                "budget_text": "$budget_text",
                "score": "$score",
                "intent": "$intent",
                "appointment_datetime": "$appointment_datetime",
                "created_at": "$created_at",
                "tags": "$tags"
            }},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    results = await _db.leads.aggregate(pipeline).to_list(20)
    kanban_columns = {
        "new": {"title": "Nuevos", "leads": [], "count": 0},
        "contacted": {"title": "Contactados", "leads": [], "count": 0},
        "qualified": {"title": "Calificados", "leads": [], "count": 0},
        "appointment": {"title": "Cita Agendada", "leads": [], "count": 0},
        "hot": {"title": "Calientes", "leads": [], "count": 0},
        "warm": {"title": "Tibios", "leads": [], "count": 0},
        "cold": {"title": "Fríos", "leads": [], "count": 0},
        "completed": {"title": "Cerrados", "leads": [], "count": 0},
    }
    for result in results:
        status = result["_id"] or "new"
        if status in kanban_columns:
            kanban_columns[status]["leads"] = result["leads"][:20]
            kanban_columns[status]["count"] = result["count"]
    return kanban_columns


# Mapping de status técnico a label castellano (consistente con kanban_columns)
_STATUS_LABELS = {
    "new": "Nuevo",
    "contacted": "Contactado",
    "qualified": "Calificado",
    "appointment": "Cita Agendada",
    "hot": "Caliente",
    "warm": "Tibio",
    "cold": "Frío",
    "completed": "Cerrado",
}

# Columnas del CSV (orden importa)
_CSV_HEADERS = [
    "Nombre", "Teléfono", "Estado", "Score", "Tags",
    "Zona", "Presupuesto", "Intención", "Cita agendada",
    "Asesor asignado", "Notas", "Fuente",
    "Creado", "Última actualización",
]


def _fmt_dt(val) -> str:
    if not val:
        return ""
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val)
        except ValueError:
            return val
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M")
    return str(val)


def _lead_to_row(lead: dict) -> List[str]:
    return [
        lead.get("name") or "",
        lead.get("phone") or "",
        _STATUS_LABELS.get(lead.get("status", ""), lead.get("status", "")),
        str(lead.get("score") or 0),
        ", ".join(lead.get("tags") or []),
        lead.get("zone") or "",
        lead.get("budget_text") or "",
        lead.get("intent") or "",
        _fmt_dt(lead.get("appointment_datetime")),
        lead.get("assigned_agent_name") or "",
        (lead.get("notes") or "").replace("\n", " ").strip(),
        lead.get("source") or "",
        _fmt_dt(lead.get("created_at")),
        _fmt_dt(lead.get("last_message_at")),
    ]


@router.get("/leads/export")
async def export_leads_csv(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    days: Optional[int] = None,
    current_user: User = Depends(get_current_user),
):
    """Exporta leads del tenant a CSV (UTF-8 con BOM para Excel-friendly).

    Filtros opcionales:
    - `status`: kanban column key (new, contacted, qualified, appointment, hot,
      warm, cold, completed). Si es CSV con coma → múltiples.
    - `tag`: tag exacto a filtrar (ej. "interesado").
    - `days`: solo leads creados en los últimos N días.
    """
    query = tenant_filter(current_user)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            query["status"] = statuses[0]
        elif len(statuses) > 1:
            query["status"] = {"$in": statuses}
    if tag:
        query["tags"] = tag
    if days and days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query["created_at"] = {"$gte": cutoff}

    leads = await _db.leads.find(
        query, {"_id": 0, "conversation_history": 0}
    ).sort("created_at", -1).to_list(10000)

    buf = io.StringIO()
    # BOM para que Excel detecte UTF-8 correctamente
    buf.write("\ufeff")
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(_CSV_HEADERS)
    for lead in leads:
        writer.writerow(_lead_to_row(lead))

    buf.seek(0)
    filename = f"leads_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Total-Rows": str(len(leads)),
        },
    )


@router.get("/leads/assigned-to-me")
async def get_my_leads(
    current_user: User = Depends(get_current_user),
    status: Optional[str] = None,
    limit: int = 100,
):
    """Obtiene leads asignados al asesor actual"""
    query = tenant_filter(current_user, {"assigned_agent": current_user.email})
    if status:
        query["status"] = status
    leads = await _db.leads.find(
        query, {"_id": 0, "conversation_history": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    for lead in leads:
        _parse_lead_dates(lead)
    return leads


@router.get("/leads/stats/summary")
async def get_stats(current_user: User = Depends(get_current_user)):
    """Obtiene estadísticas de leads (filtrado por tenant)"""
    tf = tenant_filter(current_user)
    total = await _db.leads.count_documents(tf)
    hot = await _db.leads.count_documents({**tf, "status": "hot"})
    warm = await _db.leads.count_documents({**tf, "status": "warm"})
    cold = await _db.leads.count_documents({**tf, "status": "cold"})
    with_appointment = await _db.leads.count_documents(
        {**tf, "appointment_datetime": {"$exists": True, "$ne": None}}
    )
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_leads = await _db.leads.count_documents(
        {**tf, "created_at": {"$gte": today.isoformat()}}
    )
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_leads = await _db.leads.count_documents(
        {**tf, "created_at": {"$gte": week_ago.isoformat()}}
    )
    avg_score_pipeline = [
        {"$match": tf},
        {"$group": {"_id": None, "avg_score": {"$avg": "$score"}}},
    ]
    avg_result = await _db.leads.aggregate(avg_score_pipeline).to_list(1)
    avg_score = (
        avg_result[0]["avg_score"]
        if avg_result and avg_result[0].get("avg_score") is not None
        else 0
    )
    return {
        "total": total,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "with_appointment": with_appointment,
        "today": today_leads,
        "this_week": week_leads,
        "avg_score": round(avg_score, 2),
        "conversion_rate": round((hot / total * 100) if total > 0 else 0, 2),
    }


@router.get("/leads/{phone}")
async def get_lead(phone: str, current_user: User = Depends(get_current_user)):
    """Obtiene un lead específico (filtrado por tenant)"""
    query = tenant_filter(current_user, {"phone": phone})
    lead = await _db.leads.find_one(query, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    _parse_lead_dates(lead)
    return lead


@router.put("/leads/{phone}")
async def update_lead(
    phone: str,
    lead_update: LeadUpdate,
    current_user: User = Depends(get_current_user),
):
    """Actualiza un lead (filtrado por tenant)"""
    update_data = {
        k: v for k, v in lead_update.model_dump(exclude_unset=True).items() if v is not None
    }
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    query = tenant_filter(current_user, {"phone": phone})
    result = await _db.leads.update_one(query, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return {"message": "Lead actualizado"}


@router.delete("/leads/{phone}")
async def delete_lead(phone: str, current_user: User = Depends(get_current_user)):
    """Elimina un lead (filtrado por tenant)"""
    query = tenant_filter(current_user, {"phone": phone})
    result = await _db.leads.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return {"message": "Lead eliminado exitosamente"}


@router.post("/leads/{phone}/tags")
async def add_tag(
    phone: str,
    tag_data: dict,
    current_user: User = Depends(get_current_user),
):
    tag = tag_data.get("tag", "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag vacío")
    query = tenant_filter(current_user, {"phone": phone})
    result = await _db.leads.update_one(query, {"$addToSet": {"tags": tag}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return {"message": "Tag agregado", "tag": tag}


@router.delete("/leads/{phone}/tags/{tag}")
async def remove_tag(
    phone: str,
    tag: str,
    current_user: User = Depends(get_current_user),
):
    query = tenant_filter(current_user, {"phone": phone})
    result = await _db.leads.update_one(query, {"$pull": {"tags": tag}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Lead o tag no encontrado")
    return {"message": "Tag eliminado"}


@router.post("/leads/{phone}/ai-summary")
async def get_lead_ai_summary(
    phone: str,
    force: bool = False,
    current_user: User = Depends(get_current_user),
):
    """Genera (o devuelve cache) el resumen IA del lead.

    Gateado por feature flag `ai_lead_summary`. Solo el tenant del lead puede consultarlo.
    """
    from feature_flags import has_feature
    from lead_summary_service import generate_lead_summary

    if not current_user.tenant_id:
        raise HTTPException(403, detail="Tenant no resuelto")
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {"_id": 0, "features": 1},
    )
    if not has_feature(tenant or {}, "ai_lead_summary"):
        raise HTTPException(
            status_code=403,
            detail=(
                "Feature 'ai_lead_summary' no habilitada para tu cuenta. "
                "Contactá soporte para activarla."
            ),
        )
    summary = await generate_lead_summary(
        _db, current_user.tenant_id, phone, force=force,
    )
    if summary is None:
        raise HTTPException(404, detail="Lead no encontrado o LLM no configurado")
    return summary


@router.get("/tags")
async def get_all_tags(current_user: User = Depends(get_current_user)):
    tf = tenant_filter(current_user)
    pipeline = [
        {"$match": tf},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    tags = await _db.leads.aggregate(pipeline).to_list(100)
    return [{"tag": t["_id"], "count": t["count"]} for t in tags]
