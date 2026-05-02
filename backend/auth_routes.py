from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import logging

logger = logging.getLogger(__name__)

from models import Agent, AgentCreate, AgentLogin, User, Tenant, TenantCreate
from auth import verify_password, get_password_hash, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
_client = AsyncIOMotorClient(mongo_url)
_db = _client[os.environ['DB_NAME']]

def get_db():
    return _db


# ============================================
# Auth Dependencies
# ============================================

async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """Obtiene usuario actual desde token JWT (incluye tenant_id)"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")

    email = payload.get("sub")
    role = payload.get("role", "asesor")
    name = payload.get("name", "")
    tenant_id = payload.get("tenant_id", "")

    return User(email=email, name=name, role=role, tenant_id=tenant_id)

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Requiere rol admin o superadmin"""
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Acceso denegado. Requiere rol admin")
    return current_user

async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Requiere rol superadmin (dueño del SaaS)"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado. Requiere rol superadmin")
    return current_user


def tenant_filter(user: User, extra: dict = None) -> dict:
    """Helper: construye filtro por tenant_id. Superadmin ve todo."""
    if user.role == "superadmin":
        q = {}
    else:
        q = {"tenant_id": user.tenant_id}
    if extra:
        q.update(extra)
    return q


# ============================================
# Login
# ============================================

