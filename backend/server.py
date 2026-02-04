from fastapi import FastAPI, APIRouter, Request, Response, Header, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncio

from models import (
    Lead, LeadCreate, LeadUpdate, Agent, BotConfig,
    LeadStatus, FlowStage
)
from whatsapp_service import WhatsAppService
from llm_service import LLMService
from bot_flow import BotFlowManager
from scoring import ScoringEngine
from google_services import GoogleSheetsService, GoogleCalendarService
from email_service import EmailService
from scheduler import ScheduledTasks
from auth import decode_access_token
from auth_routes import router as auth_router, get_current_user, require_admin
from assignment import AssignmentEngine

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Inmobiliaria WhatsApp Bot")
api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================================
# WEBSOCKET NOTIFICATION MANAGER
# ==============================================
class NotificationManager:
    """Gestiona conexiones WebSocket y notificaciones en tiempo real"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_emails: Dict[str, str] = {}  # websocket_id -> email
    
    async def connect(self, websocket: WebSocket, user_email: str):
        """Conecta usuario al sistema de notificaciones"""
        await websocket.accept()
        ws_id = str(id(websocket))
        self.active_connections[ws_id] = websocket
        self.user_emails[ws_id] = user_email
        logger.info(f"WebSocket conectado: {user_email}")
    
    def disconnect(self, websocket: WebSocket):
        """Desconecta usuario"""
        ws_id = str(id(websocket))
        if ws_id in self.active_connections:
            del self.active_connections[ws_id]
            email = self.user_emails.pop(ws_id, "unknown")
            logger.info(f"WebSocket desconectado: {email}")
    
    async def send_to_user(self, email: str, notification: dict):
        """Envía notificación a usuario específico"""
        for ws_id, websocket in list(self.active_connections.items()):
            if self.user_emails.get(ws_id) == email:
                try:
                    await websocket.send_json(notification)
                except Exception as e:
                    logger.error(f"Error enviando notificación: {e}")
    
    async def send_to_admins(self, notification: dict):
        """Envía notificación a todos los admins conectados"""
        admin_emails = []
        async for agent in db.agents.find({"role": "admin"}, {"email": 1}):
            admin_emails.append(agent["email"])
        
        for ws_id, websocket in list(self.active_connections.items()):
            if self.user_emails.get(ws_id) in admin_emails:
                try:
                    await websocket.send_json(notification)
                except Exception as e:
                    logger.error(f"Error enviando a admin: {e}")
    
    async def broadcast(self, notification: dict):
        """Envía notificación a todos los usuarios conectados"""
        for ws_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_json(notification)
            except Exception as e:
                logger.error(f"Error en broadcast: {e}")

notification_manager = NotificationManager()
assignment_engine = None  # Se inicializa en startup

wa_service = WhatsAppService(db)
llm_service = LLMService()
email_service = EmailService(db)
bot_flow = BotFlowManager(wa_service, llm_service, email_service)
sheets_service = GoogleSheetsService()
calendar_service = GoogleCalendarService()
scheduler = ScheduledTasks(db, email_service)


@api_router.get("/")
async def root():
    return {"message": "Inmobiliaria WhatsApp Bot API"}


@api_router.get("/webhook")
async def verify_webhook(
    request: Request,
):
    """Verificación de webhook de WhatsApp"""
    params = dict(request.query_params)
    hub_mode = params.get("hub.mode")
    hub_challenge = params.get("hub.challenge")
    hub_verify_token = params.get("hub.verify_token")
    
    verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN")
    
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("Webhook verificado exitosamente")
        return Response(content=hub_challenge, status_code=200)
    
    logger.warning("Verificación de webhook fallida")
    return Response(content="Unauthorized", status_code=403)


@api_router.post("/webhook")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None)
):
    """Recibe mensajes entrantes de WhatsApp"""
    try:
        body = await request.body()
        
        if x_hub_signature_256:
            signature = x_hub_signature_256.replace("sha256=", "")
            if not wa_service.verify_signature(body, signature):
                logger.error("Firma de webhook inválida")
                return Response(status_code=401)
        
        data = json.loads(body)
        logger.info(f"Webhook recibido: {json.dumps(data, indent=2)}")
        
        if data.get("object") == "whatsapp_business_account":
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [])
            
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message in messages:
                    await handle_incoming_message(message)
        
        return Response(status_code=200)
    
    except Exception as e:
        logger.error(f"Error procesando webhook: {str(e)}")
        return Response(status_code=500)


async def handle_incoming_message(message: dict):
    """Procesa mensaje entrante"""
    try:
        sender = message.get("from")
        message_type = message.get("type")
        
        await wa_service.record_customer_message(sender)
        
        lead = await db.leads.find_one({"phone": sender}, {"_id": 0})
        
        if not lead:
            lead = Lead(phone=sender)
            lead_dict = lead.model_dump()
            lead_dict["last_message_at"] = lead.last_message_at.isoformat()
            lead_dict["created_at"] = lead.created_at.isoformat()
            await db.leads.insert_one(lead_dict)
        else:
            if isinstance(lead.get("created_at"), str):
                lead["created_at"] = datetime.fromisoformat(lead["created_at"])
            if isinstance(lead.get("last_message_at"), str):
                lead["last_message_at"] = datetime.fromisoformat(lead["last_message_at"])
            if lead.get("appointment_datetime") and isinstance(lead["appointment_datetime"], str):
                lead["appointment_datetime"] = datetime.fromisoformat(lead["appointment_datetime"])
            
            lead = Lead(**lead)
        
        message_text = ""
        if message_type == "text":
            message_text = message.get("text", {}).get("body", "")
        elif message_type == "button":
            message_text = message.get("button", {}).get("text", "")
        elif message_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                message_text = interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                message_text = interactive.get("list_reply", {}).get("title", "")
        
        if message_text:
            updated_lead = await bot_flow.process_message(lead, message_text, db)
            
            if updated_lead.status == LeadStatus.HOT:
                await sheets_service.sync_lead_to_sheet(updated_lead.model_dump())
            
            if updated_lead.appointment_datetime:
                await calendar_service.create_appointment(
                    updated_lead.name or f"Lead {updated_lead.phone}",
                    updated_lead.phone,
                    updated_lead.appointment_datetime
                )
    
    except Exception as e:
        logger.error(f"Error manejando mensaje entrante: {str(e)}")


@api_router.get("/leads", response_model=List[Lead])
async def get_leads(
    status: Optional[str] = None,
    limit: int = 100
):
    """Obtiene lista de leads"""
    query = {}
    if status:
        query["status"] = status
    
    leads = await db.leads.find(query, {
        "_id": 0,
        "conversation_history": 0
    }).sort("created_at", -1).limit(limit).to_list(limit)
    
    for lead in leads:
        if isinstance(lead.get("created_at"), str):
            lead["created_at"] = datetime.fromisoformat(lead["created_at"])
        if isinstance(lead.get("last_message_at"), str):
            lead["last_message_at"] = datetime.fromisoformat(lead["last_message_at"])
        if lead.get("appointment_datetime") and isinstance(lead["appointment_datetime"], str):
            lead["appointment_datetime"] = datetime.fromisoformat(lead["appointment_datetime"])
    
    return leads


@api_router.get("/leads/{phone}")
async def get_lead(phone: str):
    """Obtiene un lead específico"""
    lead = await db.leads.find_one({"phone": phone}, {"_id": 0})
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    if isinstance(lead.get("created_at"), str):
        lead["created_at"] = datetime.fromisoformat(lead["created_at"])
    if isinstance(lead.get("last_message_at"), str):
        lead["last_message_at"] = datetime.fromisoformat(lead["last_message_at"])
    if lead.get("appointment_datetime") and isinstance(lead["appointment_datetime"], str):
        lead["appointment_datetime"] = datetime.fromisoformat(lead["appointment_datetime"])
    
    return lead


@api_router.put("/leads/{phone}")
async def update_lead(phone: str, lead_update: LeadUpdate):
    """Actualiza un lead"""
    update_data = {k: v for k, v in lead_update.model_dump(exclude_unset=True).items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    
    result = await db.leads.update_one(
        {"phone": phone},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return {"message": "Lead actualizado"}


@api_router.delete("/leads/{phone}")
async def delete_lead(phone: str):
    """Elimina un lead permanentemente"""
    result = await db.leads.delete_one({"phone": phone})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return {"message": "Lead eliminado exitosamente"}


@api_router.get("/leads/stats/summary")
async def get_stats():
    """Obtiene estadísticas de leads"""
    total = await db.leads.count_documents({})
    hot = await db.leads.count_documents({"status": "hot"})
    warm = await db.leads.count_documents({"status": "warm"})
    cold = await db.leads.count_documents({"status": "cold"})
    
    with_appointment = await db.leads.count_documents({"appointment_datetime": {"$exists": True, "$ne": None}})
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_leads = await db.leads.count_documents({"created_at": {"$gte": today.isoformat()}})
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_leads = await db.leads.count_documents({"created_at": {"$gte": week_ago.isoformat()}})
    
    avg_score_pipeline = [
        {"$group": {"_id": None, "avg_score": {"$avg": "$score"}}}
    ]
    avg_result = await db.leads.aggregate(avg_score_pipeline).to_list(1)
    avg_score = avg_result[0]["avg_score"] if avg_result else 0
    
    return {
        "total": total,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "with_appointment": with_appointment,
        "today": today_leads,
        "this_week": week_leads,
        "avg_score": round(avg_score, 2),
        "conversion_rate": round((hot / total * 100) if total > 0 else 0, 2)
    }


@api_router.get("/config")
async def get_config():
    """Obtiene configuración del bot"""
    config = await db.bot_config.find_one({}, {"_id": 0})
    
    if not config:
        config = BotConfig().model_dump()
        config["updated_at"] = config["updated_at"].isoformat()
        await db.bot_config.insert_one(config)
    
    return config


@api_router.put("/config")
async def update_config(config: BotConfig):
    """Actualiza configuración del bot"""
    config_dict = config.model_dump()
    config_dict["updated_at"] = datetime.utcnow().isoformat()
    
    await db.bot_config.update_one(
        {},
        {"$set": config_dict},
        upsert=True
    )
    
    return {"message": "Configuración actualizada"}


@api_router.get("/agents", response_model=List[Agent])
async def get_agents():
    """Obtiene lista de agentes"""
    agents = await db.agents.find({}, {"_id": 0}).to_list(100)
    
    for agent in agents:
        if isinstance(agent.get("created_at"), str):
            agent["created_at"] = datetime.fromisoformat(agent["created_at"])
    
    return agents


@api_router.post("/agents", response_model=Agent)
async def create_agent(agent: Agent):
    """Crea un nuevo agente"""
    agent_dict = agent.model_dump()
    agent_dict["created_at"] = agent.created_at.isoformat()
    
    await db.agents.insert_one(agent_dict)
    return agent


@api_router.post("/test-email")
async def test_email():
    """Envía email de prueba para verificar configuración"""
    try:
        success = await email_service.test_email()
        if success:
            return {"success": True, "message": "Email de prueba enviado exitosamente"}
        else:
            raise HTTPException(status_code=500, detail="Error enviando email de prueba")
    except Exception as e:
        logger.error(f"Error en test de email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/email-stats")
async def get_email_stats():
    """Obtiene estadísticas de emails enviados"""
    try:
        total = await db.email_logs.count_documents({})
        successful = await db.email_logs.count_documents({"success": True})
        failed = await db.email_logs.count_documents({"success": False})
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = await db.email_logs.count_documents({
            "sent_at": {"$gte": today.isoformat()}
        })
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_count = await db.email_logs.count_documents({
            "sent_at": {"$gte": week_ago.isoformat()}
        })
        
        by_type_pipeline = [
            {"$group": {"_id": "$email_type", "count": {"$sum": 1}}}
        ]
        by_type = await db.email_logs.aggregate(by_type_pipeline).to_list(10)
        by_type_dict = {item["_id"]: item["count"] for item in by_type}
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round((successful / total * 100) if total > 0 else 0, 2),
            "today": today_count,
            "this_week": week_count,
            "by_type": by_type_dict
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Inicia tareas programadas al arrancar el servidor"""
    logger.info("Iniciando tareas programadas...")
    await scheduler.start()


@app.on_event("shutdown")
async def shutdown_db_client():
    """Detiene tareas y cierra conexiones al apagar el servidor"""
    logger.info("Deteniendo tareas programadas...")
    await scheduler.stop()
    client.close()
