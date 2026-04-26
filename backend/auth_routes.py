from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
import os

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
