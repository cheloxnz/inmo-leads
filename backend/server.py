from fastapi import FastAPI, APIRouter, Request, Response, Header, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import io
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncio

from models import (
    Lead, LeadCreate, LeadUpdate, Agent, BotConfig,
    LeadStatus, FlowStage, User
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
from audio_service import AudioTranscriptionService
from payment_service import PaymentService, SUBSCRIPTION_PLANS
from scheduled_messages import ScheduledMessagesService, BroadcastService
from resend_service import send_welcome_email

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
scheduler = ScheduledTasks(db, email_service, wa_service)
audio_service = AudioTranscriptionService()
payment_service = PaymentService(db)


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


@api_router.get("/debug-token")
async def debug_token():
    """Debug: verificar token configurado"""
    from whatsapp_service import WhatsAppService
    # Crear instancia temporal para ver el token que usaría
    ws = WhatsAppService(db)
    return {
        "token_start": ws.access_token[:50] + "..." if ws.access_token else "NO_TOKEN",
        "token_length": len(ws.access_token) if ws.access_token else 0,
        "token_from": "hardcoded" if "EAAMSvSefVHQBQv05eAfa5NrQ8" in (ws.access_token or "") else "env_or_old"
    }


@api_router.post("/webhook")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None)
):
    """Recibe mensajes entrantes de WhatsApp"""
    try:
        body = await request.body()
        logger.info(f"Webhook POST recibido - Body length: {len(body)}")
        
        # Temporalmente deshabilitamos verificación de firma para debug
        # if x_hub_signature_256:
        #     signature = x_hub_signature_256.replace("sha256=", "")
        #     if not wa_service.verify_signature(body, signature):
        #         logger.error("Firma de webhook inválida")
        #         return Response(status_code=401)
        
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
        previous_status = lead.get("status") if lead else None
        
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
        button_id = ""
        if message_type == "text":
            message_text = message.get("text", {}).get("body", "")
        elif message_type == "button":
            message_text = message.get("button", {}).get("text", "")
        elif message_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                button_id = interactive.get("button_reply", {}).get("id", "")
                message_text = button_id  # Usar el ID del botón como mensaje
                logger.info(f"Button pressed: id={button_id}")
            elif interactive.get("type") == "list_reply":
                message_text = interactive.get("list_reply", {}).get("id", "")
        elif message_type == "audio":
            # Transcribir mensaje de voz
            audio_info = message.get("audio", {})
            audio_id = audio_info.get("id")
            if audio_id:
                logger.info(f"🎤 Audio recibido de {sender}, transcribiendo...")
                transcribed_text = await audio_service.transcribe_whatsapp_audio(
                    audio_id, 
                    wa_service.access_token
                )
                if transcribed_text:
                    message_text = transcribed_text
                    logger.info(f"✅ Audio transcrito: '{transcribed_text[:100]}...'")
                    # Notificar que se recibió audio
                    wa_service.send_text_message(sender, f"🎤 _Audio recibido: \"{transcribed_text[:100]}{'...' if len(transcribed_text) > 100 else ''}\"_")
                else:
                    wa_service.send_text_message(sender, "No pude escuchar el audio. ¿Podés escribirme tu consulta?")
                    return
        
        if message_text:
            updated_lead = await bot_flow.process_message(lead, message_text, db)
            
            # Asignación automática cuando lead se vuelve HOT
            if updated_lead.status == LeadStatus.HOT and previous_status != "hot":
                if assignment_engine and not updated_lead.assigned_agent:
                    assigned_email = await assignment_engine.assign_lead_to_agent(
                        updated_lead.phone,
                        updated_lead.model_dump()
                    )
                    
                    if assigned_email:
                        # Notificar al asesor asignado
                        await notification_manager.send_to_user(assigned_email, {
                            "type": "new_lead_assigned",
                            "title": "🔥 Nuevo Lead Asignado",
                            "message": f"Lead caliente asignado: {updated_lead.name or 'Sin nombre'} ({updated_lead.zone or 'Sin zona'})",
                            "lead_phone": updated_lead.phone,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        # Si presupuesto alto, notificar a admins
                        budget = updated_lead.budget_text or ""
                        if "500" in budget or "1000" in budget or "millón" in budget.lower():
                            await notification_manager.send_to_admins({
                                "type": "high_value_lead",
                                "title": "🎯 Lead de Alto Valor",
                                "message": f"Lead con presupuesto >$500k detectado: {updated_lead.name}",
                                "lead_phone": updated_lead.phone,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                
                await sheets_service.sync_lead_to_sheet(updated_lead.model_dump())
            
            # Notificar cuando cliente responde
            if updated_lead.assigned_agent and previous_status:
                await notification_manager.send_to_user(updated_lead.assigned_agent, {
                    "type": "customer_replied",
                    "title": "💬 Cliente Respondió",
                    "message": f"{updated_lead.name or 'Cliente'} respondió en WhatsApp",
                    "lead_phone": updated_lead.phone,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # 🚨 Notificar URGENCIA a todos los admins y asesor asignado
            if updated_lead.is_urgent:
                logger.info(f"🚨 Enviando notificación de URGENCIA para lead {updated_lead.phone}")
                urgent_notification = {
                    "type": "urgent_lead",
                    "title": "🚨 URGENTE - Atención Inmediata",
                    "message": f"Lead URGENTE: {updated_lead.name or 'Sin nombre'} - {updated_lead.phone}",
                    "lead_phone": updated_lead.phone,
                    "timestamp": datetime.utcnow().isoformat()
                }
                # Broadcast a todos los conectados (para asegurar que llegue)
                await notification_manager.broadcast(urgent_notification)
                logger.info(f"✅ Notificación de urgencia enviada por broadcast")
            
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


# NOTE: This route MUST be BEFORE /leads/{phone} to avoid path parameter matching
@api_router.get("/leads/assigned-to-me")
async def get_my_leads(
    current_user: User = Depends(get_current_user),
    status: Optional[str] = None,
    limit: int = 100
):
    """Obtiene leads asignados al asesor actual"""
    query = {"assigned_agent": current_user.email}
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


# Tags endpoints
@api_router.post("/leads/{phone}/tags")
async def add_tag(phone: str, tag_data: dict):
    """Agrega un tag a un lead"""
    tag = tag_data.get("tag", "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag vacío")
    
    result = await db.leads.update_one(
        {"phone": phone},
        {"$addToSet": {"tags": tag}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return {"message": "Tag agregado", "tag": tag}


@api_router.delete("/leads/{phone}/tags/{tag}")
async def remove_tag(phone: str, tag: str):
    """Elimina un tag de un lead"""
    result = await db.leads.update_one(
        {"phone": phone},
        {"$pull": {"tags": tag}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Lead o tag no encontrado")
    
    return {"message": "Tag eliminado"}


@api_router.get("/tags")
async def get_all_tags():
    """Obtiene todos los tags únicos usados"""
    pipeline = [
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    tags = await db.leads.aggregate(pipeline).to_list(100)
    return [{"tag": t["_id"], "count": t["count"]} for t in tags]


# Métricas para gráficos
@api_router.get("/metrics/leads-by-day")
async def get_leads_by_day(days: int = 30):
    """Obtiene cantidad de leads por día"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {"$match": {"created_at": {"$gte": start_date.isoformat()}}},
        {"$addFields": {
            "date": {"$substr": ["$created_at", 0, 10]}
        }},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    
    result = await db.leads.aggregate(pipeline).to_list(100)
    return [{"date": r["_id"], "count": r["count"]} for r in result]


@api_router.get("/metrics/leads-by-status")
async def get_leads_by_status():
    """Obtiene distribución de leads por estado"""
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    result = await db.leads.aggregate(pipeline).to_list(10)
    return [{"status": r["_id"] or "unknown", "count": r["count"]} for r in result]


@api_router.get("/metrics/leads-by-intent")
async def get_leads_by_intent():
    """Obtiene distribución de leads por intención"""
    pipeline = [
        {"$group": {"_id": "$intent", "count": {"$sum": 1}}}
    ]
    result = await db.leads.aggregate(pipeline).to_list(10)
    return [{"intent": r["_id"] or "sin_definir", "count": r["count"]} for r in result]


@api_router.get("/metrics/conversion-funnel")
async def get_conversion_funnel():
    """Obtiene métricas del funnel de conversión"""
    total = await db.leads.count_documents({})
    qualified = await db.leads.count_documents({"score": {"$gte": 30}})
    with_appointment = await db.leads.count_documents({"appointment_datetime": {"$exists": True, "$ne": None}})
    hot = await db.leads.count_documents({"status": "hot"})
    
    return {
        "total_leads": total,
        "qualified": qualified,
        "with_appointment": with_appointment,
        "hot_leads": hot,
        "qualification_rate": round((qualified / total * 100) if total > 0 else 0, 1),
        "appointment_rate": round((with_appointment / total * 100) if total > 0 else 0, 1),
        "conversion_rate": round((hot / total * 100) if total > 0 else 0, 1)
    }


@api_router.get("/metrics/messages")
async def get_messages_metrics(days: int = 30):
    """Obtiene métricas de mensajes procesados"""
    start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    # Contar mensajes desde conversation_history de cada lead
    pipeline = [
        {"$unwind": "$conversation_history"},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "from_customer": {
                "$sum": {"$cond": [{"$eq": ["$conversation_history.from", "customer"]}, 1, 0]}
            },
            "from_bot": {
                "$sum": {"$cond": [{"$eq": ["$conversation_history.from", "bot"]}, 1, 0]}
            }
        }}
    ]
    
    result = await db.leads.aggregate(pipeline).to_list(1)
    
    # Mensajes por día (últimos N días)
    pipeline_by_day = [
        {"$unwind": "$conversation_history"},
        {"$match": {"conversation_history.timestamp": {"$gte": start_date}}},
        {"$addFields": {"date": {"$substr": ["$conversation_history.timestamp", 0, 10]}}},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    by_day = await db.leads.aggregate(pipeline_by_day).to_list(100)
    
    # Total de leads
    total_leads = await db.leads.count_documents({})
    
    stats = result[0] if result else {"total": 0, "from_customer": 0, "from_bot": 0}
    recent_count = sum(d["count"] for d in by_day)
    
    return {
        "total_messages": stats.get("total", 0),
        "incoming_messages": stats.get("from_customer", 0),
        "outgoing_messages": stats.get("from_bot", 0),
        "messages_last_period": recent_count,
        "messages_by_day": [{"date": r["_id"], "count": r["count"]} for r in by_day],
        "avg_per_day": round(recent_count / days, 1) if days > 0 else 0,
        "total_leads": total_leads,
        "avg_messages_per_lead": round(stats.get("total", 0) / total_leads, 1) if total_leads > 0 else 0
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


# ==============================================
# MÉTRICAS POR ASESOR
# ==============================================

@api_router.get("/metrics/agent/{email}")
async def get_agent_metrics(email: str, current_user: User = Depends(get_current_user)):
    """Obtiene métricas de un asesor específico"""
    # Asesores solo pueden ver sus propias métricas
    if current_user.role != "admin" and current_user.email != email:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    if not assignment_engine:
        raise HTTPException(status_code=500, detail="Motor de asignación no inicializado")
    
    metrics = await assignment_engine.get_agent_metrics(email)
    
    # Agregar datos del asesor
    agent = await db.agents.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if agent:
        metrics["agent_name"] = agent.get("name")
        metrics["specialties"] = agent.get("specialties", [])
        metrics["zones"] = agent.get("zones", [])
        metrics["max_concurrent_leads"] = agent.get("max_concurrent_leads", 15)
    
    return metrics


@api_router.get("/metrics/all-agents")
async def get_all_agents_metrics(current_user: User = Depends(require_admin)):
    """Obtiene métricas de todos los asesores (solo admin)"""
    agents = await db.agents.find({"role": {"$ne": "admin"}}, {"_id": 0, "password_hash": 0}).to_list(100)
    
    results = []
    for agent in agents:
        metrics = await assignment_engine.get_agent_metrics(agent["email"])
        metrics["agent_name"] = agent.get("name")
        metrics["email"] = agent.get("email")
        metrics["specialties"] = agent.get("specialties", [])
        metrics["zones"] = agent.get("zones", [])
        metrics["active"] = agent.get("active", True)
        metrics["max_concurrent_leads"] = agent.get("max_concurrent_leads", 15)
        
        # Verificar si está sobrecargado
        if metrics.get("active_leads", 0) >= metrics["max_concurrent_leads"]:
            metrics["is_overloaded"] = True
        else:
            metrics["is_overloaded"] = False
        
        results.append(metrics)
    
    return results


@api_router.get("/metrics/daily-goals")
async def get_daily_goals(current_user: User = Depends(get_current_user)):
    """Obtiene progreso de metas diarias"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Leads de hoy por status
    hot_today = await db.leads.count_documents({
        "created_at": {"$gte": today.isoformat()},
        "status": "hot"
    })
    
    total_today = await db.leads.count_documents({
        "created_at": {"$gte": today.isoformat()}
    })
    
    appointments_today = await db.leads.count_documents({
        "appointment_datetime": {
            "$gte": today.isoformat(),
            "$lt": (today + timedelta(days=1)).isoformat()
        }
    })
    
    return {
        "hot_leads_today": hot_today,
        "total_leads_today": total_today,
        "appointments_today": appointments_today,
        "hot_lead_goal": 10,  # Meta configurable
        "goal_reached": hot_today >= 10
    }


@api_router.get("/notifications/upcoming-appointments")
async def get_upcoming_appointments(current_user: User = Depends(get_current_user)):
    """Obtiene citas próximas (1 hora)"""
    now = datetime.utcnow()
    one_hour_later = now + timedelta(hours=1)
    
    query = {
        "appointment_datetime": {
            "$gte": now.isoformat(),
            "$lte": one_hour_later.isoformat()
        },
        "appointment_reminder_sent": False
    }
    
    # Si es asesor, filtrar por sus leads
    if current_user.role != "admin":
        query["assigned_agent"] = current_user.email
    
    appointments = await db.leads.find(query, {"_id": 0}).to_list(20)
    return appointments


@api_router.get("/notifications/inactive-leads")
async def get_inactive_leads(current_user: User = Depends(get_current_user)):
    """Obtiene leads tibios sin actividad en 3+ días"""
    three_days_ago = datetime.utcnow() - timedelta(days=3)
    
    query = {
        "status": "warm",
        "last_message_at": {"$lte": three_days_ago.isoformat()}
    }
    
    # Si es asesor, filtrar por sus leads
    if current_user.role != "admin":
        query["assigned_agent"] = current_user.email
    
    inactive = await db.leads.find(query, {"_id": 0}).to_list(20)
    return inactive


# ==============================================
# PAYMENT ENDPOINTS (Stripe)
# ==============================================
class CheckoutRequest(BaseModel):
    plan_id: str
    customer_email: str
    customer_name: str
    origin_url: str


@api_router.get("/plans")
async def get_plans():
    """Obtiene los planes de suscripción disponibles"""
    return SUBSCRIPTION_PLANS


@api_router.post("/checkout")
async def create_checkout(request: CheckoutRequest):
    """Crea una sesión de checkout de Stripe"""
    try:
        result = await payment_service.create_checkout_session(
            plan_id=request.plan_id,
            customer_email=request.customer_email,
            customer_name=request.customer_name,
            origin_url=request.origin_url
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error en checkout: {e}")
        raise HTTPException(status_code=500, detail="Error creando sesión de pago")


@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str):
    """Obtiene el estado de una sesión de checkout"""
    try:
        status = await payment_service.get_checkout_status(session_id)
        
        # Si el pago fue exitoso, enviar email de bienvenida
        if status.get("payment_status") == "paid":
            transaction = await db.payment_transactions.find_one(
                {"session_id": session_id},
                {"_id": 0}
            )
            
            # Solo enviar si no se envió antes
            if transaction and not transaction.get("welcome_email_sent"):
                email_result = await send_welcome_email(
                    customer_email=transaction.get("customer_email"),
                    customer_name=transaction.get("customer_name"),
                    plan_name=transaction.get("plan_name"),
                    amount=transaction.get("amount")
                )
                
                # Marcar como enviado
                if email_result.get("status") == "success":
                    await db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {"welcome_email_sent": True}}
                    )
                    logger.info(f"Email de bienvenida enviado a {transaction.get('customer_email')}")
        
        return status
    except Exception as e:
        logger.error(f"Error obteniendo status: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estado del pago")


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Webhook para eventos de Stripe"""
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature", "")
        result = await payment_service.handle_webhook(body, signature)
        
        # Enviar email de bienvenida si el pago fue exitoso
        if result.get("payment_status") == "paid":
            # Obtener datos del cliente desde la transacción
            transaction = await db.payment_transactions.find_one(
                {"session_id": result.get("session_id")},
                {"_id": 0}
            )
            
            if transaction:
                await send_welcome_email(
                    customer_email=transaction.get("customer_email"),
                    customer_name=transaction.get("customer_name"),
                    plan_name=transaction.get("plan_name"),
                    amount=transaction.get("amount")
                )
                logger.info(f"Email de bienvenida enviado a {transaction.get('customer_email')}")
        
        return result
    except Exception as e:
        logger.error(f"Error en webhook Stripe: {e}")
        return {"status": "error", "message": str(e)}


@api_router.get("/transactions")
async def get_transactions(current_user: User = Depends(require_admin)):
    """Obtiene todas las transacciones (solo admin)"""
    return await payment_service.get_all_transactions()


# ==============================================
# BROADCAST & MENSAJES MASIVOS
# ==============================================
class BroadcastRequest(BaseModel):
    message: str
    filters: Optional[Dict] = None
    scheduled_at: Optional[str] = None

broadcast_service = None

@api_router.post("/broadcast")
async def send_broadcast(request: BroadcastRequest, current_user: User = Depends(require_admin)):
    """Envía mensaje broadcast a múltiples leads"""
    global broadcast_service
    if not broadcast_service:
        broadcast_service = BroadcastService(wa_service, db)
    
    scheduled = None
    if request.scheduled_at:
        scheduled = datetime.fromisoformat(request.scheduled_at)
    
    result = await broadcast_service.send_broadcast(
        message=request.message,
        filters=request.filters,
        scheduled_at=scheduled
    )
    
    # Registrar en auditoría
    await log_audit_event(
        action="broadcast_sent",
        user_email=current_user.email,
        details={"recipients": result.get("total_recipients"), "filters": request.filters}
    )
    
    return result

@api_router.get("/broadcast/history")
async def get_broadcast_history(current_user: User = Depends(require_admin)):
    """Obtiene historial de broadcasts"""
    global broadcast_service
    if not broadcast_service:
        broadcast_service = BroadcastService(wa_service, db)
    return await broadcast_service.get_broadcast_history()


# ==============================================
# ACCIONES MASIVAS
# ==============================================
class BulkActionRequest(BaseModel):
    lead_phones: List[str]
    action: str  # "tag", "assign", "status", "delete"
    value: Optional[str] = None

@api_router.post("/leads/bulk-action")
async def bulk_action(request: BulkActionRequest, current_user: User = Depends(require_admin)):
    """Ejecuta acción masiva sobre múltiples leads"""
    updated_count = 0
    
    for phone in request.lead_phones:
        try:
            if request.action == "tag" and request.value:
                await db.leads.update_one(
                    {"phone": phone},
                    {"$addToSet": {"tags": request.value}}
                )
            elif request.action == "assign" and request.value:
                await db.leads.update_one(
                    {"phone": phone},
                    {"$set": {"assigned_to": request.value}}
                )
            elif request.action == "status" and request.value:
                await db.leads.update_one(
                    {"phone": phone},
                    {"$set": {"status": request.value}}
                )
            elif request.action == "delete":
                await db.leads.delete_one({"phone": phone})
            
            updated_count += 1
        except Exception as e:
            logger.error(f"Error in bulk action for {phone}: {e}")
    
    # Registrar en auditoría
    await log_audit_event(
        action=f"bulk_{request.action}",
        user_email=current_user.email,
        details={"count": updated_count, "value": request.value}
    )
    
    return {"updated_count": updated_count, "total": len(request.lead_phones)}


# ==============================================
# HISTORIAL DE AUDITORÍA
# ==============================================
async def log_audit_event(action: str, user_email: str, details: dict = None, lead_phone: str = None):
    """Registra evento de auditoría"""
    await db.audit_log.insert_one({
        "action": action,
        "user_email": user_email,
        "lead_phone": lead_phone,
        "details": details,
        "timestamp": datetime.utcnow(),
        "ip_address": None  # Se puede agregar desde el request
    })

@api_router.get("/audit-log")
async def get_audit_log(
    limit: int = 50,
    action: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """Obtiene historial de auditoría"""
    query = {}
    if action:
        query["action"] = action
    
    logs = await db.audit_log.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    
    for log in logs:
        if log.get("timestamp"):
            log["timestamp"] = log["timestamp"].isoformat()
    
    return logs


# ==============================================
# MÉTRICAS NPS
# ==============================================
@api_router.get("/metrics/nps")
async def get_nps_metrics(current_user: User = Depends(require_admin)):
    """Obtiene métricas de NPS"""
    pipeline = [
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "avg_score": {"$avg": "$score"}
        }}
    ]
    
    results = await db.nps_responses.aggregate(pipeline).to_list(10)
    
    total = sum(r["count"] for r in results)
    promoters = next((r["count"] for r in results if r["_id"] == "promoter"), 0)
    detractors = next((r["count"] for r in results if r["_id"] == "detractor"), 0)
    
    nps_score = 0
    if total > 0:
        nps_score = round(((promoters - detractors) / total) * 100)
    
    return {
        "nps_score": nps_score,
        "total_responses": total,
        "promoters": promoters,
        "passives": next((r["count"] for r in results if r["_id"] == "passive"), 0),
        "detractors": detractors,
        "breakdown": results
    }


# ==============================================
# REPORTES PDF
# ==============================================
@api_router.get("/reports/pdf")
async def generate_pdf_report(
    report_type: str = "monthly",
    current_user: User = Depends(require_admin)
):
    """Genera reporte PDF descargable"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        from reportlab.lib import colors
    except ImportError:
        raise HTTPException(status_code=500, detail="ReportLab no instalado")
    
    # Obtener datos para el reporte
    now = datetime.utcnow()
    start_date = now - timedelta(days=30)
    
    # Estadísticas
    total_leads = await db.leads.count_documents({})
    new_leads = await db.leads.count_documents({"created_at": {"$gte": start_date.isoformat()}})
    appointments = await db.leads.count_documents({"appointment_datetime": {"$exists": True}})
    hot_leads = await db.leads.count_documents({"status": "hot"})
    
    # Crear PDF en memoria
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Header
    p.setFont("Helvetica-Bold", 24)
    p.drawString(50, height - 50, "InmoBot - Reporte Mensual")
    
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 75, f"Generado: {now.strftime('%d/%m/%Y %H:%M')}")
    
    # Línea separadora
    p.line(50, height - 90, width - 50, height - 90)
    
    # Métricas principales
    y_pos = height - 130
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y_pos, "Resumen del Período")
    
    y_pos -= 30
    p.setFont("Helvetica", 12)
    metrics = [
        ("Total de Leads", total_leads),
        ("Nuevos Leads (30 días)", new_leads),
        ("Citas Agendadas", appointments),
        ("Leads Calientes", hot_leads),
    ]
    
    for label, value in metrics:
        p.drawString(70, y_pos, f"• {label}: {value}")
        y_pos -= 20
    
    # Pie de página
    p.setFont("Helvetica", 10)
    p.drawString(50, 30, "InmoBot - Sistema de Gestión de Leads Inmobiliarios")
    p.drawString(width - 100, 30, f"Página 1")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    
    # Registrar en auditoría
    await log_audit_event(
        action="report_generated",
        user_email=current_user.email,
        details={"report_type": report_type}
    )
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=inmobot_reporte_{now.strftime('%Y%m%d')}.pdf"}
    )


# ==============================================
# CALCULADORA ROI
# ==============================================
@api_router.get("/calculator/roi")
async def calculate_roi(
    monthly_leads: int = 100,
    conversion_rate: float = 0.05,
    avg_commission: float = 5000,
    plan_cost: float = 129,
    current_user: User = Depends(require_admin)
):
    """Calcula ROI estimado"""
    # Sin InmoBot (estimado)
    manual_response_rate = 0.6  # 60% de leads contactados
    manual_conversion = conversion_rate * 0.7  # 30% menos conversión por respuesta tardía
    
    revenue_without = monthly_leads * manual_response_rate * manual_conversion * avg_commission
    
    # Con InmoBot
    bot_response_rate = 1.0  # 100% respuesta
    bot_conversion = conversion_rate * 1.4  # 40% más conversión por respuesta inmediata
    
    revenue_with = monthly_leads * bot_response_rate * bot_conversion * avg_commission
    
    # Cálculos
    additional_revenue = revenue_with - revenue_without
    roi = ((additional_revenue - plan_cost) / plan_cost) * 100 if plan_cost > 0 else 0
    
    return {
        "monthly_leads": monthly_leads,
        "without_inmobot": {
            "response_rate": f"{manual_response_rate * 100}%",
            "conversion_rate": f"{manual_conversion * 100:.1f}%",
            "estimated_revenue": round(revenue_without, 2),
            "closed_deals": round(monthly_leads * manual_response_rate * manual_conversion, 1)
        },
        "with_inmobot": {
            "response_rate": "100%",
            "conversion_rate": f"{bot_conversion * 100:.1f}%",
            "estimated_revenue": round(revenue_with, 2),
            "closed_deals": round(monthly_leads * bot_response_rate * bot_conversion, 1)
        },
        "comparison": {
            "additional_revenue": round(additional_revenue, 2),
            "plan_cost": plan_cost,
            "net_gain": round(additional_revenue - plan_cost, 2),
            "roi_percentage": round(roi, 1)
        }
    }


# ==============================================
# KANBAN DATA
# ==============================================
@api_router.get("/leads/kanban")
async def get_kanban_data(current_user: User = Depends(get_current_user)):
    """Obtiene leads organizados para vista Kanban"""
    pipeline = [
        {"$group": {
            "_id": "$status",
            "leads": {"$push": {
                "phone": "$phone",
                "name": "$name",
                "zone": "$zone",
                "budget_text": "$budget_text",
                "score": "$score",
                "intent": "$intent",
                "appointment_datetime": "$appointment_datetime",
                "created_at": "$created_at",
                "tags": "$tags"
            }},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    results = await db.leads.aggregate(pipeline).to_list(20)
    
    # Organizar en columnas del Kanban
    kanban_columns = {
        "new": {"title": "Nuevos", "leads": [], "count": 0},
        "contacted": {"title": "Contactados", "leads": [], "count": 0},
        "qualified": {"title": "Calificados", "leads": [], "count": 0},
        "appointment": {"title": "Cita Agendada", "leads": [], "count": 0},
        "hot": {"title": "Calientes", "leads": [], "count": 0},
        "completed": {"title": "Cerrados", "leads": [], "count": 0}
    }
    
    for result in results:
        status = result["_id"] or "new"
        if status in kanban_columns:
            kanban_columns[status]["leads"] = result["leads"][:20]  # Limitar a 20 por columna
            kanban_columns[status]["count"] = result["count"]
    
    return kanban_columns

@api_router.put("/leads/{phone}/status")
async def update_lead_status(
    phone: str,
    new_status: str,
    current_user: User = Depends(get_current_user)
):
    """Actualiza el estado de un lead (para drag & drop del Kanban)"""
    result = await db.leads.update_one(
        {"phone": phone},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow().isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Registrar en auditoría
    await log_audit_event(
        action="status_changed",
        user_email=current_user.email,
        lead_phone=phone,
        details={"new_status": new_status}
    )
    
    return {"success": True, "new_status": new_status}


# ==============================================
# WEBSOCKET ENDPOINT
# ==============================================
@api_router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: Optional[str] = None
):
    """Endpoint WebSocket para notificaciones en tiempo real"""
    try:
        # Verificar token
        if not token:
            await websocket.close(code=4001)
            return
        
        payload = decode_access_token(token)
        if not payload:
            await websocket.close(code=4001)
            return
        
        user_email = payload.get("sub")
        user_role = payload.get("role", "asesor")
        
        await notification_manager.connect(websocket, user_email)
        
        # Enviar confirmación de conexión
        await websocket.send_json({
            "type": "connected",
            "message": "Conectado al sistema de notificaciones",
            "user": user_email,
            "role": user_role
        })
        
        # Mantener conexión abierta
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Ping/pong para mantener conexión viva
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Enviar heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except:
                    break
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
    finally:
        notification_manager.disconnect(websocket)


# ==============================================
# ADMIN: CREAR USUARIO INICIAL
# ==============================================
@api_router.post("/setup/create-admin")
async def create_initial_admin():
    """Crea usuario admin inicial (solo si no existe ninguno)"""
    from auth import get_password_hash
    
    existing_admin = await db.agents.find_one({"role": "admin"})
    if existing_admin:
        raise HTTPException(status_code=400, detail="Ya existe un administrador")
    
    admin = {
        "name": "Administrador",
        "email": "admin@inmobot.com",
        "phone": "+5491100000000",
        "password_hash": get_password_hash("Admin123!"),
        "role": "admin",
        "specialties": [],
        "zones": [],
        "max_concurrent_leads": 999,
        "active": True,
        "created_at": datetime.utcnow().isoformat()
    }
    
    await db.agents.insert_one(admin)
    
    return {
        "message": "Admin creado exitosamente",
        "email": "admin@inmobot.com",
        "password": "Admin123!",
        "note": "¡Cambia la contraseña después del primer login!"
    }


# Incluir routers
app.include_router(api_router)
app.include_router(auth_router, prefix="/api")

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
    global assignment_engine
    logger.info("Iniciando tareas programadas...")
    assignment_engine = AssignmentEngine(db)
    await scheduler.start()


@app.on_event("shutdown")
async def shutdown_db_client():
    """Detiene tareas y cierra conexiones al apagar el servidor"""
    logger.info("Deteniendo tareas programadas...")
    await scheduler.stop()
    client.close()
