from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
import os

from models import Agent, AgentCreate, AgentLogin, User
from auth import verify_password, get_password_hash, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

def get_db():
    from server import db
    return db

async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """Obtiene usuario actual desde token JWT"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Token inv\u00e1lido o expirado")
    
    email = payload.get("sub")
    role = payload.get("role", "asesor")
    name = payload.get("name", "")
    
    return User(email=email, name=name, role=role)

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Requiere rol de administrador"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado. Requiere rol admin")
    return current_user

@router.post("/login")
async def login(credentials: AgentLogin, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Login de asesor o admin"""
    agent = await db.agents.find_one({"email": credentials.email}, {"_id": 0})
    
    if not agent:
        raise HTTPException(status_code=401, detail="Credenciales inv\u00e1lidas")
    
    if not agent.get("password_hash"):
        raise HTTPException(status_code=401, detail="Usuario sin password configurado")
    
    if not verify_password(credentials.password, agent["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inv\u00e1lidas")
    
    if not agent.get("active"):
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    
    token_data = {
        "sub": agent["email"],
        "name": agent["name"],
        "role": agent.get("role", "asesor")
    }
    
    access_token = create_access_token(token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": agent["email"],
            "name": agent["name"],
            "role": agent.get("role", "asesor"),
            "phone": agent.get("phone")
        }
    }

@router.post("/register")
async def register_agent(agent_data: AgentCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Registra nuevo asesor (solo admin puede hacer esto idealmente)"""
    existing = await db.agents.find_one({"email": agent_data.email})
    
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    agent = Agent(
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

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtiene informaci\u00f3n del usuario actual"""
    agent = await db.agents.find_one({"email": current_user.email}, {"_id": 0, "password_hash": 0})
    
    if not agent:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return agent

@router.get("/agents")
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Lista todos los asesores (admin) o solo el propio perfil (asesor)"""
    if current_user.role == "admin":
        agents = await db.agents.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
        
        for agent in agents:
            if isinstance(agent.get("created_at"), str):
                agent["created_at"] = datetime.fromisoformat(agent["created_at"])
        
        return agents
    else:
        agent = await db.agents.find_one({"email": current_user.email}, {"_id": 0, "password_hash": 0})
        return [agent] if agent else []

@router.put("/agents/{email}")
async def update_agent(
    email: str,
    agent_update: dict,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Actualiza un asesor (solo admin)"""
    if "password" in agent_update:
        agent_update["password_hash"] = get_password_hash(agent_update.pop("password"))
    
    result = await db.agents.update_one(
        {"email": email},
        {"$set": agent_update}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asesor no encontrado")
    
    return {"message": "Asesor actualizado"}

@router.delete("/agents/{email}")
async def delete_agent(
    email: str,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Elimina un asesor (solo admin)"""
    result = await db.agents.delete_one({"email": email})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asesor no encontrado")
    
    return {"message": "Asesor eliminado"}
