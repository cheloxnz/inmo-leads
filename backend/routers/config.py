"""Router de configuración del tenant: bot config, WhatsApp, IA, flujos."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import get_current_user, require_admin, get_db, tenant_filter
from models import BotConfig, User

router = APIRouter(tags=["config"])
logger = logging.getLogger(__name__)
_db = get_db()


# ============================================
# Bot Config (general)
# ============================================

@router.get("/config")
async def get_config(current_user: User = Depends(get_current_user)):
    """Obtiene configuración del bot (por tenant)"""
    tf = tenant_filter(current_user)
    config = await _db.bot_config.find_one(tf, {"_id": 0})
    if not config:
        config = BotConfig(tenant_id=current_user.tenant_id).model_dump()
        config["updated_at"] = config["updated_at"].isoformat()
        await _db.bot_config.insert_one(config)
    return config


@router.put("/config")
async def update_config(config: BotConfig, current_user: User = Depends(require_admin)):
    """Actualiza configuración del bot (por tenant)"""
    config_dict = config.model_dump()
    config_dict["tenant_id"] = current_user.tenant_id
    config_dict["updated_at"] = datetime.utcnow().isoformat()
    await _db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": config_dict},
        upsert=True,
    )
    return {"message": "Configuración actualizada"}


# ============================================
# WhatsApp Config (per tenant)
# ============================================

@router.get("/config/whatsapp")
async def get_whatsapp_config(current_user: User = Depends(require_admin)):
    """Admin: Obtiene config de WhatsApp del tenant"""
    import os
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {
        "whatsapp_phone_number_id": tenant.get("whatsapp_phone_number_id", ""),
        "whatsapp_access_token": (
            "***" + tenant.get("whatsapp_access_token", "")[-10:]
            if tenant.get("whatsapp_access_token") else ""
        ),
        "whatsapp_business_account_id": tenant.get("whatsapp_business_account_id", ""),
        "webhook_verify_token": tenant.get("webhook_verify_token", ""),
        "webhook_url": f"{os.getenv('REACT_APP_BACKEND_URL', '')}/api/webhook",
        "configured": bool(
            tenant.get("whatsapp_access_token") and tenant.get("whatsapp_phone_number_id")
        ),
    }


@router.put("/config/whatsapp")
async def update_whatsapp_config(
    config: dict,
    current_user: User = Depends(require_admin),
):
    """Admin: Actualiza config de WhatsApp del tenant"""
    update_fields = {}
    allowed = [
        "whatsapp_phone_number_id",
        "whatsapp_access_token",
        "whatsapp_business_account_id",
        "webhook_verify_token",
    ]
    for key in allowed:
        if key in config:
            update_fields[key] = config[key]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    update_fields["updated_at"] = datetime.utcnow().isoformat()
    await _db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update_fields},
    )
    return {"message": "Configuracion de WhatsApp actualizada"}


# ============================================
# AI Config (per tenant)
# ============================================

@router.get("/config/ai")
async def get_ai_config(current_user: User = Depends(require_admin)):
    """Admin: Obtiene config de IA del tenant"""
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {
        "has_own_key": bool(tenant.get("openai_api_key")),
        "key_preview": (
            "***" + tenant.get("openai_api_key", "")[-8:]
            if tenant.get("openai_api_key") else ""
        ),
        "max_ai_messages": tenant.get("max_ai_messages", 2000),
        "model": "gpt-4o",
    }


@router.put("/config/ai")
async def update_ai_config(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Configura key propia de OpenAI (opcional)"""
    update = {}
    if "openai_api_key" in body:
        update["openai_api_key"] = body["openai_api_key"]
    if not update:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    update["updated_at"] = datetime.utcnow().isoformat()
    await _db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update},
    )
    return {"message": "Configuracion de IA actualizada"}


# ============================================
# Custom Flow Builder
# ============================================

@router.get("/flow/config")
async def get_flow_config(current_user: User = Depends(get_current_user)):
    """Obtiene la config del flujo del tenant (custom o template base)"""
    from flow_templates import get_template
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    template_id = tenant.get("template_id", "servicios") if tenant else "servicios"
    base_template = get_template(template_id)
    config = await _db.bot_config.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    return {
        "template_id": template_id,
        "template_name": base_template.get("name", ""),
        "is_customized": bool(config and config.get("custom_flow_steps")),
        "welcome_message": (config or {}).get("custom_welcome_message")
            or base_template.get("welcome_message", ""),
        "welcome_buttons": (config or {}).get("custom_welcome_buttons")
            or base_template.get("welcome_buttons", []),
        "flow_steps": (config or {}).get("custom_flow_steps")
            or base_template.get("flow_steps", []),
        "scoring": (config or {}).get("custom_scoring")
            or base_template.get("scoring", {}),
        "appointment_message": (config or {}).get("custom_appointment_message")
            or base_template.get("appointment_message", ""),
        "appointment_buttons": (config or {}).get("custom_appointment_buttons")
            or base_template.get("appointment_buttons", []),
        "completion_message": (config or {}).get("custom_completion_message")
            or base_template.get("completion_message", ""),
        "faq": (config or {}).get("custom_faq") or base_template.get("faq", {}),
        "labels": (config or {}).get("custom_labels") or base_template.get("labels", {}),
    }


@router.put("/flow/config")
async def update_flow_config(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Guarda config custom del flujo"""
    update = {"tenant_id": current_user.tenant_id}
    fields_map = {
        "welcome_message": "custom_welcome_message",
        "welcome_buttons": "custom_welcome_buttons",
        "flow_steps": "custom_flow_steps",
        "scoring": "custom_scoring",
        "appointment_message": "custom_appointment_message",
        "appointment_buttons": "custom_appointment_buttons",
        "completion_message": "custom_completion_message",
        "faq": "custom_faq",
        "labels": "custom_labels",
    }
    for key, db_key in fields_map.items():
        if key in body:
            update[db_key] = body[key]
    update["updated_at"] = datetime.utcnow().isoformat()
    await _db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update},
        upsert=True,
    )
    return {"message": "Flujo actualizado"}


@router.post("/flow/reset")
async def reset_flow_config(current_user: User = Depends(require_admin)):
    """Admin: Resetea el flujo custom al template base"""
    custom_fields = [
        "custom_flow_steps", "custom_welcome_message", "custom_welcome_buttons",
        "custom_scoring", "custom_appointment_message", "custom_appointment_buttons",
        "custom_completion_message", "custom_faq", "custom_labels",
    ]
    unset = {f: "" for f in custom_fields}
    await _db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$unset": unset},
    )
    return {"message": "Flujo reseteado al template base"}
