"""
Servicio de emails transaccionales con Resend
"""
import os
import asyncio
import logging
import resend
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

logger = logging.getLogger(__name__)

# Configuración
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = "hola@inmobot-ia.com"
SENDER_NAME = "InmoBot"

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
else:
    logger.warning("RESEND_API_KEY no configurada")


async def send_welcome_email(
    customer_email: str,
    customer_name: str,
    plan_name: str,
    amount: float
) -> dict:
    """Envía email de bienvenida cuando un cliente paga"""
    
    if not RESEND_API_KEY:
        logger.error("No se puede enviar email: RESEND_API_KEY no configurada")
        return {"status": "error", "message": "API key no configurada"}
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <img src="https://customer-assets.emergentagent.com/job_lead-manager-es/artifacts/l1ys0o2g_ChatGPT%20Image%203%20feb%202026%2C%2009_57_44%20p.m..png" alt="InmoBot" style="width: 100px; border-radius: 15px;">
        </div>
        
        <h1 style="color: #2563eb; text-align: center;">¡Bienvenido a InmoBot! 🎉</h1>
        
        <p>Hola <strong>{customer_name}</strong>,</p>
        
        <p>¡Gracias por elegir InmoBot! Tu pago ha sido procesado exitosamente.</p>
        
        <div style="background: #f8fafc; border-radius: 10px; padding: 20px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #1e40af;">Detalles de tu compra:</h3>
            <p style="margin: 5px 0;"><strong>Plan:</strong> {plan_name}</p>
            <p style="margin: 5px 0;"><strong>Monto:</strong> ${amount} USD</p>
        </div>
        
        <h3 style="color: #1e40af;">¿Qué sigue?</h3>
        <ol>
            <li>Nos pondremos en contacto contigo en las próximas 24 horas para coordinar la configuración.</li>
            <li>Configuraremos tu número de WhatsApp Business.</li>
            <li>Te daremos acceso a tu dashboard personalizado.</li>
            <li>Te capacitaremos en el uso del sistema (15-20 minutos).</li>
        </ol>
        
        <p>Si tenés alguna pregunta, respondé a este email o escribinos por WhatsApp.</p>
        
        <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
            <p style="color: #64748b; font-size: 14px;">
                InmoBot - Automatización para Inmobiliarias<br>
                <a href="https://app.inmobot-ia.com" style="color: #2563eb;">app.inmobot-ia.com</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    params = {
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": [customer_email],
        "subject": f"🏠 ¡Bienvenido a InmoBot, {customer_name}!",
        "html": html_content
    }
    
    try:
        email = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email de bienvenida enviado a {customer_email}")
        return {
            "status": "success",
            "message": f"Email enviado a {customer_email}",
            "email_id": email.get("id")
        }
    except Exception as e:
        logger.error(f"Error enviando email de bienvenida: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


async def send_notification_email(
    to_email: str,
    subject: str,
    message: str
) -> dict:
    """Envía email de notificación genérico"""
    
    if not RESEND_API_KEY:
        return {"status": "error", "message": "API key no configurada"}
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="https://customer-assets.emergentagent.com/job_lead-manager-es/artifacts/l1ys0o2g_ChatGPT%20Image%203%20feb%202026%2C%2009_57_44%20p.m..png" alt="InmoBot" style="width: 80px; border-radius: 12px;">
        </div>
        
        <div style="background: #f8fafc; border-radius: 10px; padding: 20px;">
            {message}
        </div>
        
        <div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">
            InmoBot - <a href="https://app.inmobot-ia.com" style="color: #2563eb;">app.inmobot-ia.com</a>
        </div>
    </body>
    </html>
    """
    
    params = {
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }
    
    try:
        email = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email enviado a {to_email}: {subject}")
        return {"status": "success", "email_id": email.get("id")}
    except Exception as e:
        logger.error(f"Error enviando email: {str(e)}")
        return {"status": "error", "message": str(e)}
