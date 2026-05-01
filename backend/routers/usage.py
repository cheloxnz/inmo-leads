"""Router de uso/límites: usage summary + compra de packs IA via Stripe."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import get_current_user, require_admin, get_db
from models import User
from usage_service import UsageService
from payment_service import PaymentService

router = APIRouter(tags=["usage"])
logger = logging.getLogger(__name__)
_db = get_db()
usage_service = UsageService(_db)
payment_service = PaymentService(_db)


@router.get("/usage")
async def get_usage(current_user: User = Depends(get_current_user)):
    """Obtiene resumen de uso del tenant actual"""
    return await usage_service.get_usage_summary(current_user.tenant_id)


@router.post("/usage/buy-pack")
async def buy_ai_pack(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Compra un bloque de mensajes IA extra via Stripe"""
    pack_id = body.get("pack_id")
    from usage_service import AI_MESSAGE_PACKS
    pack = AI_MESSAGE_PACKS.get(pack_id)
    if not pack:
        raise HTTPException(status_code=400, detail="Pack no valido")
    if not payment_service.api_key:
        raise HTTPException(status_code=400, detail="Stripe no configurado")

    import stripe
    try:
        origin_url = body.get("origin_url", "")
        success_url = f"{origin_url}/config?pack=success&pack_id={pack_id}"
        cancel_url = f"{origin_url}/config?pack=cancelled"
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': pack["name"],
                        'description': f'{pack["messages"]} conversaciones IA adicionales para tu plan',
                    },
                    'unit_amount': int(pack["price"] * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "ai_pack",
                "pack_id": pack_id,
                "tenant_id": current_user.tenant_id,
                "messages": str(pack["messages"]),
            },
        )
        await _db.payment_transactions.insert_one({
            "session_id": session.id,
            "tenant_id": current_user.tenant_id,
            "type": "ai_pack",
            "pack_id": pack_id,
            "pack_name": pack["name"],
            "amount": pack["price"],
            "messages": pack["messages"],
            "currency": "usd",
            "payment_status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        })
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Error comprando pack: {e}")
        raise HTTPException(status_code=500, detail="Error creando sesion de pago")


@router.post("/usage/confirm-pack")
async def confirm_pack_purchase(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Confirma compra de pack (llamado despues del redirect de Stripe)"""
    pack_id = body.get("pack_id")
    if not pack_id:
        raise HTTPException(status_code=400, detail="pack_id requerido")
    result = await usage_service.add_extra_messages(current_user.tenant_id, pack_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await _db.payment_transactions.update_one(
        {"tenant_id": current_user.tenant_id, "pack_id": pack_id, "payment_status": "pending"},
        {"$set": {"payment_status": "paid", "paid_at": datetime.utcnow().isoformat()}},
    )
    return result
