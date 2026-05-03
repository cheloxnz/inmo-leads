import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
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
        asyncio.create_task(self.run_upsell_checks())
        asyncio.create_task(self.send_admin_weekly_report())
        asyncio.create_task(self.run_whatsapp_health_checks())

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
        """Cada 24h, envía emails de trial según cadencia:
        - días_left == 4: halfway check-in (solo 1 vez)
        - días_left in {3, 1, 0}: warning clásico por bucket
        - días_left < 0 (expirado, hasta -30): email de expirado (solo 1 vez)
        Idempotente por (tenant_id, bucket): no envía 2 veces el mismo aviso."""
        await asyncio.sleep(240)
        from routers.coach import _trial_days_left
        BASE_URL = (
            __import__("os").environ.get("PUBLIC_BASE_URL")
            or "https://inmobot-preview.preview.emergentagent.com"
        )
        WARN_BUCKETS = {3, 1, 0}
        HALFWAY_DAY = 4  # día 3 del trial (de 7) = 4 días left
        while self.running:
            try:
                cursor = self.db.tenants.find(
                    {"active": True},
                    {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1,
                     "subscription_status": 1, "created_at": 1},
                )
                async for t in cursor:
                    days_left = _trial_days_left(t)
                    if days_left is None:
                        continue
                    # Decide tipo de email
                    if days_left == HALFWAY_DAY:
                        bucket, send_fn_name = "halfway", "send_trial_halfway"
                    elif days_left in WARN_BUCKETS:
                        bucket, send_fn_name = f"warn_{days_left}d", "send_trial_ending_soon"
                    elif -30 <= days_left < 0:
                        bucket, send_fn_name = "expired", "send_trial_expired"
                    else:
                        continue

                    # Idempotencia por (tenant, bucket)
                    sent_key = f"trial_{bucket}_{t['tenant_id']}"
                    already = await self.db.email_logs.find_one(
                        {"lead_phone": sent_key}, {"_id": 1}
                    )
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
                        send_fn = getattr(self.email, send_fn_name)
                        kwargs = dict(
                            to_email=agent["email"],
                            business_name=biz,
                            upgrade_url=f"{BASE_URL}/config",
                        )
                        # Solo halfway/warning llevan days_left
                        if send_fn_name != "send_trial_expired":
                            kwargs["days_left"] = max(0, days_left)
                        await send_fn(**kwargs)
                        # Registrar en email_logs con dedupe-key
                        await self.db.email_logs.insert_one({
                            "email_type": "trial_ending_soon",
                            "recipient_emails": [agent["email"]],
                            "tenant_id": t["tenant_id"],
                            "lead_phone": sent_key,  # campo usado como dedupe-key
                            "subject": f"trial_{bucket}",
                            "sent_at": datetime.utcnow().isoformat(),
                        })
                    except Exception as e:
                        logger.warning(
                            f"[Scheduler] trial email failed for {t['tenant_id']}: {e}"
                        )
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

                # Top-3 productos con demanda insatisfecha (Iter32b)
                unmet_top = []
                try:
                    pipeline = [
                        {"$match": {"tenant_id": tid, "notified_at": None}},
                        {"$group": {
                            "_id": "$product_id",
                            "leads_count": {"$sum": 1},
                            "product_name": {"$first": "$product_name"},
                        }},
                        {"$sort": {"leads_count": -1}},
                        {"$limit": 5},
                    ]
                    rows = await self.db.product_waitlist.aggregate(pipeline).to_list(5)
                    for r in rows:
                        prod = await self.db.products.find_one(
                            {"tenant_id": tid, "product_id": r["_id"]}, {"_id": 0},
                        )
                        # Solo incluir si sigue agotado
                        if prod:
                            stock = prod.get("stock_quantity")
                            still_out = (
                                prod.get("active") is False
                                or (stock is not None and stock <= 0)
                            )
                        else:
                            still_out = True
                        if still_out:
                            unmet_top.append({
                                "name": r.get("product_name") or (prod or {}).get("name", ""),
                                "leads_count": r["leads_count"],
                                "price": (prod or {}).get("price", 0),
                            })
                        if len(unmet_top) >= 3:
                            break
                except Exception as e:
                    logger.warning(f"[digest] unmet demand fail tenant={tid}: {e}")

                stats = {
                    "days": 7,
                    "leads_new": leads_new,
                    "leads_total": leads_total,
                    "conversions": conversions,
                    "ai_messages": ai_msgs,
                    "referral_credit_capped_usd": credit.get("capped_amount_usd", 0),
                    "referral_active_count": credit.get("active_count", 0),
                    "unmet_top": unmet_top,
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

    async def run_upsell_checks(self):
        """Cada 24h, evalúa tenants Pro con alta demanda insatisfecha y dispara
        emails de upsell automático. Idempotente con cooldown de 30 días.
        También marca conversiones (tenant que upgradeó a Enterprise post-upsell).
        """
        await asyncio.sleep(360)  # warmup
        from upsell_service import check_and_send_upsells, mark_upsell_conversions
        while self.running:
            try:
                result = await check_and_send_upsells(self.db, self.email)
                conv = await mark_upsell_conversions(self.db)
                if result.get("sent", 0) > 0 or result.get("evaluated", 0) > 0 or conv > 0:
                    logger.info(
                        f"[Scheduler] Upsell run: evaluated={result['evaluated']} "
                        f"sent={result['sent']} skipped_cooldown={result['skipped_cooldown']} "
                        f"conversions_marked={conv}"
                    )
            except Exception as e:
                logger.error(f"[Scheduler] upsell run error: {e}")
            await asyncio.sleep(24 * 3600)

    async def send_admin_weekly_report(self):
        """Todos los lunes 9 UTC: envía reporte agregado al superadmin.

        Override con DIGEST_FORCE=1 para disparo manual al arrancar.
        """
        await asyncio.sleep(600)  # warmup
        while self.running:
            now = datetime.now(timezone.utc)
            force = os.environ.get("DIGEST_FORCE") == "1"
            should_run = (now.weekday() == 0 and now.hour == 9) or force
            if should_run:
                try:
                    await self._send_admin_report()
                    if force:
                        os.environ["DIGEST_FORCE"] = "0"
                        break
                except Exception as e:
                    logger.error(f"[Scheduler] admin report error: {e}")
            await asyncio.sleep(3600)

    async def run_whatsapp_health_checks(self):
        """Cada 12h re-chequea el estado de WhatsApp de todos los tenants con
        credenciales configuradas y refresca `tenants.whatsapp_last_check`.

        Detecta regresiones silenciosas: tokens expirados en Meta, quality
        rating que bajó a YELLOW/RED, número que perdió la verificación.
        Si un tenant pasa de OK a ERROR, loguea un WARN para que se pueda
        alertar (y opcionalmente agregar notificación email en el futuro).

        Override con WA_HEALTH_FORCE=1 para disparo manual al arrancar.
        """
        await asyncio.sleep(900)  # warmup 15 min post-start
        from routers.config import _run_whatsapp_check
        interval_hours = int(os.environ.get("WA_HEALTH_INTERVAL_HOURS", "12"))
        while self.running:
            force = os.environ.get("WA_HEALTH_FORCE") == "1"
            try:
                cursor = self.db.tenants.find(
                    {
                        "active": True,
                        "whatsapp_phone_number_id": {"$nin": ["", None]},
                        "whatsapp_access_token": {"$nin": ["", None]},
                    },
                    {"_id": 0, "tenant_id": 1, "whatsapp_last_check": 1},
                )
                checked = 0
                regressions = 0
                async for t in cursor:
                    tid = t["tenant_id"]
                    prev_ok = bool((t.get("whatsapp_last_check") or {}).get("ok"))
                    try:
                        result = await _run_whatsapp_check(tid)
                        checked += 1
                        # Detectar regresión: estaba OK y ahora no
                        if prev_ok and not result.get("ok"):
                            regressions += 1
                            logger.warning(
                                f"[wa_health_cron] REGRESSION tenant={tid} "
                                f"status={result.get('status')} msg={result.get('message')}"
                            )
                    except Exception as e:
                        logger.warning(f"[wa_health_cron] check failed tenant={tid}: {e}")
                if checked > 0:
                    logger.info(
                        f"[wa_health_cron] run: checked={checked} regressions={regressions}"
                    )
                if force:
                    os.environ["WA_HEALTH_FORCE"] = "0"
                    break
            except Exception as e:
                logger.error(f"[Scheduler] whatsapp health cron error: {e}")
            await asyncio.sleep(interval_hours * 3600)

    async def _send_admin_report(self) -> bool:
        """Arma stats cross-tenant + envía el email al SUPERADMIN_EMAIL."""
        target = os.environ.get("SUPERADMIN_EMAIL")
        if not target:
            logger.info("[admin_report] SUPERADMIN_EMAIL no configurado, skip")
            return False
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        cutoff_iso = cutoff.isoformat()

        active_tenants = await self.db.tenants.count_documents({
            "active": True,
            "subscription_status": {"$ne": "cancelled"},
        })
        new_tenants = await self.db.tenants.count_documents({
            "created_at": {"$gte": cutoff_iso},
        })
        total_leads = await self.db.leads.count_documents({
            "created_at": {"$gte": cutoff_iso},
        })
        hot_leads = await self.db.leads.count_documents({
            "status": "hot",
            "created_at": {"$gte": cutoff_iso},
        })

        # Upsells (Iter32d/e)
        upsells_sent = 0
        upsells_converted = 0
        upsells_mrr = 0
        try:
            upsells_sent = await self.db.upsell_events.count_documents({
                "sent_at": {"$gte": cutoff_iso},
            })
            upsells_converted = await self.db.upsell_events.count_documents({
                "sent_at": {"$gte": cutoff_iso},
                "converted": True,
            })
            # MRR adicional estimado (Enterprise $249 - Pro $99 = $150 × convertidos)
            upsells_mrr = upsells_converted * 150
        except Exception:
            pass

        # Demanda total cross-tenant
        total_demand_usd = 0.0
        try:
            pipeline = [
                {"$match": {"notified_at": None}},
                {"$group": {
                    "_id": {"tenant_id": "$tenant_id", "product_id": "$product_id"},
                    "leads_count": {"$sum": 1},
                }},
            ]
            rows = await self.db.product_waitlist.aggregate(pipeline).to_list(5000)
            for r in rows:
                tid = r["_id"]["tenant_id"]
                pid = r["_id"]["product_id"]
                prod = await self.db.products.find_one(
                    {"tenant_id": tid, "product_id": pid}, {"_id": 0, "price": 1},
                )
                price = (prod or {}).get("price", 0) or 0
                total_demand_usd += r["leads_count"] * price
        except Exception:
            pass

        # Top 10 tenants por leads esta semana
        pipeline_top = [
            {"$match": {"created_at": {"$gte": cutoff_iso}}},
            {"$group": {"_id": "$tenant_id", "leads": {"$sum": 1}}},
            {"$sort": {"leads": -1}},
            {"$limit": 10},
        ]
        top_rows = await self.db.leads.aggregate(pipeline_top).to_list(10)
        top_tenants = []
        for r in top_rows:
            tenant = await self.db.tenants.find_one(
                {"tenant_id": r["_id"]},
                {"_id": 0, "business_name": 1, "subscription_plan": 1},
            )
            if tenant:
                top_tenants.append({
                    "name": tenant.get("business_name", r["_id"]),
                    "plan": tenant.get("subscription_plan", "—"),
                    "leads": r["leads"],
                })

        # Churn risk: tenants activos con leads esta semana < 50% del promedio
        # de las últimas 4 semanas (excluyendo trial < 14d porque ramp-up es normal).
        churn_risk = []
        try:
            four_weeks_ago = (now - timedelta(days=28)).isoformat()
            tenants_active = self.db.tenants.find({
                "active": True,
                "subscription_status": {"$nin": ["cancelled", "trial"]},
            }, {"_id": 0, "tenant_id": 1, "business_name": 1, "subscription_plan": 1, "created_at": 1})
            async for t in tenants_active:
                tid = t["tenant_id"]
                created = t.get("created_at", "")
                # Skip si el tenant es muy nuevo (< 28 días) — no hay baseline
                if created and created > four_weeks_ago:
                    continue
                leads_this_week = await self.db.leads.count_documents({
                    "tenant_id": tid,
                    "created_at": {"$gte": cutoff_iso},
                })
                leads_last_4w = await self.db.leads.count_documents({
                    "tenant_id": tid,
                    "created_at": {"$gte": four_weeks_ago, "$lt": cutoff_iso},
                })
                avg_weekly = leads_last_4w / 4 if leads_last_4w else 0
                # Ruido: solo considerar si el baseline tenía al menos 5 leads/sem
                if avg_weekly < 5:
                    continue
                ratio = leads_this_week / avg_weekly if avg_weekly else 1
                if ratio < 0.5:
                    drop_pct = round((1 - ratio) * 100, 0)
                    churn_risk.append({
                        "name": t.get("business_name", tid),
                        "plan": t.get("subscription_plan", "—"),
                        "tenant_id": tid,
                        "leads_this_week": leads_this_week,
                        "avg_weekly": round(avg_weekly, 1),
                        "drop_pct": drop_pct,
                    })
            # Top 10 riesgos ordenados por drop
            churn_risk.sort(key=lambda x: x["drop_pct"], reverse=True)
            churn_risk = churn_risk[:10]
        except Exception as e:
            logger.warning(f"[admin_report] churn risk calc failed: {e}")

        stats = {
            "days": 7,
            "active_tenants": active_tenants,
            "new_tenants": new_tenants,
            "total_leads": total_leads,
            "hot_leads": hot_leads,
            "upsells_sent": upsells_sent,
            "upsells_converted": upsells_converted,
            "upsells_mrr_added": upsells_mrr,
            "total_demand_detected_usd": round(total_demand_usd, 2),
            "top_tenants": top_tenants,
            "churn_risk": churn_risk,
        }
        ok = await self.email.send_admin_weekly_report(
            to_email=target, stats=stats,
        )
        logger.info(
            f"[admin_report] sent={ok} tenants={active_tenants} "
            f"upsells_sent={upsells_sent} demand=${total_demand_usd:.0f}"
        )
        return ok

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
                        logger.info("[Scheduler] Iniciando facturacion overage del mes anterior")
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
