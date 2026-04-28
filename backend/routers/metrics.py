"""Router de metricas agregadas de leads por tenant"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends

from auth_routes import get_current_user, get_db, tenant_filter
from models import User

router = APIRouter(tags=["metrics"])

_db = get_db()


@router.get("/metrics/leads-by-day")
async def get_leads_by_day(days: int = 30, current_user: User = Depends(get_current_user)):
    start_date = datetime.utcnow() - timedelta(days=days)
    tf = tenant_filter(current_user, {"created_at": {"$gte": start_date.isoformat()}})
    pipeline = [
        {"$match": tf},
        {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    result = await _db.leads.aggregate(pipeline).to_list(100)
    return [{"date": r["_id"], "count": r["count"]} for r in result]


@router.get("/metrics/leads-by-status")
async def get_leads_by_status(current_user: User = Depends(get_current_user)):
    tf = tenant_filter(current_user)
    pipeline = [
        {"$match": tf},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    result = await _db.leads.aggregate(pipeline).to_list(10)
    return [{"status": r["_id"] or "unknown", "count": r["count"]} for r in result]


@router.get("/metrics/leads-by-intent")
async def get_leads_by_intent(current_user: User = Depends(get_current_user)):
    tf = tenant_filter(current_user)
    pipeline = [
        {"$match": tf},
        {"$group": {"_id": "$intent", "count": {"$sum": 1}}}
    ]
    result = await _db.leads.aggregate(pipeline).to_list(10)
    return [{"intent": r["_id"] or "sin_definir", "count": r["count"]} for r in result]


@router.get("/metrics/conversion-funnel")
async def get_conversion_funnel(current_user: User = Depends(get_current_user)):
    tf = tenant_filter(current_user)
    total = await _db.leads.count_documents(tf)
    qualified = await _db.leads.count_documents({**tf, "score": {"$gte": 30}})
    with_appointment = await _db.leads.count_documents({**tf, "appointment_datetime": {"$exists": True, "$ne": None}})
    hot = await _db.leads.count_documents({**tf, "status": "hot"})
    return {
        "total_leads": total,
        "qualified": qualified,
        "with_appointment": with_appointment,
        "hot_leads": hot,
        "qualification_rate": round((qualified / total * 100) if total > 0 else 0, 1),
        "appointment_rate": round((with_appointment / total * 100) if total > 0 else 0, 1),
        "conversion_rate": round((hot / total * 100) if total > 0 else 0, 1)
    }


@router.get("/metrics/messages")
async def get_messages_metrics(days: int = 30, current_user: User = Depends(get_current_user)):
    start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    tf = tenant_filter(current_user)

    pipeline = [
        {"$match": tf},
        {"$unwind": "$conversation_history"},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "from_customer": {
                "$sum": {"$cond": [{"$eq": ["$conversation_history.from", "customer"]}, 1, 0]}
            },
            "from_bot": {
                "$sum": {"$cond": [{"$eq": ["$conversation_history.from", "bot"]}, 1, 0]}
            }
        }}
    ]
    result = await _db.leads.aggregate(pipeline).to_list(1)

    pipeline_by_day = [
        {"$match": tf},
        {"$unwind": "$conversation_history"},
        {"$match": {"conversation_history.timestamp": {"$gte": start_date}}},
        {"$addFields": {"date": {"$substr": ["$conversation_history.timestamp", 0, 10]}}},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    by_day = await _db.leads.aggregate(pipeline_by_day).to_list(100)

    total_leads = await _db.leads.count_documents(tf)

    stats = result[0] if result else {"total": 0, "from_customer": 0, "from_bot": 0}
    recent_count = sum(d["count"] for d in by_day)

    return {
        "total_messages": stats.get("total", 0),
        "incoming_messages": stats.get("from_customer", 0),
        "outgoing_messages": stats.get("from_bot", 0),
        "messages_last_period": recent_count,
        "messages_by_day": [{"date": r["_id"], "count": r["count"]} for r in by_day],
        "avg_per_day": round(recent_count / days, 1) if days > 0 else 0,
        "total_leads": total_leads,
        "avg_messages_per_lead": round(stats.get("total", 0) / total_leads, 1) if total_leads > 0 else 0
    }
