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
from whatsapp_service import WhatsAppService, create_wa_service_for_tenant
from llm_service import LLMService, create_llm_for_tenant
from bot_flow import BotFlowManager
from scoring import calculate_score
from google_services import GoogleSheetsService, GoogleCalendarService
from email_service import EmailService
from scheduler import ScheduledTasks
from auth import decode_access_token
from auth_routes import router as auth_router, get_current_user, require_admin, require_superadmin, tenant_filter
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

# Lifespan handler (reemplaza @app.on_event deprecado)
from contextlib import asynccontextmanager  # noqa: E402

# scheduler/assignment_engine se inician dentro del lifespan (defs mas abajo).
@asynccontextmanager
async def lifespan(_app):
    # Startup
    global assignment_engine
    logger.info("Iniciando tareas programadas...")
    assignment_engine = AssignmentEngine(db)
    try:
        await db.tenants.create_index("tenant_id", unique=True)
        await db.agents.create_index("email", unique=True)
        await db.products.create_index([("tenant_id", 1), ("product_id", 1)], unique=True)
        await db.widget_analytics.create_index([("tenant_id", 1), ("event_type", 1), ("created_at", -1)])
        # Coach: indices y TTL
        await db.coach_nudges.create_index([("tenant_id", 1), ("nudge_type", 1), ("dismissed_at", 1)])
        await db.coach_nudges.create_index([("nudge_id", 1)], unique=True)
        await db.coach_nudges.create_index(
            "dismissed_at", expireAfterSeconds=90 * 86400, name="dismissed_at_ttl"
        )
        await db.coach_celebrations.create_index(
            [("tenant_id", 1), ("celebration_type", 1)], unique=True
        )
        await db.coach_celebrations.create_index([("celebration_id", 1)], unique=True)
        await db.coach_celebrations.create_index(
            "seen_at", expireAfterSeconds=30 * 86400, name="seen_at_ttl"
        )

        # Migracion one-shot: legacy ISO strings -> BSON datetime para TTL
        from datetime import datetime as _dt
        for col, field in (("coach_nudges", "dismissed_at"), ("coach_nudges", "created_at")):
            legacy = await db[col].count_documents({field: {"$type": "string"}})
            if legacy:
                cursor = db[col].find({field: {"$type": "string"}}, {"_id": 1, field: 1})
                migrated = 0
                async for doc in cursor:
                    try:
                        parsed = _dt.fromisoformat(str(doc[field]).replace("Z", "+00:00"))
                        await db[col].update_one({"_id": doc["_id"]}, {"$set": {field: parsed}})
                        migrated += 1
                    except Exception:
                        pass
                logger.info(f"Migrated {migrated} legacy {col}.{field} strings -> BSON datetime")
        logger.info("Indices unique creados/verificados")
    except Exception as e:
        logger.warning(f"No se pudieron crear indices unique: {e}")

    await scheduler.start()
    yield
    # Shutdown
    logger.info("Deteniendo tareas programadas...")
    await scheduler.stop()
    client.close()


app = FastAPI(title="Inmobiliaria WhatsApp Bot", lifespan=lifespan)
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

from generic_flow import GenericFlowEngine
from usage_service import UsageService
from catalog_service import CatalogService
generic_flow = GenericFlowEngine(wa_service, llm_service, email_service)
usage_service = UsageService(db)
catalog_service = CatalogService(db)

sheets_service = GoogleSheetsService()
calendar_service = GoogleCalendarService()
audio_service = AudioTranscriptionService()
payment_service = PaymentService(db)
scheduler = ScheduledTasks(db, email_service, wa_service, payment_service=payment_service)


@api_router.get("/")
async def root():
    return {"message": "InmoBot SaaS API"}


