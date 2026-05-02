"""Router de branding/whitelabel.

Expone endpoints para:
- Admin del tenant: configurar logo, color, brand_name, custom_subdomain.
- Público: resolver branding por subdomain (para que el frontend cargue el logo
  antes del login cuando accede vía `cliente1.inmobot.app`).

Subdominios reservados que NO pueden usarse como custom:
  www, api, admin, app, blog, mail, static, cdn, dev, staging, superadmin
"""
import logging
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import require_admin, get_db
from models import User

router = APIRouter(tags=["branding"])
logger = logging.getLogger(__name__)
_db = get_db()

RESERVED_SUBDOMAINS = {
    "www", "api", "admin", "app", "blog", "mail", "static",
    "cdn", "dev", "staging", "superadmin", "public", "help", "docs",
    "support", "status", "auth", "login", "signup",
}
SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@router.get("/branding")
async def get_my_branding(current_user: User = Depends(require_admin)):
    """Admin: lee la config de branding del tenant."""
    t = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {
            "_id": 0, "business_name": 1, "brand_name": 1,
            "logo_url": 1, "primary_color": 1, "custom_subdomain": 1,
            "whitelabel_enabled": 1,
        },
    )
    if not t:
        raise HTTPException(404, "Tenant no encontrado")
    return {
        "business_name": t.get("business_name", ""),
        "brand_name": t.get("brand_name", "") or t.get("business_name", ""),
        "logo_url": t.get("logo_url", ""),
        "primary_color": t.get("primary_color", "#6366f1"),
        "custom_subdomain": t.get("custom_subdomain", ""),
        "whitelabel_enabled": bool(t.get("whitelabel_enabled", False)),
    }


@router.put("/branding")
async def update_my_branding(
    body: dict,
    current_user: User = Depends(require_admin),
):
    """Admin: actualiza branding. Disponible sólo para planes pro/enterprise."""
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {"_id": 0, "subscription_plan": 1},
    )
    if not tenant:
        raise HTTPException(404, "Tenant no encontrado")
    plan = tenant.get("subscription_plan", "trial")
    if plan not in {"pro", "enterprise"}:
        raise HTTPException(
            403,
            "Whitelabel solo disponible en plan Pro o Enterprise. Upgradeá para desbloquear.",
        )

    update = {}
    for key in ("brand_name", "logo_url"):
        if key in body and body[key] is not None:
            update[key] = str(body[key]).strip()[:200]

    if "primary_color" in body and body["primary_color"] is not None:
        color = str(body["primary_color"]).strip()
        if color and not HEX_COLOR_RE.match(color):
            raise HTTPException(400, "primary_color debe ser hex (ej: #6366f1)")
        update["primary_color"] = color

    if "custom_subdomain" in body and body["custom_subdomain"] is not None:
        sub = str(body["custom_subdomain"]).strip().lower()
        if sub:
            if not SUBDOMAIN_RE.match(sub):
                raise HTTPException(
                    400,
                    "Subdomain inválido: solo a-z, 0-9, guiones (no al inicio/final), 2-32 chars",
                )
            if sub in RESERVED_SUBDOMAINS:
                raise HTTPException(400, f"'{sub}' es un subdomain reservado")
            # Unique check
            clash = await _db.tenants.find_one(
                {
                    "custom_subdomain": sub,
                    "tenant_id": {"$ne": current_user.tenant_id},
                },
                {"_id": 0, "tenant_id": 1},
            )
            if clash:
                raise HTTPException(409, f"Subdomain '{sub}' ya está en uso")
        update["custom_subdomain"] = sub

    if not update:
        raise HTTPException(400, "Ningún campo válido enviado")

    update["whitelabel_enabled"] = True
    update["branding_updated_at"] = datetime.now(timezone.utc).isoformat()

    await _db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update},
    )
    return {"ok": True, "updated": list(update.keys())}


@router.get("/public/branding/{subdomain}")
async def get_public_branding(subdomain: str):
    """Público: resuelve branding por custom_subdomain para que el frontend
    cargue el logo antes del login cuando accede vía `cliente1.inmobot.app`.

    Retorna 404 si el subdomain no existe.
    """
    sub = (subdomain or "").strip().lower()
    if not sub or sub in RESERVED_SUBDOMAINS:
        raise HTTPException(404, "No encontrado")
    tenant = await _db.tenants.find_one(
        {"custom_subdomain": sub, "whitelabel_enabled": True, "active": True},
        {
            "_id": 0, "tenant_id": 1, "business_name": 1, "brand_name": 1,
            "logo_url": 1, "primary_color": 1,
        },
    )
    if not tenant:
        raise HTTPException(404, "Subdomain no encontrado")
    return {
        "tenant_id": tenant["tenant_id"],
        "brand_name": tenant.get("brand_name") or tenant.get("business_name", ""),
        "logo_url": tenant.get("logo_url", ""),
        "primary_color": tenant.get("primary_color", "#6366f1"),
    }


@router.get("/branding/check-subdomain/{subdomain}")
async def check_subdomain_availability(
    subdomain: str,
    current_user: User = Depends(require_admin),
):
    """Admin: chequea si un subdomain está disponible (antes de guardar)."""
    sub = (subdomain or "").strip().lower()
    if not sub:
        return {"available": False, "reason": "vacío"}
    if not SUBDOMAIN_RE.match(sub):
        return {"available": False, "reason": "formato inválido"}
    if sub in RESERVED_SUBDOMAINS:
        return {"available": False, "reason": "reservado"}
    clash = await _db.tenants.find_one(
        {
            "custom_subdomain": sub,
            "tenant_id": {"$ne": current_user.tenant_id},
        },
        {"_id": 0, "tenant_id": 1},
    )
    if clash:
        return {"available": False, "reason": "ya en uso"}
    return {"available": True, "url": f"{sub}.inmobot.app"}
