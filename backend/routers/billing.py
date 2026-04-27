"""Router de billing y suscripciones SaaS (Stripe)"""
from fastapi import APIRouter, Depends, HTTPException, Request

from auth_routes import get_current_user, require_admin, get_db
from payment_service import PaymentService, SUBSCRIPTION_PLANS
from models import User

router = APIRouter(tags=["billing"])

_db = get_db()
payment_service = PaymentService(_db)


@router.get("/plans")
async def get_plans():
    """Lista planes disponibles (publico)"""
    return SUBSCRIPTION_PLANS


@router.post("/billing/subscribe")
async def subscribe_plan(body: dict, current_user: User = Depends(require_admin)):
    """Admin: inicia checkout de suscripcion"""
    plan_id = body.get("plan_id")
    origin_url = body.get("origin_url", "")
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id requerido")

    try:
        result = await payment_service.create_subscription_checkout(
            plan_id=plan_id,
            tenant_id=current_user.tenant_id,
            customer_email=current_user.email,
            origin_url=origin_url
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/billing")
async def get_billing(current_user: User = Depends(require_admin)):
    """Admin: Obtiene info de billing de su tenant"""
    return await payment_service.get_billing_info(current_user.tenant_id)


@router.post("/billing/cancel")
async def cancel_billing(current_user: User = Depends(require_admin)):
    """Admin: Cancela suscripcion al final del periodo"""
    return await payment_service.cancel_subscription(current_user.tenant_id)


@router.post("/billing/bill-overage")
async def bill_overage_endpoint(body: dict = None, current_user: User = Depends(get_current_user)):
    """SuperAdmin: factura el overage de IA del periodo (todos los tenants o uno)"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadmin")

    body = body or {}
    period = body.get("period")
    tenant_id = body.get("tenant_id")

    if tenant_id:
        return await payment_service.bill_overage_for_tenant(tenant_id, period)
    return await payment_service.bill_all_overages(period)


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Webhook para eventos de Stripe"""
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature", "")
        result = await payment_service.handle_webhook(body, signature)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/transactions")
async def get_transactions(current_user: User = Depends(require_admin)):
    """Admin/SuperAdmin: Obtiene transacciones"""
    if current_user.role == "superadmin":
        return await payment_service.get_all_transactions()
    txns = await _db.payment_transactions.find(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    return txns