@api_router.get("/webhook")
async def verify_webhook(request: Request):
    """Verificación de webhook de WhatsApp (multi-tenant)"""
    params = dict(request.query_params)
    hub_mode = params.get("hub.mode")
    hub_challenge = params.get("hub.challenge")
    hub_verify_token = params.get("hub.verify_token")
    
    # First try default verify token from .env
    default_token = os.getenv("WEBHOOK_VERIFY_TOKEN")
    if hub_mode == "subscribe" and hub_verify_token == default_token:
        logger.info("Webhook verificado (default token)")
        return Response(content=hub_challenge, status_code=200)
    
    # Then try tenant-specific tokens
    if hub_mode == "subscribe" and hub_verify_token:
        tenant = await db.tenants.find_one(
            {"webhook_verify_token": hub_verify_token, "active": True},
            {"_id": 0}
        )
        if tenant:
            logger.info(f"Webhook verificado (tenant: {tenant['tenant_id']})")
            return Response(content=hub_challenge, status_code=200)
    
    logger.warning("Verificación de webhook fallida")
    return Response(content="Unauthorized", status_code=403)


@api_router.get("/debug-token")
async def debug_token():
    """Debug: verificar token configurado"""
    ws = WhatsAppService(db)
    return {
        "token_start": ws.access_token[:50] + "..." if ws.access_token else "NO_TOKEN",
        "token_length": len(ws.access_token) if ws.access_token else 0
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
            
            # Identify tenant by WhatsApp phone_number_id
            phone_number_id = ""
            for change in changes:
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id", "")
                break
            
            # Find tenant for this phone_number_id
            tenant = await db.tenants.find_one(
                {"whatsapp_phone_number_id": phone_number_id, "active": True},
                {"_id": 0}
            ) if phone_number_id else None
            tenant_id = tenant["tenant_id"] if tenant else ""
            
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message in messages:
                    await handle_incoming_message(message, tenant_id, tenant)
        
        return Response(status_code=200)
    
    except Exception as e:
        logger.error(f"Error procesando webhook: {str(e)}")
        return Response(status_code=500)


async def handle_incoming_message(message: dict, tenant_id: str = "", tenant: dict = None):
    """Procesa mensaje entrante (tenant-aware)"""
    try:
        sender = message.get("from")
        message_type = message.get("type")
        
        # Use tenant-specific WhatsApp service if tenant has its own token
        active_wa = wa_service
        if tenant and tenant.get("whatsapp_access_token"):
            active_wa = create_wa_service_for_tenant(db, tenant)
        
        await active_wa.record_customer_message(sender)
        
        lead = await db.leads.find_one({"phone": sender, "tenant_id": tenant_id}, {"_id": 0})
        previous_status = lead.get("status") if lead else None
        
        if not lead:
            lead = Lead(phone=sender, tenant_id=tenant_id)
            lead_dict = lead.model_dump()
            lead_dict["last_message_at"] = lead.last_message_at.isoformat()
            lead_dict["created_at"] = lead.created_at.isoformat()

            # Lead Attribution: si hubo click_whatsapp reciente del widget (ultimos 30 min), atribuir al widget
            try:
                from datetime import timedelta as _td
                cutoff = (datetime.utcnow() - _td(minutes=30)).isoformat()
                recent_click = await db.widget_analytics.find_one(
                    {
                        "tenant_id": tenant_id,
                        "event_type": "click_whatsapp",
                        "created_at": {"$gte": cutoff}
                    },
                    sort=[("created_at", -1)]
                )
                if recent_click:
                    lead.source = "widget"
                    lead.referring_product_id = recent_click.get("product_id")
                    lead.widget_session_id = recent_click.get("session_id")
                    lead_dict["source"] = "widget"
                    lead_dict["referring_product_id"] = recent_click.get("product_id")
                    lead_dict["widget_session_id"] = recent_click.get("session_id")
                    # Emitir lead_generated event al analytics del widget
                    await db.widget_analytics.insert_one({
                        "tenant_id": tenant_id,
                        "event_type": "lead_generated",
                        "product_id": recent_click.get("product_id"),
                        "session_id": recent_click.get("session_id"),
                        "phone": sender,
                        "ip_hash": recent_click.get("ip_hash", ""),
                        "created_at": datetime.utcnow().isoformat(),
                        "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    })
            except Exception as _attr_err:
                logger.warning(f"Lead attribution fallo: {_attr_err}")

            await db.leads.insert_one(lead_dict)
            
            # 🔔 Notificar NUEVO LEAD (solo primer mensaje)
            await notification_manager.send_to_admins({
                "type": "new_lead",
                "title": "📥 Nuevo Lead",
                "message": f"Nueva conversación iniciada desde {sender}{' (vino del catalogo web)' if lead_dict.get('source') == 'widget' else ''}",
                "lead_phone": sender,
                "timestamp": datetime.utcnow().isoformat()
            })
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
            # Determine which flow engine to use based on tenant template
            use_generic = True
            if tenant:
                template_id = tenant.get("template_id", "servicios")
                if template_id == "inmobiliaria":
                    use_generic = False  # Use legacy flow for inmobiliaria

            # Create tenant-specific LLM service (uses tenant key if available)
            tenant_llm = create_llm_for_tenant(tenant)

            # Check AI usage limits before processing
            ai_allowed = await usage_service.increment_ai_messages(tenant_id) if tenant_id else True

            if use_generic:
                # Pass tenant-specific LLM and WA service
                generic_flow.llm = tenant_llm if ai_allowed else None
                await generic_flow.process_message(lead, message_text, db, tenant_id, tenant_wa=active_wa)
                # generic_flow muta lead in-place; usar lead como updated_lead
                updated_lead = lead
            else:
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
            
            # 🔔 Notificar cuando conversación se COMPLETA (cita agendada o calificación finalizada)
            if updated_lead.flow_stage in ["appointment_confirmed", "completed", "tasacion_scheduled"]:
                previous_flow_stage = lead.flow_stage if hasattr(lead, 'flow_stage') else None
                if previous_flow_stage != updated_lead.flow_stage:
                    await notification_manager.send_to_admins({
                        "type": "conversation_completed",
                        "title": "✅ Conversación Completada",
                        "message": f"{updated_lead.name or 'Lead'} - {updated_lead.intent or 'Sin intención'} - Cita/Tasación agendada",
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
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """Obtiene lista de leads (filtrado por tenant)"""
    query = tenant_filter(current_user)
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


# NOTE: These routes MUST be BEFORE /leads/{phone} to avoid path parameter matching
@api_router.get("/leads/kanban")
async def get_kanban_data(current_user: User = Depends(get_current_user)):
    """Obtiene leads organizados para vista Kanban (filtrado por tenant)"""
    match_stage = tenant_filter(current_user)
    pipeline = [
        {"$match": match_stage},
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
        "warm": {"title": "Tibios", "leads": [], "count": 0},
        "cold": {"title": "Fríos", "leads": [], "count": 0},
        "completed": {"title": "Cerrados", "leads": [], "count": 0}
    }
    
    for result in results:
        status = result["_id"] or "new"
        if status in kanban_columns:
            kanban_columns[status]["leads"] = result["leads"][:20]
            kanban_columns[status]["count"] = result["count"]
    
    return kanban_columns


@api_router.get("/leads/assigned-to-me")
async def get_my_leads(
    current_user: User = Depends(get_current_user),
    status: Optional[str] = None,
    limit: int = 100
):
    """Obtiene leads asignados al asesor actual"""
    query = tenant_filter(current_user, {"assigned_agent": current_user.email})
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
async def get_lead(phone: str, current_user: User = Depends(get_current_user)):
    """Obtiene un lead específico (filtrado por tenant)"""
    query = tenant_filter(current_user, {"phone": phone})
    lead = await db.leads.find_one(query, {"_id": 0})
    
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
async def update_lead(phone: str, lead_update: LeadUpdate, current_user: User = Depends(get_current_user)):
    """Actualiza un lead (filtrado por tenant)"""
    update_data = {k: v for k, v in lead_update.model_dump(exclude_unset=True).items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    
    query = tenant_filter(current_user, {"phone": phone})
    result = await db.leads.update_one(query, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return {"message": "Lead actualizado"}


@api_router.delete("/leads/{phone}")
async def delete_lead(phone: str, current_user: User = Depends(get_current_user)):
    """Elimina un lead (filtrado por tenant)"""
    query = tenant_filter(current_user, {"phone": phone})
    result = await db.leads.delete_one(query)
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return {"message": "Lead eliminado exitosamente"}


@api_router.get("/leads/stats/summary")
async def get_stats(current_user: User = Depends(get_current_user)):
    """Obtiene estadísticas de leads (filtrado por tenant)"""
    tf = tenant_filter(current_user)
    total = await db.leads.count_documents(tf)
    hot = await db.leads.count_documents({**tf, "status": "hot"})
    warm = await db.leads.count_documents({**tf, "status": "warm"})
    cold = await db.leads.count_documents({**tf, "status": "cold"})
    
    with_appointment = await db.leads.count_documents({**tf, "appointment_datetime": {"$exists": True, "$ne": None}})
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_leads = await db.leads.count_documents({**tf, "created_at": {"$gte": today.isoformat()}})
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_leads = await db.leads.count_documents({**tf, "created_at": {"$gte": week_ago.isoformat()}})
    
    avg_score_pipeline = [
        {"$match": tf},
        {"$group": {"_id": None, "avg_score": {"$avg": "$score"}}}
    ]
    avg_result = await db.leads.aggregate(avg_score_pipeline).to_list(1)
    avg_score = avg_result[0]["avg_score"] if avg_result and avg_result[0].get("avg_score") is not None else 0
    
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
async def add_tag(phone: str, tag_data: dict, current_user: User = Depends(get_current_user)):
    tag = tag_data.get("tag", "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag vacío")
    query = tenant_filter(current_user, {"phone": phone})
    result = await db.leads.update_one(query, {"$addToSet": {"tags": tag}})
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return {"message": "Tag agregado", "tag": tag}


@api_router.delete("/leads/{phone}/tags/{tag}")
async def remove_tag(phone: str, tag: str, current_user: User = Depends(get_current_user)):
    query = tenant_filter(current_user, {"phone": phone})
    result = await db.leads.update_one(query, {"$pull": {"tags": tag}})
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Lead o tag no encontrado")
    
    return {"message": "Tag eliminado"}


@api_router.get("/tags")
async def get_all_tags(current_user: User = Depends(get_current_user)):
    tf = tenant_filter(current_user)
    pipeline = [
        {"$match": tf},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    tags = await db.leads.aggregate(pipeline).to_list(100)
    return [{"tag": t["_id"], "count": t["count"]} for t in tags]


# ============================================
# Metricas de leads -> routers/metrics.py
# ============================================


@api_router.get("/config")
async def get_config(current_user: User = Depends(get_current_user)):
    """Obtiene configuración del bot (por tenant)"""
    tf = tenant_filter(current_user)
    config = await db.bot_config.find_one(tf, {"_id": 0})
    
    if not config:
        config = BotConfig(tenant_id=current_user.tenant_id).model_dump()
        config["updated_at"] = config["updated_at"].isoformat()
        await db.bot_config.insert_one(config)
    
    return config


@api_router.put("/config")
async def update_config(config: BotConfig, current_user: User = Depends(require_admin)):
    """Actualiza configuración del bot (por tenant)"""
    config_dict = config.model_dump()
    config_dict["tenant_id"] = current_user.tenant_id
    config_dict["updated_at"] = datetime.utcnow().isoformat()
    
    await db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": config_dict},
        upsert=True
    )
    
    return {"message": "Configuración actualizada"}


# ============================================
# WhatsApp Config per Tenant
# ============================================

@api_router.get("/config/whatsapp")
async def get_whatsapp_config(current_user: User = Depends(require_admin)):
    """Admin: Obtiene config de WhatsApp del tenant"""
    tenant = await db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {
        "whatsapp_phone_number_id": tenant.get("whatsapp_phone_number_id", ""),
        "whatsapp_access_token": "***" + tenant.get("whatsapp_access_token", "")[-10:] if tenant.get("whatsapp_access_token") else "",
        "whatsapp_business_account_id": tenant.get("whatsapp_business_account_id", ""),
        "webhook_verify_token": tenant.get("webhook_verify_token", ""),
        "webhook_url": f"{os.getenv('REACT_APP_BACKEND_URL', '')}/api/webhook",
        "configured": bool(tenant.get("whatsapp_access_token") and tenant.get("whatsapp_phone_number_id"))
    }

@api_router.put("/config/whatsapp")
async def update_whatsapp_config(
    config: dict,
    current_user: User = Depends(require_admin)
):
    """Admin: Actualiza config de WhatsApp del tenant"""
    update_fields = {}
    allowed = ["whatsapp_phone_number_id", "whatsapp_access_token", "whatsapp_business_account_id", "webhook_verify_token"]
    for key in allowed:
        if key in config:
            update_fields[key] = config[key]
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    update_fields["updated_at"] = datetime.utcnow().isoformat()
    
    await db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update_fields}
    )
    return {"message": "Configuracion de WhatsApp actualizada"}



# ============================================
# Usage / Limits Endpoints
# ============================================

@api_router.get("/usage")
async def get_usage(current_user: User = Depends(get_current_user)):
    """Obtiene resumen de uso del tenant actual"""
    return await usage_service.get_usage_summary(current_user.tenant_id)


@api_router.get("/config/ai")
async def get_ai_config(current_user: User = Depends(require_admin)):
    """Admin: Obtiene config de IA del tenant"""
    tenant = await db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {
        "has_own_key": bool(tenant.get("openai_api_key")),
        "key_preview": "***" + tenant.get("openai_api_key", "")[-8:] if tenant.get("openai_api_key") else "",
        "max_ai_messages": tenant.get("max_ai_messages", 2000),
        "model": "gpt-4o"
    }


@api_router.put("/config/ai")
async def update_ai_config(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Configura key propia de OpenAI (opcional)"""
    update = {}
    if "openai_api_key" in body:
        update["openai_api_key"] = body["openai_api_key"]
    
    if not update:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    update["updated_at"] = datetime.utcnow().isoformat()
    await db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update}
    )
    return {"message": "Configuracion de IA actualizada"}


@api_router.post("/usage/buy-pack")
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
                "messages": str(pack["messages"])
            }
        )

        # Save transaction
        await db.payment_transactions.insert_one({
            "session_id": session.id,
            "tenant_id": current_user.tenant_id,
            "type": "ai_pack",
            "pack_id": pack_id,
            "pack_name": pack["name"],
            "amount": pack["price"],
            "messages": pack["messages"],
            "currency": "usd",
            "payment_status": "pending",
            "created_at": datetime.utcnow().isoformat()
        })

        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Error comprando pack: {e}")
        raise HTTPException(status_code=500, detail="Error creando sesion de pago")


@api_router.post("/usage/confirm-pack")
async def confirm_pack_purchase(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Confirma compra de pack (llamado despues del redirect de Stripe)"""
    pack_id = body.get("pack_id")
    if not pack_id:
        raise HTTPException(status_code=400, detail="pack_id requerido")

    result = await usage_service.add_extra_messages(current_user.tenant_id, pack_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Update transaction
    await db.payment_transactions.update_one(
        {"tenant_id": current_user.tenant_id, "pack_id": pack_id, "payment_status": "pending"},
        {"$set": {"payment_status": "paid", "paid_at": datetime.utcnow().isoformat()}},
    )

    return result




# ============================================
# Catalog / Products Endpoints -> routers/catalog.py
# ============================================
# Endpoints movidos a routers/catalog.py e incluidos al final del archivo



# ============================================
# Custom Flow Builder (per tenant)
# ============================================

@api_router.get("/flow/config")
async def get_flow_config(current_user: User = Depends(get_current_user)):
    """Obtiene la config del flujo del tenant (custom o template base)"""
    from flow_templates import get_template

    # Get tenant info
    tenant = await db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    template_id = tenant.get("template_id", "servicios") if tenant else "servicios"
    base_template = get_template(template_id)

    # Get custom overrides
    config = await db.bot_config.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})

    return {
        "template_id": template_id,
        "template_name": base_template.get("name", ""),
        "is_customized": bool(config and config.get("custom_flow_steps")),
        "welcome_message": (config or {}).get("custom_welcome_message") or base_template.get("welcome_message", ""),
        "welcome_buttons": (config or {}).get("custom_welcome_buttons") or base_template.get("welcome_buttons", []),
        "flow_steps": (config or {}).get("custom_flow_steps") or base_template.get("flow_steps", []),
        "scoring": (config or {}).get("custom_scoring") or base_template.get("scoring", {}),
        "appointment_message": (config or {}).get("custom_appointment_message") or base_template.get("appointment_message", ""),
        "appointment_buttons": (config or {}).get("custom_appointment_buttons") or base_template.get("appointment_buttons", []),
        "completion_message": (config or {}).get("custom_completion_message") or base_template.get("completion_message", ""),
        "faq": (config or {}).get("custom_faq") or base_template.get("faq", {}),
        "labels": (config or {}).get("custom_labels") or base_template.get("labels", {})
    }


@api_router.put("/flow/config")
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
        "labels": "custom_labels"
    }

    for key, db_key in fields_map.items():
        if key in body:
            update[db_key] = body[key]

    update["updated_at"] = datetime.utcnow().isoformat()

    await db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update},
        upsert=True
    )
    return {"message": "Flujo actualizado"}


@api_router.post("/flow/reset")
async def reset_flow_config(current_user: User = Depends(require_admin)):
    """Admin: Resetea el flujo custom al template base"""
    custom_fields = [
        "custom_flow_steps", "custom_welcome_message", "custom_welcome_buttons",
        "custom_scoring", "custom_appointment_message", "custom_appointment_buttons",
        "custom_completion_message", "custom_faq", "custom_labels"
    ]
    unset = {f: "" for f in custom_fields}
    
    await db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$unset": unset}
    )
    return {"message": "Flujo reseteado al template base"}




@api_router.get("/agents", response_model=List[Agent])
async def get_agents(current_user: User = Depends(get_current_user)):
    """Obtiene lista de agentes (por tenant)"""
    tf = tenant_filter(current_user)
    agents = await db.agents.find(tf, {"_id": 0, "password_hash": 0}).to_list(100)
    
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
        **tenant_filter(current_user),
        "created_at": {"$gte": today.isoformat()},
        "status": "hot"
    })
    
    total_today = await db.leads.count_documents({
        **tenant_filter(current_user),
        "created_at": {"$gte": today.isoformat()}
    })
    
    appointments_today = await db.leads.count_documents({
        **tenant_filter(current_user),
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
        **tenant_filter(current_user),
        "appointment_datetime": {
            "$gte": now.isoformat(),
            "$lte": one_hour_later.isoformat()
        },
        "appointment_reminder_sent": False
    }
    
    if current_user.role not in ("admin", "superadmin"):
        query["assigned_agent"] = current_user.email
    
    appointments = await db.leads.find(query, {"_id": 0}).to_list(20)
    return appointments


@api_router.get("/notifications/inactive-leads")
async def get_inactive_leads(current_user: User = Depends(get_current_user)):
    """Obtiene leads tibios sin actividad en 3+ días"""
    three_days_ago = datetime.utcnow() - timedelta(days=3)
    
    query = {
        **tenant_filter(current_user),
        "status": "warm",
        "last_message_at": {"$lte": three_days_ago.isoformat()}
    }
    
    if current_user.role not in ("admin", "superadmin"):
        query["assigned_agent"] = current_user.email
    
    inactive = await db.leads.find(query, {"_id": 0}).to_list(20)
    return inactive


# ==============================================
# PAYMENT & BILLING ENDPOINTS -> routers/billing.py
# ==============================================
# Endpoints movidos a routers/billing.py e incluidos al final del archivo


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
            tf = tenant_filter(current_user, {"phone": phone})
            if request.action == "tag" and request.value:
                await db.leads.update_one(tf, {"$addToSet": {"tags": request.value}})
            elif request.action == "assign" and request.value:
                await db.leads.update_one(tf, {"$set": {"assigned_to": request.value}})
            elif request.action == "status" and request.value:
                await db.leads.update_one(tf, {"$set": {"status": request.value}})
            elif request.action == "delete":
                await db.leads.delete_one(tf)
            
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
async def log_audit_event(action: str, user_email: str, details: dict = None, lead_phone: str = None, tenant_id: str = ""):
    """Registra evento de auditoría"""
    await db.audit_log.insert_one({
        "tenant_id": tenant_id,
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
    query = tenant_filter(current_user)
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
    tf = tenant_filter(current_user)
    pipeline = [
        {"$match": tf},
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


# ============================================
# App Version / Update Notification
# ============================================

@api_router.get("/app/version")
async def get_app_version():
    """Retorna la versión actual de la app y mensaje de actualización"""
    config = await db.app_config.find_one({"key": "app_version"}, {"_id": 0})
    if not config:
        return {"version": "1.0.0", "update_message": None, "force_refresh": False}
    return {
        "version": config.get("version", "1.0.0"),
        "update_message": config.get("update_message"),
        "force_refresh": config.get("force_refresh", False)
    }

@api_router.post("/app/version")
async def set_app_version(
    body: dict,
    current_user: dict = Depends(require_admin)
):
    """Admin: Notifica una nueva versión disponible a todos los clientes"""
    version = body.get("version", "1.0.0")
    update_message = body.get("update_message", "Hay una nueva version disponible. Presiona F5 para actualizar.")
    force_refresh = body.get("force_refresh", False)

    await db.app_config.update_one(
        {"key": "app_version"},
        {"$set": {
            "key": "app_version",
            "version": version,
            "update_message": update_message,
            "force_refresh": force_refresh
        }},
        upsert=True
    )
    return {"status": "ok", "version": version}

@api_router.delete("/app/version")
async def clear_update_notification(
    current_user: dict = Depends(require_admin)
):
    """Admin: Limpia la notificación de actualización"""
    await db.app_config.update_one(
        {"key": "app_version"},
        {"$set": {"update_message": None, "force_refresh": False}},
        upsert=True
    )
    return {"status": "ok"}


# Incluir routers
from routers.catalog import router as catalog_router
from routers.billing import router as billing_router
from routers.metrics import router as metrics_router
from routers.widget import router as widget_router
from routers.superadmin import router as superadmin_router
from routers.templates import router as templates_router
from routers.uploads import router as uploads_router
from routers.onboarding import router as onboarding_router
from routers.bot_config_ai import router as bot_config_ai_router
from routers.flow_ai import router as flow_ai_router
from routers.coach import router as coach_router
from routers.public_share import router as public_share_router

app.include_router(api_router)
app.include_router(auth_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(widget_router, prefix="/api")
app.include_router(superadmin_router, prefix="/api")
app.include_router(templates_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")
app.include_router(bot_config_ai_router, prefix="/api")
app.include_router(flow_ai_router, prefix="/api")
app.include_router(coach_router, prefix="/api")
app.include_router(public_share_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


