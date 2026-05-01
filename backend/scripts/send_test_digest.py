"""Script puntual para mandar el digest semanal a cheloxnz@gmail.com.

Crea data sintética para que el email tenga contenido realista y dispara
send_weekly_digest directo (no usa el cron porque no hay tenant real).
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    cli = AsyncIOMotorClient(mongo_url)
    db = cli[db_name]

    from email_service import EmailService
    email_svc = EmailService(db)

    # Stats sintéticas que reflejan un tenant en pleno crecimiento
    stats = {
        "days": 7,
        "leads_new": 47,
        "leads_total": 312,
        "conversions": 9,
        "ai_messages": 1843,
        "referral_credit_capped_usd": 99,
        "referral_active_count": 2,
        "unmet_top": [
            {"name": "iPhone 15 Pro Max 256GB", "leads_count": 12, "price": 1299},
            {"name": "Samsung S24 Ultra", "leads_count": 8, "price": 1199},
            {"name": "MacBook Air M3 13'", "leads_count": 5, "price": 1099},
        ],
    }

    print("Enviando digest a cheloxnz@gmail.com ...")
    ok = await email_svc.send_weekly_digest(
        to_email="cheloxnz@gmail.com",
        business_name="Tu Negocio Demo",
        stats=stats,
    )
    print(f"Resultado: {'OK ✓ enviado' if ok else 'FAIL ✗ no se envió'}")
    cli.close()


if __name__ == "__main__":
    asyncio.run(main())
