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
    status: str = Query(""),
    method: str = Query(""),
    period: str = Query(""),          # formato YYYY-MM
    search: str = Query(""),          # busca por company_name
    limit: int = Query(500),
    current_user: User = Depends(require_superadmin),
):
    query = {}
    if client_id:
        query["client_id"] = client_id
    if status:
        query["status"] = status
    if method:
        query["method"] = method
    if period:
        query["period"] = period
    if search:
        query["company_name"] = {"$regex": search, "$options": "i"}
    payments = []
    async for doc in _db.automatik_payments.find(query).sort("payment_date", -1).limit(limit):
        payments.append(_clean(doc))
    return payments


@router.delete("/payments/{payment_id}")
async def delete_payment(
    payment_id: str,
    current_user: User = Depends(require_superadmin),
):
    result = await _db.automatik_payments.delete_one({"payment_id": payment_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Pago no encontrado")
    return {"ok": True}


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
# Leads del Bot Automatik
# ──────────────────────────────────────────────────────────────────────────────

@router.delete("/leads/{lead_phone}")
async def delete_automatik_lead(
    lead_phone: str,
    current_user: User = Depends(require_superadmin),
):
    result = await _db.leads.delete_one({"phone": lead_phone, "tenant_id": "automatik-media"})
    if result.deleted_count == 0:
        raise HTTPException(404, "Lead no encontrado")
    return {"ok": True}


@router.get("/leads")
async def list_automatik_leads(
    status: str = Query(""),
    search: str = Query(""),
    limit: int = Query(200),
    current_user: User = Depends(require_superadmin),
):
    """Devuelve leads del tenant automatik-media con sus respuestas B2B."""
    query: dict = {"tenant_id": "automatik-media"}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
        ]
    leads = []
    async for doc in _db.leads.find(query, {"_id": 0}).sort("created_at", -1).limit(limit):
        leads.append(doc)
    return leads


# ──────────────────────────────────────────────────────────────────────────────
# Gastos
# ──────────────────────────────────────────────────────────────────────────────

EXPENSE_CATEGORIES = ["ia", "herramientas", "ads", "infraestructura", "equipo", "otro"]


class ExpenseCreate(BaseModel):
    name: str
    category: str = "otro"
    amount: float
    currency: str = "USD"
    period: Optional[str] = None       # YYYY-MM, default mes actual
    date: Optional[str] = None
    recurrent: bool = False            # se replica automáticamente cada mes
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    date: Optional[str] = None
    recurrent: Optional[bool] = None
    notes: Optional[str] = None


@router.get("/expenses")
async def list_expenses(
    period: str = Query(""),
    category: str = Query(""),
    current_user: User = Depends(require_superadmin),
):
    query: dict = {}
    if period:
        query["period"] = period
    if category:
        query["category"] = category
    expenses = []
    async for doc in _db.automatik_expenses.find(query).sort("date", -1):
        expenses.append(_clean(doc))
    return expenses


@router.post("/expenses")
async def create_expense(
    body: ExpenseCreate,
    current_user: User = Depends(require_superadmin),
):
    now = datetime.utcnow().isoformat()
    today = date.today()
    expense_id = str(uuid.uuid4())
    doc = {
        "expense_id": expense_id,
        "name": body.name,
        "category": body.category,
        "amount": body.amount,
        "currency": body.currency,
        "period": body.period or today.strftime("%Y-%m"),
        "date": body.date or today.isoformat(),
        "recurrent": body.recurrent,
        "notes": body.notes,
        "created_at": now,
    }
    await _db.automatik_expenses.insert_one(doc)
    return _clean(doc)


@router.put("/expenses/{expense_id}")
async def update_expense(
    expense_id: str,
    body: ExpenseUpdate,
    current_user: User = Depends(require_superadmin),
):
    existing = await _db.automatik_expenses.find_one({"expense_id": expense_id})
    if not existing:
        raise HTTPException(404, "Gasto no encontrado")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    await _db.automatik_expenses.update_one({"expense_id": expense_id}, {"$set": updates})
    updated = await _db.automatik_expenses.find_one({"expense_id": expense_id})
    return _clean(updated)


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: str,
    current_user: User = Depends(require_superadmin),
):
    result = await _db.automatik_expenses.delete_one({"expense_id": expense_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Gasto no encontrado")
    return {"ok": True}


@router.post("/expenses/replicate-recurrent")
async def replicate_recurrent(
    target_period: str = Query(...),   # YYYY-MM al que copiar
    current_user: User = Depends(require_superadmin),
):
    """Copia los gastos recurrentes del mes anterior al período indicado."""
    # mes anterior
    year, month = map(int, target_period.split("-"))
    prev_month = month - 1 or 12
    prev_year = year if month > 1 else year - 1
    source_period = f"{prev_year}-{prev_month:02d}"

    copied = 0
    async for doc in _db.automatik_expenses.find({"period": source_period, "recurrent": True}):
        existing = await _db.automatik_expenses.find_one(
            {"name": doc["name"], "period": target_period, "recurrent": True}
        )
        if existing:
            continue
        new_doc = {k: v for k, v in doc.items() if k != "_id"}
        new_doc["expense_id"] = str(uuid.uuid4())
        new_doc["period"] = target_period
        new_doc["date"] = f"{target_period}-01"
        new_doc["created_at"] = datetime.utcnow().isoformat()
        await _db.automatik_expenses.insert_one(new_doc)
        copied += 1
    return {"copied": copied, "source": source_period, "target": target_period}


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
