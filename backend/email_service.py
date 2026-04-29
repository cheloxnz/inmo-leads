import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
from models import EmailType, EmailLog

logger = logging.getLogger(__name__)

class EmailService:
    """Servicio para envío de notificaciones por email usando Gmail SMTP"""
    
    def __init__(self, db=None):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL")
        self.from_name = os.getenv("SMTP_FROM_NAME", "InmoBot AI")
        self.notification_emails = os.getenv("NOTIFICATION_EMAILS", "").split(",")
        self.db = db
        
        if not self.smtp_username or not self.smtp_password:
            logger.warning("Credenciales SMTP no configuradas. Emails deshabilitados.")
    
    async def send_email(self, to_emails: List[str], subject: str, html_body: str, text_body: Optional[str] = None, email_type: EmailType = EmailType.TEST, lead_phone: Optional[str] = None) -> bool:
        """Envía email usando Gmail SMTP y registra en log"""
        if not self.smtp_username or not self.smtp_password:
            logger.warning("No se puede enviar email: credenciales no configuradas")
            await self._log_email(email_type, to_emails, subject, False, "Credenciales no configuradas", lead_phone)
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ", ".join(to_emails)
            msg['Subject'] = subject
            
            if text_body:
                part1 = MIMEText(text_body, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(html_body, 'html')
            msg.attach(part2)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email enviado exitosamente a {to_emails}")
            await self._log_email(email_type, to_emails, subject, True, None, lead_phone)
            return True
        
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            await self._log_email(email_type, to_emails, subject, False, str(e), lead_phone)
            return False
    
    async def _log_email(self, email_type: EmailType, recipients: List[str], subject: str, success: bool, error: Optional[str], lead_phone: Optional[str]):
        """Registra envío de email en base de datos"""
        if not self.db:
            return
        
        try:
            log = EmailLog(
                email_type=email_type,
                recipient_emails=recipients,
                lead_phone=lead_phone,
                subject=subject,
                success=success,
                error_message=error
            )
            log_dict = log.model_dump()
            log_dict["sent_at"] = log.sent_at.isoformat()
            
            await self.db.email_logs.insert_one(log_dict)
        except Exception as e:
            logger.error(f"Error logging email: {str(e)}")
    
    async def send_hot_lead_notification(self, lead_data: dict) -> bool:
        """Envía notificación de lead caliente a los asesores"""
        if not self.notification_emails or not self.notification_emails[0]:
            logger.warning("No hay emails configurados para notificaciones")
            return False
        
        phone = lead_data.get('phone', 'N/A')
        name = lead_data.get('name') or 'Sin nombre'
        intent = lead_data.get('intent', 'N/A')
        zone = lead_data.get('zone', 'N/A')
        budget = lead_data.get('budget_text', 'N/A')
        property_type = lead_data.get('property_type', 'N/A')
        bedrooms = lead_data.get('bedrooms', 'N/A')
        urgency = lead_data.get('urgency', 'N/A')
        score = lead_data.get('score', 0)
        appointment = lead_data.get('appointment_datetime')
        
        subject = f"🔥 LEAD CALIENTE - Score {score}/12"
        
        text_body = f"""LEAD CALIENTE DETECTADO

Nombre: {name}
Teléfono: {phone}
Intención: {intent}
Zona: {zone}
Presupuesto: {budget}
Tipo: {property_type}
Dormitorios: {bedrooms}
Urgencia: {urgency}
Score: {score}/12
"""
        
        if appointment:
            if isinstance(appointment, str):
                appointment = datetime.fromisoformat(appointment)
            text_body += f"\nCita agendada: {appointment.strftime('%d/%m/%Y %H:%M')}hs"
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .info-row {{ margin: 15px 0; padding: 12px; background: white; border-radius: 8px; border-left: 4px solid #ef4444; }}
        .label {{ font-weight: bold; color: #6b7280; font-size: 12px; text-transform: uppercase; }}
        .value {{ color: #111827; font-size: 16px; margin-top: 4px; }}
        .score {{ background: #ef4444; color: white; padding: 8px 16px; border-radius: 20px; display: inline-block; font-weight: bold; margin-top: 10px; }}
        .appointment {{ background: #10b981; color: white; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; }}
        .footer {{ text-align: center; margin-top: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔥 LEAD CALIENTE DETECTADO</h1>
            <div class="score">Score: {score}/12</div>
        </div>
        <div class="content">
            <div class="info-row">
                <div class="label">Nombre</div>
                <div class="value">{name}</div>
            </div>
            <div class="info-row">
                <div class="label">Teléfono</div>
                <div class="value">{phone}</div>
            </div>
            <div class="info-row">
                <div class="label">Intención</div>
                <div class="value">{intent}</div>
            </div>
            <div class="info-row">
                <div class="label">Zona</div>
                <div class="value">{zone}</div>
            </div>
            <div class="info-row">
                <div class="label">Presupuesto</div>
                <div class="value">{budget}</div>
            </div>
            <div class="info-row">
                <div class="label">Tipo de Propiedad</div>
                <div class="value">{property_type} - {bedrooms} dormitorios</div>
            </div>
            <div class="info-row">
                <div class="label">Urgencia</div>
                <div class="value">{urgency}</div>
            </div>"""
        
        if appointment:
            if isinstance(appointment, str):
                appointment = datetime.fromisoformat(appointment)
            appointment_str = appointment.strftime('%d/%m/%Y a las %H:%M')
            html_body += f"""
            <div class="appointment">
                <strong>📅 Cita Agendada</strong><br>
                {appointment_str}hs
            </div>"""
        
        html_body += f"""
            <div class="footer">
                <p>Este es un lead caliente que requiere atención inmediata.</p>
                <p><strong>InmoBot AI</strong> - Sistema de Calificación Automática</p>
            </div>
        </div>
    </div>
</body>
</html>"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.HOT_LEAD,
            lead_phone=phone
        )
    
    async def send_appointment_reminder(self, lead_data: dict, hours_before: int = 24) -> bool:
        """Envía recordatorio de cita programada"""
        if not self.notification_emails or not self.notification_emails[0]:
            return False
        
        name = lead_data.get('name') or 'Cliente'
        phone = lead_data.get('phone', 'N/A')
        appointment = lead_data.get('appointment_datetime')
        appointment_type = lead_data.get('appointment_type', 'reunión')
        
        if not appointment:
            return False
        
        if isinstance(appointment, str):
            appointment = datetime.fromisoformat(appointment)
        
        subject = f"📅 Recordatorio: Cita con {name} en {hours_before}hs"
        
        text_body = f"""RECORDATORIO DE CITA

Cliente: {name}
Teléfono: {phone}
Tipo: {appointment_type}
Fecha: {appointment.strftime('%d/%m/%Y %H:%M')}hs

La cita es en {hours_before} horas.
"""
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .appointment-box {{ background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #3b82f6; margin: 20px 0; }}
        .time {{ font-size: 24px; font-weight: bold; color: #3b82f6; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📅 RECORDATORIO DE CITA</h1>
        </div>
        <div class="content">
            <div class="appointment-box">
                <p><strong>Cliente:</strong> {name}</p>
                <p><strong>Teléfono:</strong> {phone}</p>
                <p><strong>Tipo:</strong> {appointment_type}</p>
                <p class="time">{appointment.strftime('%d/%m/%Y a las %H:%M')}hs</p>
            </div>
            <p style="text-align: center; color: #6b7280;">La cita es en <strong>{hours_before} horas</strong></p>
        </div>
    </div>
</body>
</html>"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.APPOINTMENT_REMINDER,
            lead_phone=phone
        )
    
    async def send_warm_lead_reactivation(self, lead_data: dict) -> bool:
        """Envía email para reactivar lead tibio sin actividad"""
        if not self.notification_emails or not self.notification_emails[0]:
            return False
        
        phone = lead_data.get('phone', 'N/A')
        name = lead_data.get('name') or 'Cliente'
        zone = lead_data.get('zone', '')
        property_type = lead_data.get('property_type', 'propiedad')
        
        subject = f"🟡 Lead Tibio sin actividad - {name}"
        
        text_body = f"""REACTIVACIÓN DE LEAD TIBIO

Cliente: {name}
Teléfono: {phone}
Zona: {zone}
Tipo: {property_type}

Este lead lleva 3 días sin actividad. Considera enviarle un mensaje por WhatsApp con novedades.
"""
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .lead-box {{ background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #f59e0b; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🟡 LEAD TIBIO - REACTIVACIÓN</h1>
        </div>
        <div class="content">
            <div class="lead-box">
                <p><strong>Cliente:</strong> {name}</p>
                <p><strong>Teléfono:</strong> {phone}</p>
                <p><strong>Zona:</strong> {zone}</p>
                <p><strong>Tipo:</strong> {property_type}</p>
            </div>
            <p style="text-align: center; color: #6b7280;">Este lead lleva <strong>3 días sin actividad</strong>. Considera contactarlo con novedades.</p>
        </div>
    </div>
</body>
</html>"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.WARM_LEAD_REACTIVATION,
            lead_phone=phone
        )
    
    async def send_new_referral_commission(
        self,
        to_email: str,
        referrer_business_name: str,
        referred_business_name: str,
        amount_per_month_usd: float,
        active_count: int,
        active_credit_capped_usd: float,
        plan_price_usd: float,
        is_capped: bool,
    ) -> bool:
        """Notifica al referrer que ganó una nueva comisión recurrente."""
        if not to_email:
            return False
        subject = f"🎉 Conseguiste un nuevo referido — ${amount_per_month_usd:.0f}/mes ganados"
        cap_note = (
            f"<p style='margin-top:14px;color:#047857;'><strong>¡Tu suscripción es gratis!</strong> "
            f"Llegaste al tope del plan (${plan_price_usd:.0f}/mes). El descuento se aplica al 100%.</p>"
            if is_capped else ""
        )
        text_body = (
            f"¡Hola {referrer_business_name}!\n\n"
            f"Conseguiste un nuevo referido: {referred_business_name}.\n"
            f"Te genera ${amount_per_month_usd:.0f}/mes de descuento durante 12 meses.\n\n"
            f"Tu crédito activo este mes: -${active_credit_capped_usd:.0f} ({active_count} referidos activos).\n"
            f"Se descontará automáticamente en tu próxima factura.\n\n"
            f"Compartí tu link de referido para sumar más:\n"
            f"https://inmobot-preview.preview.emergentagent.com/signup\n\n"
            f"InmoBot AI"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; line-height:1.55; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:600px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#10b981 0%,#059669 100%); color:#fff; padding:32px 28px; text-align:center; }}
  .header h1 {{ margin:0; font-size:22px; }}
  .header .amount {{ font-size:42px; font-weight:800; margin-top:6px; letter-spacing:-0.02em; }}
  .header .subtitle {{ opacity:0.92; font-size:14px; margin-top:6px; }}
  .content {{ padding:28px; }}
  .stats {{ display:flex; gap:12px; margin:18px 0; flex-wrap:wrap; }}
  .stat {{ flex:1 1 140px; background:#ecfdf5; border:1px solid #6ee7b7; border-radius:10px; padding:14px; }}
  .stat .lbl {{ font-size:11px; color:#047857; text-transform:uppercase; letter-spacing:0.05em; font-weight:600; }}
  .stat .val {{ font-size:24px; font-weight:700; color:#065f46; margin-top:4px; }}
  .footer {{ padding:18px 28px; color:#6b7280; font-size:12px; text-align:center; border-top:1px solid #e5e7eb; }}
</style></head>
<body>
  <div class='container'>
    <div class='header'>
      <h1>🎉 Conseguiste un nuevo referido</h1>
      <div class='amount'>+${amount_per_month_usd:.0f}/mes</div>
      <div class='subtitle'>durante los próximos 12 meses</div>
    </div>
    <div class='content'>
      <p>¡Hola <strong>{referrer_business_name}</strong>!</p>
      <p><strong>{referred_business_name}</strong> se sumó a InmoBot con tu link de referido y ya está pagando su suscripción 🚀</p>
      <div class='stats'>
        <div class='stat'><div class='lbl'>Crédito activo</div><div class='val'>-${active_credit_capped_usd:.0f}</div></div>
        <div class='stat'><div class='lbl'>Referidos activos</div><div class='val'>{active_count}</div></div>
      </div>
      <p style='color:#6b7280; font-size:14px;'>El descuento se aplica automáticamente en tu próxima factura. No tenés que hacer nada.</p>
      {cap_note}
    </div>
    <div class='footer'>
      Querés ganar más? Compartí tu link de referido desde el panel de Facturación.<br>
      InmoBot AI · Programa de referidos
    </div>
  </div>
</body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.NEW_REFERRAL_COMMISSION,
        )

    async def send_trial_ending_soon(
        self,
        to_email: str,
        business_name: str,
        days_left: int,
        upgrade_url: str,
    ) -> bool:
        """Aviso al admin cuando faltan pocos días al trial."""
        if not to_email:
            return False
        subject = f"⏰ Tu trial de InmoBot termina en {days_left} {'día' if days_left==1 else 'días'}"
        text_body = (
            f"Hola {business_name},\n\n"
            f"Tu período de prueba gratuita termina en {days_left} días.\n"
            f"Suscribite ahora para no perder tu bot, leads y configuración:\n{upgrade_url}\n\n"
            f"InmoBot AI"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><style>
  body {{ font-family: -apple-system, Arial, sans-serif; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:560px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%); color:#fff; padding:28px; text-align:center; }}
  .content {{ padding:28px; line-height:1.55; }}
  .cta {{ display:inline-block; padding:12px 22px; background:#6366f1; color:#fff; text-decoration:none; border-radius:8px; font-weight:600; margin-top:14px; }}
</style></head>
<body><div class='container'>
  <div class='header'><h1 style='margin:0;font-size:22px;'>⏰ Tu trial termina pronto</h1></div>
  <div class='content'>
    <p>Hola <strong>{business_name}</strong>,</p>
    <p>Tu período de prueba gratuita termina en <strong>{days_left} {'día' if days_left==1 else 'días'}</strong>.</p>
    <p>No pierdas el bot que construiste, los leads que ya generaste ni tu configuración. Activá tu plan en 1 minuto:</p>
    <p style='text-align:center;'><a class='cta' href='{upgrade_url}'>Suscribirme ahora</a></p>
    <p style='color:#6b7280;font-size:13px;margin-top:24px;'>Si tenés dudas, respondé este mail y te ayudamos.</p>
  </div>
</div></body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.TRIAL_ENDING_SOON,
        )

    async def send_weekly_digest(
        self,
        to_email: str,
        business_name: str,
        stats: dict,
    ) -> bool:
        """Resumen semanal para retención.

        stats: {leads_new, leads_total, conversions, ai_messages, days,
                referral_credit_capped_usd, referral_active_count}
        """
        if not to_email:
            return False
        days = stats.get("days", 7)
        subject = f"📊 Tu resumen semanal de InmoBot — {business_name}"
        leads_new = stats.get("leads_new", 0)
        leads_total = stats.get("leads_total", 0)
        conversions = stats.get("conversions", 0)
        ai_msgs = stats.get("ai_messages", 0)
        savings = stats.get("referral_credit_capped_usd", 0)
        ref_active = stats.get("referral_active_count", 0)
        text_body = (
            f"Resumen últimos {days} días para {business_name}:\n"
            f"- Leads nuevos: {leads_new}\n"
            f"- Conversiones: {conversions}\n"
            f"- Mensajes IA: {ai_msgs}\n"
            f"- Ahorro por referidos este mes: ${savings:.0f} ({ref_active} activos)\n"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><style>
  body {{ font-family:-apple-system,Arial,sans-serif; color:#111827; background:#f3f4f6; margin:0; }}
  .container {{ max-width:600px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%); color:#fff; padding:24px 28px; text-align:left; }}
  .stats {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:18px 28px; }}
  .stat {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:14px; }}
  .stat .lbl {{ font-size:11px; color:#6b7280; text-transform:uppercase; letter-spacing:0.05em; font-weight:600; }}
  .stat .val {{ font-size:22px; font-weight:700; color:#111827; margin-top:4px; }}
  .footer {{ padding:18px 28px; color:#6b7280; font-size:12px; }}
</style></head>
<body><div class='container'>
  <div class='header'><h1 style='margin:0;font-size:20px;'>📊 Tu resumen semanal</h1>
    <div style='opacity:0.9;font-size:13px;margin-top:4px;'>Últimos {days} días · {business_name}</div></div>
  <div class='stats'>
    <div class='stat'><div class='lbl'>Leads nuevos</div><div class='val'>{leads_new}</div></div>
    <div class='stat'><div class='lbl'>Conversiones</div><div class='val'>{conversions}</div></div>
    <div class='stat'><div class='lbl'>Mensajes IA</div><div class='val'>{ai_msgs}</div></div>
    <div class='stat'><div class='lbl'>Total leads</div><div class='val'>{leads_total}</div></div>
    <div class='stat' style='grid-column:1/-1; background:#ecfdf5; border-color:#6ee7b7;'>
      <div class='lbl' style='color:#047857;'>Ahorro por referidos este mes</div>
      <div class='val' style='color:#065f46;'>${savings:.0f} <span style='font-size:13px; color:#047857; font-weight:500;'>({ref_active} activos)</span></div>
    </div>
  </div>
  <div class='footer'>Querés ver más? Iniciá sesión en tu dashboard de InmoBot.</div>
</div></body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.WEEKLY_DIGEST,
        )

    async def test_email(self) -> bool:
        """Envía email de prueba para verificar configuración"""
        if not self.notification_emails or not self.notification_emails[0]:
            logger.error("No hay emails configurados para notificaciones")
            return False
        
        subject = "✅ Test InmoBot AI - Configuración exitosa"
        
        html_body = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; border-radius: 10px; }
        .content { padding: 30px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Configuración Exitosa</h1>
        </div>
        <div class="content">
            <p>¡Felicitaciones! El sistema de notificaciones por email está funcionando correctamente.</p>
            <p>Recibirás alertas automáticas cuando:</p>
            <ul>
                <li>🔥 Se detecte un lead caliente (Score ≥ 7)</li>
                <li>📅 Se agende una cita</li>
                <li>🟡 Leads tibios necesiten reactivación (3 días sin actividad)</li>
                <li>⏰ Recordatorios de citas 24hs antes</li>
            </ul>
            <p><strong>InmoBot AI</strong> - Sistema de Calificación Automática</p>
        </div>
    </div>
</body>
</html>"""
        
        text_body = """Configuración Exitosa

El sistema de notificaciones por email está funcionando correctamente.

Recibirás alertas automáticas cuando se detecten leads calientes, citas agendadas y leads tibios.

InmoBot AI - Sistema de Calificación Automática
"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.TEST
        )