@router.post("/login")
async def login(credentials: AgentLogin, db: AsyncIOMotorDatabase = Depends(get_db)):
    agent = await db.agents.find_one({"email": credentials.email}, {"_id": 0})

    if not agent:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    if not agent.get("password_hash"):
        raise HTTPException(status_code=401, detail="Usuario sin password configurado")

    if not verify_password(credentials.password, agent["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    if not agent.get("active", True):
        raise HTTPException(status_code=401, detail="Usuario inactivo")

    # Check tenant is active (skip for superadmin)
    tenant_id = agent.get("tenant_id", "")
    if agent.get("role") != "superadmin" and tenant_id:
        tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant or not tenant.get("active", True):
            raise HTTPException(status_code=403, detail="Cuenta suspendida. Contacte soporte.")
        if tenant.get("subscription_status") == "suspended":
            raise HTTPException(status_code=403, detail="Suscripcion suspendida. Contacte soporte.")

    token_data = {
        "sub": agent["email"],
        "name": agent["name"],
        "role": agent.get("role", "asesor"),
        "tenant_id": tenant_id
    }

    access_token = create_access_token(token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": agent["email"],
            "name": agent["name"],
            "role": agent.get("role", "asesor"),
            "phone": agent.get("phone", ""),
            "tenant_id": tenant_id
        }
    }


# ============================================
# User Profile
# ============================================

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    agent = await db.agents.find_one({"email": current_user.email}, {"_id": 0, "password_hash": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return agent

@router.put("/change-password")
async def change_password(
    password_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    current_password = password_data.get("current_password")
    new_password = password_data.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Se requiere contrasena actual y nueva")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="La nueva contrasena debe tener al menos 6 caracteres")

    agent = await db.agents.find_one({"email": current_user.email})
    if not agent:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not verify_password(current_password, agent.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Contrasena actual incorrecta")

    new_hash = get_password_hash(new_password)
    await db.agents.update_one(
        {"email": current_user.email},
        {"$set": {"password_hash": new_hash}}
    )

    return {"message": "Contrasena actualizada exitosamente"}


# ============================================
# Onboarding Tour (Iter33c)
# ============================================

@router.get("/onboarding/status")
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Retorna si el usuario completó el onboarding tour.

    El flag se guarda en el agente (no en el tenant) para que cada usuario
    haga el tour una sola vez aunque compartan tenant.
    """
    agent = await db.agents.find_one(
        {"email": current_user.email},
        {"_id": 0, "onboarding_completed": 1, "onboarding_started_at": 1},
    )
    return {
        "completed": bool(agent and agent.get("onboarding_completed")),
        "started_at": (agent or {}).get("onboarding_started_at"),
    }


@router.post("/onboarding/complete")
async def complete_onboarding(
    body: dict = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Marca el onboarding como completado. Body opcional: `{skipped: bool}`."""
    from datetime import datetime, timezone
    skipped = bool((body or {}).get("skipped", False))
    await db.agents.update_one(
        {"email": current_user.email},
        {"$set": {
            "onboarding_completed": True,
            "onboarding_completed_at": datetime.now(timezone.utc).isoformat(),
            "onboarding_skipped": skipped,
        }},
    )
    return {"ok": True, "skipped": skipped}




# ============================================
# Agent Management (tenant-scoped)
# ============================================

@router.post("/register")
async def register_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    existing = await db.agents.find_one({"email": agent_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    agent = Agent(
        tenant_id=current_user.tenant_id,
        name=agent_data.name,
        email=agent_data.email,
        phone=agent_data.phone,
        password_hash=get_password_hash(agent_data.password),
        specialties=agent_data.specialties,
        zones=agent_data.zones,
        role="asesor"
    )

    agent_dict = agent.model_dump()
    agent_dict["created_at"] = agent.created_at.isoformat()

    await db.agents.insert_one(agent_dict)

    return {"message": "Asesor registrado exitosamente", "email": agent.email}

@router.get("/agents")
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if current_user.role == "superadmin":
        agents = await db.agents.find({}, {"_id": 0, "password_hash": 0}).to_list(200)
    elif current_user.role == "admin":
        agents = await db.agents.find(
            {"tenant_id": current_user.tenant_id},
            {"_id": 0, "password_hash": 0}
        ).to_list(100)
    else:
        agent = await db.agents.find_one(
            {"email": current_user.email},
            {"_id": 0, "password_hash": 0}
        )
        return [agent] if agent else []

    for agent in agents:
        if isinstance(agent.get("created_at"), str):
            agent["created_at"] = datetime.fromisoformat(agent["created_at"])

    return agents

@router.put("/agents/{email}")
async def update_agent(
    email: str,
    agent_update: dict,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if "password" in agent_update:
        agent_update["password_hash"] = get_password_hash(agent_update.pop("password"))

    # Non-superadmin can only update agents in their tenant
    query = {"email": email}
    if current_user.role != "superadmin":
        query["tenant_id"] = current_user.tenant_id

    result = await db.agents.update_one(query, {"$set": agent_update})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asesor no encontrado")

    return {"message": "Asesor actualizado"}

@router.delete("/agents/{email}")
async def delete_agent(
    email: str,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    query = {"email": email}
    if current_user.role != "superadmin":
        query["tenant_id"] = current_user.tenant_id

    result = await db.agents.delete_one(query)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asesor no encontrado")

    return {"message": "Asesor eliminado"}


# ============================================
# Tenant Management (superadmin only)
# ============================================

@router.post("/tenants")
async def create_tenant(
    data: TenantCreate,
    current_user: User = Depends(require_superadmin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Superadmin: Crea un nuevo tenant (inmobiliaria cliente)"""
    existing = await db.tenants.find_one({"tenant_id": data.tenant_id})
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un tenant con ese ID")

    existing_email = await db.agents.find_one({"email": data.admin_email})
    if existing_email:
        raise HTTPException(status_code=400, detail="Email del admin ya registrado")

    # Create tenant
    tenant = Tenant(
        tenant_id=data.tenant_id,
        name=data.name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        country=data.country,
        plan=data.plan,
        business_name=data.name
    )
    tenant_dict = tenant.model_dump()
    tenant_dict["created_at"] = tenant.created_at.isoformat()
    tenant_dict["updated_at"] = tenant.updated_at.isoformat()
    await db.tenants.insert_one(tenant_dict)

    # Create admin user for this tenant
    admin = Agent(
        tenant_id=data.tenant_id,
        name=data.admin_name,
        email=data.admin_email,
        phone=data.contact_phone,
        password_hash=get_password_hash(data.admin_password),
        role="admin"
    )
    admin_dict = admin.model_dump()
    admin_dict["created_at"] = admin.created_at.isoformat()
    await db.agents.insert_one(admin_dict)

    return {
        "message": f"Tenant '{data.name}' creado exitosamente",
        "tenant_id": data.tenant_id,
        "admin_email": data.admin_email
    }

@router.get("/tenants")
async def list_tenants(
    current_user: User = Depends(require_superadmin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Superadmin: Lista todos los tenants"""
    tenants = await db.tenants.find({}, {"_id": 0}).to_list(200)
    # Add stats per tenant
    for t in tenants:
        tid = t["tenant_id"]
        t["leads_count"] = await db.leads.count_documents({"tenant_id": tid})
        t["agents_count"] = await db.agents.count_documents({"tenant_id": tid})
    return tenants

@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    current_user: User = Depends(require_superadmin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Superadmin: Obtiene detalle de un tenant"""
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return tenant

@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    update_data: dict,
    current_user: User = Depends(require_superadmin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Superadmin: Actualiza un tenant"""
    update_data.pop("tenant_id", None)  # No permitir cambiar el ID
    update_data["updated_at"] = datetime.utcnow().isoformat()

    result = await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    return {"message": "Tenant actualizado"}


import re
import time
from collections import defaultdict, deque

# Branding: campos que el tenant admin puede editar de su propio tenant
_BRANDING_ALLOWED_FIELDS = {
    "business_name", "business_tagline", "logo_url",
    "primary_color", "accent_color", "hero_bg_url",
    "template_id", "contact_phone", "whatsapp_display_phone",
    "country", "custom_features", "custom_steps",
    "palette_warn_disabled",
}

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_URL_RE = re.compile(r"^https?://[^\s<>\"']+$")

# Rate-limit AI Copy Gen: 5 calls/hora por tenant
_AI_RATE_MAX = 5
_AI_RATE_WINDOW = 3600
_ai_rate_buckets = defaultdict(deque)


def _validate_branding_payload(data: dict) -> tuple[dict, list, list]:
    """Valida y sanitiza payload de branding.

    Retorna (safe, rejected, errors):
      safe: dict con campos validos para guardar
      rejected: campos no en whitelist (auditoria)
      errors: lista de mensajes de error de validacion
    """
    safe = {}
    rejected = []
    errors = []

    for k, v in (data or {}).items():
        if k not in _BRANDING_ALLOWED_FIELDS:
            rejected.append(k)
            continue

        # Validacion por tipo de campo
        if k in ("primary_color", "accent_color"):
            if v and not _HEX_COLOR_RE.match(str(v)):
                errors.append(f"{k}: debe ser hex color #rrggbb")
                continue
        elif k in ("logo_url", "hero_bg_url"):
            if v and not _URL_RE.match(str(v)):
                errors.append(f"{k}: debe ser URL http(s) valida")
                continue
        elif k in ("custom_features", "custom_steps"):
            if not isinstance(v, list):
                errors.append(f"{k}: debe ser una lista")
                continue
            if len(v) > 5:
                errors.append(f"{k}: maximo 5 items")
                continue
        elif k == "palette_warn_disabled":
            if not isinstance(v, bool):
                errors.append(f"{k}: debe ser true/false")
                continue
        elif k == "template_id":
            valid = {"inmobiliaria", "clinica", "restaurante", "ecommerce", "servicios"}
            if v not in valid:
                errors.append(f"template_id: debe ser uno de {sorted(valid)}")
                continue
        elif isinstance(v, str) and len(v) > 500:
            errors.append(f"{k}: demasiado largo (>500 chars)")
            continue

        safe[k] = v

    return safe, rejected, errors


@router.get("/tenant/branding")
async def get_my_branding(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Tenant admin: lee la branding de su propio tenant"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Sin tenant")
    tenant = await db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    # Solo devolver campos de branding (no leak credenciales)
    _LIST_FIELDS = {"custom_features", "custom_steps"}
    out = {}
    for k in list(_BRANDING_ALLOWED_FIELDS) + ["tenant_id", "name"]:
        default = [] if k in _LIST_FIELDS else ""
        val = tenant.get(k, default)
        # Normalizar: si por datos legados custom_features/steps vienen como "" -> []
        if k in _LIST_FIELDS and not isinstance(val, list):
            val = [] if not val else val
        out[k] = val
    # Read-only: subscription info para que la UI muestre upsells/limites correctamente
    out["subscription_plan"] = tenant.get("subscription_plan", "")
    out["subscription_status"] = tenant.get("subscription_status", "")
    # Feature flags efectivos del tenant (combina defaults + overrides)
    from feature_flags import get_tenant_features
    out["features"] = get_tenant_features(tenant)
    return out


@router.put("/tenant/branding")
async def update_my_branding(
    update_data: dict,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Tenant admin: actualiza la branding/landing de su propio tenant"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Sin tenant")

    safe, rejected, errors = _validate_branding_payload(update_data)

    # Log de auditoria si hay rechazos por whitelist (intento de elevacion)
    if rejected:
        logger.warning(
            f"[AUDIT] tenant={current_user.tenant_id} user={current_user.email} "
            f"intento de modificar campos NO permitidos: {rejected}"
        )
        await db.audit_log.insert_one({
            "tenant_id": current_user.tenant_id,
            "user_email": current_user.email,
            "action": "branding_rejected_fields",
            "rejected_fields": rejected,
            "timestamp": datetime.utcnow().isoformat()
        })

    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    if not safe:
        raise HTTPException(status_code=400, detail="Sin campos validos")

    safe["updated_at"] = datetime.utcnow().isoformat()
    result = await db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": safe}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {
        "message": "Branding actualizado",
        "updated_fields": list(safe.keys()),
        "rejected_fields": rejected,
    }


@router.post("/tenant/branding/ai-generate")
async def ai_generate_branding(
    body: dict,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Tenant admin: genera copy para landing usando IA desde una descripcion del negocio.
    Rate-limit: 5 calls/hora por tenant."""
    description = (body or {}).get("description", "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="description es requerido")
    if len(description) > 500:
        raise HTTPException(status_code=400, detail="description demasiado larga (>500 chars)")

    # Rate-limit por tenant (Redis-backed con fallback in-memory)
    from rate_limit import check_rate_limit, get_retry_after
    rate_key = f"ai-gen:{current_user.tenant_id}"
    allowed, remaining = await check_rate_limit(rate_key, _AI_RATE_MAX, _AI_RATE_WINDOW)
    if not allowed:
        retry_in = await get_retry_after(rate_key, _AI_RATE_WINDOW)
        raise HTTPException(
            status_code=429,
            detail=f"Limite de IA alcanzado ({_AI_RATE_MAX}/hora). Reintentar en {retry_in}s."
        )

    from llm_service import create_llm_for_tenant
    tenant = await db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    llm = create_llm_for_tenant(tenant)
    result = await llm.generate_landing_copy(description)
    result["rate_limit"] = {
        "remaining": remaining,
        "max": _AI_RATE_MAX,
        "window_seconds": _AI_RATE_WINDOW
    }
    return result


@router.delete("/tenants/{tenant_id}")
async def deactivate_tenant(
    tenant_id: str,
    current_user: User = Depends(require_superadmin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Superadmin: Desactiva un tenant (no borra datos)"""
    result = await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"active": False, "subscription_status": "cancelled", "updated_at": datetime.utcnow().isoformat()}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    # Deactivate all agents of this tenant
    await db.agents.update_many(
        {"tenant_id": tenant_id},
        {"$set": {"active": False}}
    )

    return {"message": f"Tenant '{tenant_id}' desactivado"}
