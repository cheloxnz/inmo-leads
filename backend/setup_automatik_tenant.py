"""
setup_automatik_tenant.py
=========================
Script one-shot para crear el tenant "automatik-media" en MongoDB.

Ejecutar en el VPS:
  cd /opt/inmo-leads/backend
  python setup_automatik_tenant.py

El tenant usa el mismo número de WhatsApp ya configurado en Meta
(Phone Number ID: 1019782844562200).

Si el tenant ya existe, no hace nada (idempotente).
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

TENANT_ID = "automatik-media"
PHONE_NUMBER_ID = "1019782844562200"


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # ── 1. Tenant ──────────────────────────────────────────────────────
    existing = await db.tenants.find_one({"tenant_id": TENANT_ID})
    if existing:
        print(f"✅ Tenant '{TENANT_ID}' ya existe — sin cambios")
    else:
        tenant_doc = {
            "tenant_id": TENANT_ID,
            "name": "Automatik Media",
            "plan": "enterprise",
            "active": True,
            "whatsapp_phone_number_id": PHONE_NUMBER_ID,
            "template_id": "automatik",   # identificador de flujo
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        await db.tenants.insert_one(tenant_doc)
        print(f"✅ Tenant '{TENANT_ID}' creado")

    # ── 2. BusinessProfile ─────────────────────────────────────────────
    existing_profile = await db.business_profiles.find_one({"tenant_id": TENANT_ID})
    profile_doc = {
        "tenant_id": TENANT_ID,
        "business_name": "Automatik Media",
        "business_description": (
            "Suite de herramientas IA para inmobiliarias: "
            "InmoGen (creativos para Meta Ads), InmoBot (calificación de leads 24/7) "
            "e InmoDesk (prospección B2B automatizada)."
        ),
        "industry": "Software SaaS — Inmobiliaria",
        "phone": "5491153250877",          # WhatsApp de Marcelo (recibe notificaciones)
        "email": "marcelo.dv@automatik-media.com",
        "website": "https://automatik-media.com",
        "bot_name": "Asistente de Automatik Media",
        "advisor_name": "Marcelo",
        "city": "Buenos Aires, Argentina",
        "business_hours": "Lun-Vie 9-18hs Argentina",
        "updated_at": datetime.utcnow().isoformat(),
    }

    if existing_profile:
        await db.business_profiles.update_one(
            {"tenant_id": TENANT_ID}, {"$set": profile_doc}
        )
        print(f"✅ BusinessProfile '{TENANT_ID}' actualizado")
    else:
        await db.business_profiles.insert_one(profile_doc)
        print(f"✅ BusinessProfile '{TENANT_ID}' creado")

    # ── 3. Usuario admin para el tenant (opcional) ─────────────────────
    # El SuperAdmin (admin@inmobot.com) ya gestiona todo desde el dashboard.
    # Si querés un usuario específico para este tenant:
    # existing_user = await db.users.find_one({"email": "marcelo@automatik-media.com"})
    # ...

    print("\n🚀 Setup completo. El bot de Automatik Media está listo.")
    print(f"   Tenant ID:   {TENANT_ID}")
    print(f"   Phone ID:    {PHONE_NUMBER_ID}")
    print(f"   Asesor:      +{profile_doc['phone']}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
