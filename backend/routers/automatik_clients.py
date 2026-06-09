"""
routers/automatik_clients.py
============================
Endpoints del SuperAdmin de Automatik Media para gestionar clientes y pagos.

Colecciones MongoDB:
  - automatik_clients   → clientes (inmobiliarias que pagan la suite)
  - automatik_payments  → historial de pagos

Todos los endpoints requieren rol superadmin.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import uuid
import calendar

from auth_routes import get_current_user, require_superadmin, get_db
from models import User

router = APIRouter(prefix="/superadmin/clients", tags=["superadmin-clients"])

_db = get_db()

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

PLAN_PRICES = {"starter": 497, "pro": 997, "scale": 1997, "enterprise": 3997}
PLANS = list(PLAN_PRICES.keys())


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────

class ClientCreate(BaseModel):
    company_name: str
    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    plan: str = "pro"
    monthly_amount: Optional[float] = None
    currency: str = "USD"
    status: str = "active"
    start_date: Optional[str] = None
    next_payment_date: Optional[str] = None
    tenant_id: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    plan: Optional[str] = None
    monthly_amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    next_payment_date: Optional[str] = None
    tenant_id: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(BaseModel):
    client_id: str
    amount: float
    currency: str = "USD"
    payment_date: Optional[str] = None
    method: str = "transfer"
    status: str = "paid"
    period: Optional[str] = None
    notes: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Clientes CRUD
# ──────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_clients(
    search: str = Query(""),
    current_user: User = Depends(require_superadmin),
):
    query = {}
    if search:
        query = {"$or": [
            {"company_name": {"$regex": search, "$options": "i"}},
            {"contact_email": {"$regex": search, "$options": "i"}},
            {"contact_name": {"$regex": search, "$options": "i"}},
        ]}
    clients = []
    async for doc in _db.automatik_clients.find(query).sort("created_at", -1):
        clients.append(_clean(doc))
    return clients


@router.post("")
async def create_client(
    body: ClientCreate,
    current_user: User = Depends(require_superadmin),
):
    now = datetime.utcnow().isoformat()
    client_id = str(uuid.uuid4())
    amount = body.monthly_amount if body.monthly_amount is not None else PLAN_PRICES.get(body.plan, 997)
    doc = {
        "client_id": client_id,
        "company_name": body.company_name,
        "contact_name": body.contact_name,
        "contact_email": body.contact_email,
        "contact_phone": body.contact_phone,
        "plan": body.plan,
        "monthly_amount": amount,
        "currency": body.currency,
        "status": body.status,
        "start_date": body.start_date or date.today().isoformat(),
        "next_payment_date": body.next_payment_date,
        "tenant_id": body.tenant_id,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    await _db.automatik_clients.insert_one(doc)
    return _clean(doc)


@router.put("/{client_id}")
async def update_client(
    client_id: str,
    body: ClientUpdate,
    current_user: User = Depends(require_superadmin),
):
    existing = await _db.automatik_clients.find_one({"client_id": client_id})
    if not existing:
        raise HTTPException(404, "Cliente no encontrado")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if "plan" in updates and "monthly_amount" not in updates:
        updates["monthly_amount"] = PLAN_PRICES.get(updates["plan"], existing.get("monthly_amount", 997))
    updates["updated_at"] = datetime.utcnow().isoformat()
    await _db.automatik_clients.update_one({"client_id": client_id}, {"$set": updates})
    updated = await _db.automatik_clients.find_one({"client_id": client_id})
    return _clean(updated)


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    current_user: User = Depends(require_superadmin),
):
    result = await _db.automatik_clients.delete_one({"client_id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Cliente no encontrado")
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────────
# Pagos
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/payments/all")
async def list_payments(
    client_id: str = Query(""),
    limit: int = Query(100),
    current_user: User = Depends(require_superadmin),
):
    query = {}
    if client_id:
        query["client_id"] = client_id
    payments = []
    async for doc in _db.automatik_payments.find(query).sort("payment_date", -1).limit(limit):
        payments.append(_clean(doc))
    return payments


@router.post("/payments")
async def register_payment(
    body: PaymentCreate,
    current_user: User = Depends(require_superadmin),
):
    client = await _db.automatik_clients.find_one({"client_id": body.client_id})
    if not client:
        raise HTTPException(404, "Cliente no encontrado")

    now = datetime.utcnow().isoformat()
    payment_id = str(uuid.uuid4())
    payment_date_str = body.payment_date or date.today().isoformat()
    doc = {
        "payment_id": payment_id,
        "client_id": body.client_id,
        "company_name": client.get("company_name", ""),
        "amount": body.amount,
        "currency": body.currency,
        "payment_date": payment_date_str,
        "method": body.method,
        "status": body.status,
        "period": body.period or date.today().strftime("%Y-%m"),
        "notes": body.notes,
        "created_at": now,
    }
    await _db.automatik_payments.insert_one(doc)

    # Actualizar próximo vencimiento si el pago fue exitoso
    if body.status == "paid":
        try:
            payment_dt = date.fromisoformat(payment_date_str)
            month = payment_dt.month + 1
            year = payment_dt.year
            if month > 12:
                month = 1
                year += 1
            last_day = calendar.monthrange(year, month)[1]
            next_day = min(payment_dt.day, last_day)
            next_payment = date(year, month, next_day).isoformat()
            await _db.automatik_clients.update_one(
                {"client_id": body.client_id},
                {"$set": {"next_payment_date": next_payment, "updated_at": now}}
            )
        except Exception:
            pass

    return _clean(doc)


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard KPIs
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def dashboard_stats(
    current_user: User = Depends(require_superadmin),
):
    today = date.today()

    active_clients = await _db.automatik_clients.count_documents({"status": "active"})
    trial_clients = await _db.automatik_clients.count_documents({"status": "trial"})
    total_clients = await _db.automatik_clients.count_documents({})

    # MRR sumando clientes activos + trial en USD
    mrr = 0.0
    async for c in _db.automatik_clients.find({"status": {"$in": ["active", "trial"]}}):
        if c.get("currency", "USD") == "USD":
            mrr += c.get("monthly_amount", 0) or 0

    # Total cobrado histórico
    total_collected = 0.0
    async for p in _db.automatik_payments.find({"status": "paid", "currency": "USD"}):
        total_collected += p.get("amount", 0) or 0

    # Cobros venciendo en 30 días
    in_30 = (today.replace(day=min(today.day, 28)) if True else today)
    from datetime import timedelta
    in_30_iso = (today + timedelta(days=30)).isoformat()
    today_iso = today.isoformat()
    upcoming_payments = await _db.automatik_clients.count_documents({
        "status": "active",
        "next_payment_date": {"$gte": today_iso, "$lte": in_30_iso},
    })

    # Revenue por mes (últimos 6 meses)
    revenue_by_month = []
    for i in range(5, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        month_str = f"{year}-{month:02d}"
        total_m = 0.0
        async for p in _db.automatik_payments.find({
            "status": "paid", "currency": "USD", "period": month_str,
        }):
            total_m += p.get("amount", 0) or 0
        revenue_by_month.append({"month": month_str, "revenue": total_m})

    # Breakdown por plan
    plan_breakdown = []
    for plan in PLANS:
        count = await _db.automatik_clients.count_documents({"plan": plan, "status": "active"})
        if count > 0:
            plan_breakdown.append({"plan": plan, "count": count})

    return {
        "active_clients": active_clients,
        "trial_clients": trial_clients,
        "total_clients": total_clients,
        "mrr": mrr,
        "arr": mrr * 12,
        "total_collected": total_collected,
        "upcoming_payments_30d": upcoming_payments,
        "revenue_by_month": revenue_by_month,
        "plan_breakdown": plan_breakdown,
    }
