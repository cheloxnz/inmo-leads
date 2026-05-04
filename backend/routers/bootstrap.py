"""
Bootstrap router: creación del primer superadmin en un deploy fresco.

Protección:
- Solo funciona si NO existe todavía ningún superadmin en la DB.
- Requiere un `ADMIN_BOOTSTRAP_TOKEN` pasado como header o query param, que se
  compara con la env var del mismo nombre.
- Una vez creado el superadmin, el endpoint queda inutilizable (idempotente).

Uso esperado en producción:
1. Setear `ADMIN_BOOTSTRAP_TOKEN=<valor secreto>` en las env vars del deploy.
2. Desde tu máquina, llamar:
     curl -X POST https://inmobot-ia.com/api/admin/bootstrap \
       -H "Content-Type: application/json" \
       -H "X-Bootstrap-Token: <tu token>" \
       -d '{"email":"admin@inmobot.com","password":"XXX","name":"Super Admin"}'
3. Borrar `ADMIN_BOOTSTRAP_TOKEN` de las env vars (extra seguridad).
"""
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

from auth import get_password_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["bootstrap"])

_db_holder = {"db": None}


def init_router(db):
    _db_holder["db"] = db


def _db():
    return _db_holder["db"]


class BootstrapBody(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = "Super Admin"
    create_demo_tenant: bool = False
    demo_tenant_id: Optional[str] = "demo-inmobiliaria"
    demo_tenant_name: Optional[str] = "Demo Inmobiliaria"
    demo_admin_email: Optional[EmailStr] = None
    demo_admin_password: Optional[str] = None


@router.post("/bootstrap")
async def bootstrap_superadmin(
    body: BootstrapBody,
    x_bootstrap_token: Optional[str] = Header(None, alias="X-Bootstrap-Token"),
):
    expected = (os.environ.get("ADMIN_BOOTSTRAP_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Bootstrap deshabilitado: setear ADMIN_BOOTSTRAP_TOKEN en env vars del deploy",
        )
    if not x_bootstrap_token or x_bootstrap_token.strip() != expected:
        raise HTTPException(status_code=401, detail="Token de bootstrap inválido")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password debe tener al menos 8 caracteres")

    db = _db()
    existing = await db.agents.find_one({"role": "superadmin"}, {"_id": 0, "email": 1})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un superadmin ({existing['email']}). Este endpoint es one-shot.",
        )

    now = datetime.now(timezone.utc).isoformat()
    superadmin_doc = {
        "tenant_id": "__superadmin__",
        "name": body.name or "Super Admin",
        "email": body.email,
        "phone": "",
        "password_hash": get_password_hash(body.password),
        "role": "superadmin",
        "specialties": [],
        "zones": [],
        "max_concurrent_leads": 0,
        "active": True,
        "created_at": now,
    }
    await db.agents.insert_one(superadmin_doc)
    logger.info(f"[bootstrap] superadmin {body.email} creado")

    result = {
        "created": True,
        "superadmin_email": body.email,
        "demo_tenant_created": False,
    }

    if body.create_demo_tenant:
        demo_email = body.demo_admin_email or "demo@inmobot.com"
        demo_pass = body.demo_admin_password or "Demo123!"
        tenant_doc = {
            "tenant_id": body.demo_tenant_id or "demo-inmobiliaria",
            "name": body.demo_tenant_name or "Demo Inmobiliaria",
            "plan": "basic",
            "active": True,
            "whatsapp_phone_number_id": "",
            "whatsapp_access_token": "",
            "whatsapp_business_account_id": "",
            "webhook_verify_token": "",
            "max_leads": 500,
            "max_agents": 5,
            "subscription_status": "active",
            "subscription_plan": "basic",
            "contact_email": demo_email,
            "contact_phone": "",
            "country": "",
            "business_name": body.demo_tenant_name or "Demo Inmobiliaria",
            "business_tagline": "",
            "created_at": now,
            "updated_at": now,
        }
        await db.tenants.insert_one(tenant_doc)

        tenant_admin = {
            "tenant_id": tenant_doc["tenant_id"],
            "name": "Administrador Demo",
            "email": demo_email,
            "phone": "",
            "password_hash": get_password_hash(demo_pass),
            "role": "admin",
            "specialties": [],
            "zones": [],
            "max_concurrent_leads": 15,
            "active": True,
            "created_at": now,
        }
        await db.agents.insert_one(tenant_admin)

        result["demo_tenant_created"] = True
        result["demo_tenant_id"] = tenant_doc["tenant_id"]
        result["demo_admin_email"] = demo_email

    return result


@router.get("/bootstrap/status")
async def bootstrap_status():
    """Chequeo público (sin credenciales) para saber si el deploy ya tiene
    superadmin. Útil para que el frontend no muestre un error feo cuando la
    DB arranca vacía."""
    db = _db()
    existing = await db.agents.find_one({"role": "superadmin"}, {"_id": 0, "email": 1})
    return {
        "has_superadmin": bool(existing),
        "bootstrap_token_configured": bool(os.environ.get("ADMIN_BOOTSTRAP_TOKEN")),
    }
