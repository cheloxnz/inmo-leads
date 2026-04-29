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
