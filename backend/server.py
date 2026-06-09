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
from datetime import datetime, timedelta, timezone
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
load_dotenv(ROOT_DIR / '.env', override=True)

# Initialize structured logging FIRST (so Sentry init logs are JSON too)
from logging_config import setup_logging, RequestLoggingMiddleware
setup_logging()

# Initialize Sentry as early as possible (after env vars loaded, before app)
from sentry_config import init_sentry
init_sentry()

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
        # Referral leads: indices para attribution
        await db.referral_leads.create_index([("lead_id", 1)], unique=True)
        await db.referral_leads.create_index([("ref_tenant_id", 1), ("created_at", -1)])
        # Indice compuesto para el upsert filter en POST /lead (evita full scan)
        await db.referral_leads.create_index(
            [("ref_tenant_id", 1), ("email", 1), ("converted_tenant_id", 1)],
            name="upsert_filter"
        )
        # Comisiones: idempotencia + lookups por referrer / status / expiracion
        await db.commissions.create_index([("commission_id", 1)], unique=True)
        await db.commissions.create_index(
            [("referrer_tenant_id", 1), ("referred_tenant_id", 1)],
            unique=True, name="referral_pair_unique"
        )
        await db.commissions.create_index([("referrer_tenant_id", 1), ("status", 1)])
        await db.commissions.create_index([("status", 1), ("expires_at", 1)])

        # Referral codes (Stripe Promotion Code attribution): unique parcial
        await db.tenants.create_index(
            [("referral_code", 1)],
            unique=True,
            partialFilterExpression={"referral_code": {"$type": "string"}},
            name="tenant_referral_code_unique",
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

    # Pre-warm del cliente OpenAI (init liviano: solo crea AsyncOpenAI, no
    # hace requests). No bloquea ni puede crashear el startup.
    if os.environ.get("EMBEDDINGS_WARMUP", "1") != "0":
        async def _warmup_embeddings():
            try:
                import embeddings_service as _embed
                await _embed._ensure_client()
                logger.info("[startup] cliente embeddings listo")
            except Exception as e:
                logger.warning(f"[startup] embeddings warmup falló: {e}")

        asyncio.create_task(_warmup_embeddings())
    yield
    # Shutdown
    logger.info("Deteniendo tareas programadas...")
    await scheduler.stop()
    client.close()


app = FastAPI(title="Inmobiliaria WhatsApp Bot", lifespan=lifespan)
api_router = APIRouter(prefix="/api")

# basicConfig se reemplaza por setup_logging() (formato JSON estructurado).
# Mantenemos la variable `logger` para compatibilidad con el resto del archivo.
logger = logging.getLogger(__name__)

# Tiempo de arranque para reportar uptime en /api/health
APP_STARTED_AT = datetime.now(tz=timezone.utc)
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")


@api_router.get("/health")
async def healthcheck(detailed: int = 0):
    """Health check endpoint — usado por load balancer / UptimeRobot.

    - **Default**: hace un `ping` a MongoDB y devuelve 200 si todo está OK,
      503 si Mongo no responde. Shape estable: `{status, mongo, timestamp,
      version, uptime_seconds}`.
    - **`?detailed=1`**: agrega `mongo_latency_ms` (latencia del ping). Útil
      para dashboards de observabilidad pero no recomendado para UptimeRobot
      (mantenelo simple).

    > **UptimeRobot tip:** monitorear esta URL cada 1 min con keyword=`ok`
    > funciona perfecto. Si querés algo aún más liviano que NO toque la DB
    > (para reducir carga en Atlas con free tier), usá `/api/health/ping`.
    > NO está rate-limitado — los pings frecuentes son bienvenidos.
    """
    mongo_ok = False
    mongo_latency_ms: float | None = None
    try:
        t0 = datetime.now(tz=timezone.utc)
        await db.command("ping")
        mongo_latency_ms = round(
            (datetime.now(tz=timezone.utc) - t0).total_seconds() * 1000, 2
        )
        mongo_ok = True
    except Exception as e:
        logger.error(
            f"Healthcheck Mongo failed: {e}",
            extra={"event": "healthcheck_mongo_fail"},
        )

    uptime_seconds = int(
        (datetime.now(tz=timezone.utc) - APP_STARTED_AT).total_seconds()
    )
    status = "ok" if mongo_ok else "degraded"
    body = {
        "status": status,
        "mongo": "ok" if mongo_ok else "fail",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "version": APP_VERSION,
        "uptime_seconds": uptime_seconds,
    }
    if detailed:
        body["mongo_latency_ms"] = mongo_latency_ms
    return JSONResponse(
        status_code=200 if mongo_ok else 503,
        content=body,
    )


@api_router.get("/health/ping")
async def health_ping():
    """Health check ultra-liviano — NO toca la base de datos.

    Ideal para monitoreo externo (UptimeRobot, Pingdom, BetterStack) cada
    30-60 segundos sin generar carga en MongoDB Atlas. Devuelve siempre 200
    mientras el proceso de Python esté vivo.

    Si querés validar también la DB, usá `/api/health` en una cadencia más
    relajada (cada 5 min).
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "version": APP_VERSION,
    }


@api_router.get("/sentry-debug")
async def sentry_debug(current_user: User = Depends(require_superadmin)):
    """Endpoint de prueba: dispara una excepción para validar que Sentry captura.
    Solo accesible para superadmin."""
    division_by_zero = 1 / 0  # noqa: F841


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
@api_router.get("/whatsapp/webhook")
async def verify_webhook(request: Request):
    """Verificación de webhook de WhatsApp (multi-tenant).
    Aliasado en /webhook y /whatsapp/webhook para flexibilidad."""
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
@api_router.post("/whatsapp/webhook")
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
        
        # Manejar tipos de mensaje no soportados (imagen, video, sticker, documento)
        if not message_text and message_type in ("image", "video", "sticker", "document", "location", "contacts"):
            type_responses = {
                "image": "Recibí tu imagen, pero por ahora solo puedo procesar texto. ¿Podés contarme qué necesitás?",
                "video": "Recibí tu video, pero por ahora solo puedo procesar texto. ¿En qué te puedo ayudar?",
                "sticker": "¡Gracias por el sticker! 😄 ¿En qué te puedo ayudar?",
                "document": "Recibí tu documento. Para consultas sobre propiedades, escribime y con gusto te ayudo.",
                "location": "Gracias por compartir tu ubicación. ¿Estás buscando propiedades en esa zona?",
                "contacts": "Recibí el contacto. ¿En qué te puedo ayudar hoy?",
            }
            reply = type_responses.get(message_type, "Por ahora solo proceso texto. ¿En qué te puedo ayudar?")
            wa_service.send_text_message(sender, reply)
            return

        if message_text:
            # ── Dispatch Automatik Media (B2B qualification flow) ──────
            if tenant_id == "automatik-media":
                from automatik_bot_flow import AutomatikBotFlow
                ak_flow = AutomatikBotFlow(wa_service=active_wa, db=db)
                lead.conversation_history.append({
                    "role": "user",
                    "content": message_text,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                await ak_flow.process(lead, message_text)
                lead.last_message_at = datetime.utcnow()
                await bot_flow.save_lead(lead, db)
                return {"status": "ok"}
            # ──────────────────────────────────────────────────────────

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



# ============================================
# Leads + Tags -> routers/leads.py (Iter32 refactor)
# ============================================



# ============================================
# Metricas de leads -> routers/metrics.py
# ============================================



# ============================================
# /config/* y /flow/* y /usage/* -> routers/config.py + routers/usage.py
# ============================================





# ============================================
# Catalog / Products Endpoints -> routers/catalog.py
# ============================================
# Endpoints movidos a routers/catalog.py e incluidos al final del archivo







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
    action: str  # "tag", "assign", "status", "delete", "auto_assign"
    value: Optional[str] = None

@api_router.post("/leads/bulk-action")
async def bulk_action(request: BulkActionRequest, current_user: User = Depends(require_admin)):
    """Ejecuta acción masiva sobre múltiples leads"""
    updated_count = 0

    # ── auto_assign: round-robin entre todos los agentes activos ──────────────
    if request.action == "auto_assign":
        agents = await db.users.find(
            {"tenant_id": current_user.tenant_id, "role": {"$in": ["agent", "admin"]}},
            {"email": 1, "name": 1}
        ).to_list(100)
        if not agents:
            raise HTTPException(status_code=400, detail="No hay asesores disponibles en este tenant")
        now_iso = datetime.utcnow().isoformat()
        for i, phone in enumerate(request.lead_phones):
            agent = agents[i % len(agents)]
            tf = tenant_filter(current_user, {"phone": phone})
            try:
                await db.leads.update_one(tf, {"$set": {
                    "assigned_agent": agent["email"],
                    "assigned_agent_name": agent.get("name", agent["email"]),
                    "assigned_at": now_iso,
                }})
                updated_count += 1
            except Exception as e:
                logger.error(f"Error auto_assign for {phone}: {e}")
        await log_audit_event(
            action="bulk_auto_assign",
            user_email=current_user.email,
            details={"count": updated_count, "agents": [a["email"] for a in agents]}
        )
        return {
            "updated_count": updated_count,
            "total": len(request.lead_phones),
            "agents_used": [a.get("name", a["email"]) for a in agents],
        }

    # ── Para "assign" buscamos el nombre del agente una sola vez ─────────────
    agent_name = None
    if request.action == "assign" and request.value:
        agent_doc = await db.users.find_one(
            {"email": request.value, "tenant_id": current_user.tenant_id},
            {"name": 1}
        )
        agent_name = agent_doc.get("name", request.value) if agent_doc else request.value

    for phone in request.lead_phones:
        try:
            tf = tenant_filter(current_user, {"phone": phone})
            if request.action == "tag" and request.value:
                await db.leads.update_one(tf, {"$addToSet": {"tags": request.value}})
            elif request.action == "assign" and request.value:
                await db.leads.update_one(tf, {"$set": {
                    "assigned_agent": request.value,
                    "assigned_agent_name": agent_name,
                    "assigned_at": datetime.utcnow().isoformat(),
                }})
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
        ts = log.get("timestamp")
        if ts and not isinstance(ts, str):
            log["timestamp"] = ts.isoformat()
    
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
from routers.leads import router as leads_router
from routers.config import router as config_router
from routers.usage import router as usage_router
from routers.public_metrics import router as public_metrics_router
from routers.roi import router as roi_router
from routers.branding import router as branding_router
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
from routers.commissions import router as commissions_router
from routers.founder import router as founder_router
from routers.bot_learning import router as bot_learning_router, init_router as init_bot_learning
from routers.calendar import router as calendar_router, init_router as init_calendar
from routers.bootstrap import router as bootstrap_router, init_router as init_bootstrap
from routers.automatik_clients import router as automatik_clients_router

app.include_router(api_router)
app.include_router(auth_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(leads_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(usage_router, prefix="/api")
app.include_router(public_metrics_router, prefix="/api")
app.include_router(roi_router, prefix="/api")
app.include_router(branding_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(widget_router, prefix="/api")
app.include_router(superadmin_router, prefix="/api")
app.include_router(automatik_clients_router, prefix="/api")
app.include_router(templates_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")
app.include_router(bot_config_ai_router, prefix="/api")
app.include_router(flow_ai_router, prefix="/api")
app.include_router(coach_router, prefix="/api")
app.include_router(public_share_router, prefix="/api")
app.include_router(commissions_router, prefix="/api")
app.include_router(founder_router, prefix="/api")
app.include_router(bot_learning_router, prefix="/api")
init_bot_learning(db)
app.include_router(calendar_router, prefix="/api")
init_calendar(db)
app.include_router(bootstrap_router, prefix="/api")
init_bootstrap(db)

# ---------------- Security hardening ----------------
from security import setup_security_middleware, validate_cors_origins

setup_security_middleware(app)

# Request ID + structured access logging (after security so rate-limited
# responses also get a request_id).
app.add_middleware(RequestLoggingMiddleware)

# CORS — restringido a dominios explícitos en producción
_cors_origins = validate_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins if _cors_origins else ["*"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "X-Requested-With",
        "Accept", "Origin", "X-CSRF-Token",
    ],
    expose_headers=[
        "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset",
        "Retry-After", "X-Request-ID",
    ],
)


