import asyncio
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from email_service import EmailService

logger = logging.getLogger(__name__)

class ScheduledTasks:
    """Gestor de tareas programadas para recordatorios y reactivaciones"""
    
    def __init__(self, db: AsyncIOMotorDatabase, email_service: EmailService, wa_service=None, payment_service=None):
        self.db = db
        self.email = email_service
        self.wa = wa_service
        self.payment = payment_service
        self.running = False
    
    async def start(self):
        """Inicia las tareas programadas"""
        self.running = True
        logger.info("Tareas programadas iniciadas")
        
        asyncio.create_task(self.check_appointment_reminders())
        asyncio.create_task(self.check_warm_lead_reactivation())
        asyncio.create_task(self.check_whatsapp_appointment_reminders())
        asyncio.create_task(self.bill_monthly_overage())
        asyncio.create_task(self.run_onboarding_coach())
        asyncio.create_task(self.run_commission_expiry())
        asyncio.create_task(self.send_trial_ending_emails())
        asyncio.create_task(self.send_weekly_digest_emails())

    async def run_commission_expiry(self):
        """Cada 24h, marca como EXPIRED las commissions que cumplieron 365 dias."""
        await asyncio.sleep(180)
        from commission_service import expire_due_commissions
        while self.running:
            try:
                count = await expire_due_commissions(self.db)
                if count:
                    logger.info(f"[Scheduler] {count} comisiones expiradas")
            except Exception as e:
                logger.error(f"[Scheduler] commission expiry error: {e}")
            await asyncio.sleep(24 * 3600)

    async def send_trial_ending_emails(self):
        """Cada 24h, envía email a tenants con trial terminando en <=3 días.
        Idempotente por (tenant_id, days_left bucket): no envía 2 veces el mismo aviso."""
        await asyncio.sleep(240)
        from routers.coach import _trial_days_left, TRIAL_WARN_THRESHOLD_DAYS
        BASE_URL = (
            __import__("os").environ.get("PUBLIC_BASE_URL")
            or "https://inmobot-preview.preview.emergentagent.com"
        )
        while self.running:
            try:
                cursor = self.db.tenants.find(
                    {"active": True},
                    {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1,
                     "subscription_status": 1, "created_at": 1},
                )
                async for t in cursor:
                    days_left = _trial_days_left(t)
                    if days_left is None or days_left > TRIAL_WARN_THRESHOLD_DAYS:
                        continue
                    sent_key = f"trial_ending_{days_left}d"
                    already = await self.db.email_logs.find_one({
                        "email_type": "trial_ending_soon",
                        "subject": {"$regex": f"termina en {days_left}"},
                        "recipient_emails": {"$exists": True},
                        "lead_phone": sent_key,
                    }, {"_id": 1})
                    if already:
                        continue
                    agent = await self.db.agents.find_one(
                        {"tenant_id": t["tenant_id"], "role": "admin", "active": True},
                        {"_id": 0, "email": 1},
                    )
                    if not agent or not agent.get("email"):
                        continue
                    biz = t.get("business_name") or t.get("name") or t["tenant_id"]
                    try:
                        await self.email.send_trial_ending_soon(
                            to_email=agent["email"],
                            business_name=biz,
                            days_left=days_left,
                            upgrade_url=f"{BASE_URL}/config",
                        )
                        # marker de idempotencia: usar lead_phone como dedupe-key
                        await self.db.email_logs.update_one(
                            {"email_type": "trial_ending_soon",
                             "recipient_emails": [agent["email"]],
                             "subject": {"$regex": f"termina en {days_left}"}},
                            {"$set": {"lead_phone": sent_key}},
                        )
                    except Exception as e:
                        logger.warning(f"[Scheduler] trial email failed for {t['tenant_id']}: {e}")
            except Exception as e:
                logger.error(f"[Scheduler] trial ending task error: {e}")
            await asyncio.sleep(24 * 3600)

    async def send_weekly_digest_emails(self):
        """Cada lunes a las 09:00 UTC envía un resumen semanal a cada admin tenant activo."""
        await asyncio.sleep(300)
        last_run_iso = None
        while self.running:
            try:
                from datetime import datetime, timezone, timedelta
                now = datetime.now(timezone.utc)
                # Disparar lunes (weekday=0) entre 09:00-09:59 UTC, una vez por semana
                run_now = (now.weekday() == 0 and now.hour == 9
                           and last_run_iso != now.strftime("%G-W%V"))
                # Modo manual / dev: respetar env DIGEST_FORCE=1
                import os
                if os.environ.get("DIGEST_FORCE") == "1":
                    run_now = True
                if run_now:
                    sent = await self._send_digest_to_all_tenants()
                    last_run_iso = now.strftime("%G-W%V")
                    logger.info(f"[Scheduler] Weekly digest enviado a {sent} tenants")
            except Exception as e:
                logger.error(f"[Scheduler] weekly digest error: {e}")
            await asyncio.sleep(3600)  # check cada hora

    async def _send_digest_to_all_tenants(self) -> int:
        """Envía digest a todos los tenants admin activos. Retorna cantidad enviada."""
        from datetime import datetime, timezone, timedelta
        from commission_service import calculate_active_credit_for_tenant
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        cutoff_iso = cutoff.isoformat()
        sent = 0
        cursor = self.db.tenants.find(
            {"active": True, "subscription_status": {"$ne": "cancelled"}},
            {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1},
        )
        async for t in cursor:
            tid = t["tenant_id"]
            agent = await self.db.agents.find_one(
                {"tenant_id": tid, "role": "admin", "active": True},
                {"_id": 0, "email": 1},
            )
            if not agent or not agent.get("email"):
                continue
            try:
                leads_new = await self.db.leads.count_documents({
                    "tenant_id": tid,
                    "created_at": {"$gte": cutoff_iso},
                })
                leads_total = await self.db.leads.count_documents({"tenant_id": tid})
                conversions = await self.db.leads.count_documents({
                    "tenant_id": tid,
                    "status": {"$in": ["hot", "appointment", "completed"]},
                    "created_at": {"$gte": cutoff_iso},
                })
                ai_msgs = await self.db.usage_log.count_documents({
                    "tenant_id": tid,
                    "type": "ai_message",
                    "created_at": {"$gte": cutoff_iso},
                }) if "usage_log" in await self.db.list_collection_names() else 0
                credit = await calculate_active_credit_for_tenant(self.db, tid)
                stats = {
                    "days": 7,
                    "leads_new": leads_new,
                    "leads_total": leads_total,
                    "conversions": conversions,
                    "ai_messages": ai_msgs,
                    "referral_credit_capped_usd": credit.get("capped_amount_usd", 0),
                    "referral_active_count": credit.get("active_count", 0),
                }
                biz = t.get("business_name") or t.get("name") or tid
                await self.email.send_weekly_digest(
                    to_email=agent["email"],
                    business_name=biz,
                    stats=stats,
                )
                sent += 1
            except Exception as e:
                logger.warning(f"[Scheduler] digest fail tenant={tid}: {e}")
        return sent

    async def run_onboarding_coach(self):
        """Cada 6 horas, evalua todos los tenants y crea nudges del Coach."""
        await asyncio.sleep(120)  # esperar warmup
        from routers.coach import run_coach_for_all_tenants
        while self.running:
            try:
                result = await run_coach_for_all_tenants(self.db)
                logger.info(
                    f"[Scheduler] Onboarding Coach: {result.get('created', 0)} nudges nuevos "
                    f"sobre {result.get('evaluated', 0)} tenants evaluados"
                )
            except Exception as e:
                logger.error(f"[Scheduler] Coach error: {e}")
            await asyncio.sleep(6 * 3600)
    
    async def bill_monthly_overage(self):
        """Factura overage de IA al inicio del mes (dia 1, 04:00 UTC).
        bill_all_overages factura el mes anterior si dia<=3.
        """
        # Esperar 60s al inicio para evitar race con startup
        await asyncio.sleep(60)
        last_run_period = None
        while self.running:
            try:
                if not self.payment:
                    await asyncio.sleep(3600)
                    continue
                now = datetime.utcnow()
                # Ejecutar entre dia 1 y dia 3 del mes, hora 4-5 UTC, una vez por periodo
                if now.day <= 3 and now.hour == 4:
                    period_key = now.strftime("%Y-%m")
                    if last_run_period != period_key:
                        logger.info(f"[Scheduler] Iniciando facturacion overage del mes anterior")
                        try:
                            results = await self.payment.bill_all_overages()
                            logger.info(f"[Scheduler] Overage billing completo: {results.get('billed')} facturados, {results.get('skipped')} skipped, {results.get('errors')} errores")
                            last_run_period = period_key
                        except Exception as e:
                            logger.error(f"[Scheduler] Error facturando overage: {e}")
                # Revisar cada hora
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error en bill_monthly_overage: {str(e)}")
                await asyncio.sleep(3600)
    
    async def check_whatsapp_appointment_reminders(self):
        """Envía recordatorios por WhatsApp 24hs antes de la cita"""
        while self.running:
            try:
                if not self.wa:
                    await asyncio.sleep(3600)
                    continue
                
                now = datetime.utcnow()
                # Buscar citas en las próximas 24-25 horas
                reminder_start = now + timedelta(hours=23)
                reminder_end = now + timedelta(hours=25)
                
                leads = await self.db.leads.find({
                    "appointment_datetime": {
                        "$gte": reminder_start.isoformat(),
                        "$lt": reminder_end.isoformat()
                    },
                    "whatsapp_reminder_sent": {"$ne": True}
                }, {"_id": 0}).to_list(100)
                
                for lead in leads:
                    try:
                        phone = lead.get('phone')
                        name = lead.get('name', 'Cliente')
                        appointment = lead.get('appointment_datetime')
                        
                        if isinstance(appointment, str):
                            appointment = datetime.fromisoformat(appointment)
                        
                        formatted_date = appointment.strftime('%d/%m/%Y a las %H:%M')
                        
                        message = f"¡Hola {name}! 👋\n\n"
                        message += f"Te recordamos que tenés una cita agendada para *mañana {formatted_date}*.\n\n"
                        message += "¿Podés confirmar tu asistencia?\n\n"
                        message += "Si necesitás reagendar o cancelar, escribinos."
                        
                        # Enviar mensaje
                        self.wa.send_text_message(phone, message)
                        
                        # Marcar como enviado
                        await self.db.leads.update_one(
                            {"phone": phone},
                            {"$set": {"whatsapp_reminder_sent": True}}
                        )
                        
                        logger.info(f"Recordatorio WhatsApp enviado a {phone}")
                        
                    except Exception as e:
                        logger.error(f"Error enviando recordatorio WhatsApp a {lead.get('phone')}: {str(e)}")
                
                # Revisar cada hora
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error en check_whatsapp_appointment_reminders: {str(e)}")
                await asyncio.sleep(3600)
    
    async def check_appointment_reminders(self):
        """Revisa citas próximas y envía recordatorios 24hs antes"""
        while self.running:
            try:
                now = datetime.utcnow()
                tomorrow = now + timedelta(hours=24)
                tomorrow_plus_1h = now + timedelta(hours=25)
                
                config = await self.db.bot_config.find_one({})
                reminder_hours = config.get('appointment_reminder_hours', 24) if config else 24
                
                leads = await self.db.leads.find({
                    "appointment_datetime": {
                        "$gte": tomorrow.isoformat(),
                        "$lt": tomorrow_plus_1h.isoformat()
                    },
                    "appointment_reminder_sent": {"$ne": True}
                }, {
                    "_id": 0,
                    "phone": 1,
                    "name": 1,
                    "appointment_datetime": 1,
                    "appointment_type": 1
                }).to_list(100)
                
                for lead in leads:
                    try:
                        logger.info(f"Enviando recordatorio de cita para lead {lead['phone']}")
                        success = await self.email.send_appointment_reminder(lead, reminder_hours)
                        
                        if success:
                            await self.db.leads.update_one(
                                {"phone": lead['phone']},
                                {"$set": {"appointment_reminder_sent": True}}
                            )
                    except Exception as e:
                        logger.error(f"Error enviando recordatorio para {lead['phone']}: {str(e)}")
                
                await asyncio.sleep(3600)
            
            except Exception as e:
                logger.error(f"Error en check_appointment_reminders: {str(e)}")
                await asyncio.sleep(3600)
    
    async def check_warm_lead_reactivation(self):
        """Revisa leads tibios sin actividad y envía reactivación (máximo 1 email cada 7 días por lead)"""
        while self.running:
            try:
                config = await self.db.bot_config.find_one({})
                # Días sin actividad antes de enviar reactivación (default: 7 días)
                reactivation_days = config.get('warm_lead_reactivation_days', 7) if config else 7
                
                cutoff_date = (datetime.utcnow() - timedelta(days=reactivation_days)).isoformat()
                # Mínimo 7 días entre emails de reactivación
                min_days_between_emails = (datetime.utcnow() - timedelta(days=7)).isoformat()
                
                leads = await self.db.leads.find({
                    "status": "warm",
                    "last_message_at": {"$lt": cutoff_date},
                    "$or": [
                        {"last_reactivation_email_at": {"$exists": False}},
                        {"last_reactivation_email_at": None},
                        {"last_reactivation_email_at": {"$lt": min_days_between_emails}}
                    ]
                }, {
                    "_id": 0,
                    "phone": 1,
                    "name": 1,
                    "zone": 1,
                    "property_type": 1
                }).to_list(50)
                
                for lead in leads:
                    try:
                        logger.info(f"Enviando reactivación para lead tibio {lead['phone']}")
                        success = await self.email.send_warm_lead_reactivation(lead)
                        
                        if success:
                            await self.db.leads.update_one(
                                {"phone": lead['phone']},
                                {"$set": {"last_reactivation_email_at": datetime.utcnow().isoformat()}}
                            )
                    except Exception as e:
                        logger.error(f"Error enviando reactivación para {lead['phone']}: {str(e)}")
                
                # Revisar cada 12 horas (antes era 2 horas - muy frecuente)
                await asyncio.sleep(43200)
            
            except Exception as e:
                logger.error(f"Error en check_warm_lead_reactivation: {str(e)}")
                await asyncio.sleep(43200)
    
    async def stop(self):
        """Detiene las tareas programadas"""
        self.running = False
        logger.info("Tareas programadas detenidas")
