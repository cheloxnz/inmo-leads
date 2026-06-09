"""
setup_automatik_tenant.py
=========================
Script one-shot para configurar el tenant "automatik-media" en MongoDB.

Acciones:
  1. Crea (o actualiza) el tenant "automatik-media"
  2. Asigna el phone_number_id 1019782844562200 a automatik-media
  3. Quita ese phone_number_id del tenant "demo-inmobiliaria"
  4. Crea (o actualiza) el BusinessProfile del tenant
  5. Crea el usuario admin del tenant: marcelo@automatik-media.com

Ejecutar dentro del container:
  docker exec inmobot-backend python setup_automatik_tenant.py

Es idempotente: puede correrse múltiples veces sin problemas.
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ['MONGO_URL']
DB_NAME   = os.environ['DB_NAME']

TENANT_ID       = "automatik-media"
PHONE_NUMBER_ID = "1019782844562200"
ADMIN_EMAIL     = "marcelo@automatik-media.com"
ADMIN_PASSWORD  = "Automatik2026!"     # cambiar post-setup si querés


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # ── 1. Tenant ──────────────────────────────────────────────────────
    existing = await db.tenants.find_one({"tenant_id": TENANT_ID})
    tenant_doc = {
        "tenant_id": TENANT_ID,
        "name": "Automatik Media",
        "plan": "enterprise",
        "active": True,
        "whatsapp_phone_number_id": PHONE_NUMBER_ID,
        "template_id": "automatik",
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing:
        await db.tenants.update_one({"tenant_id": TENANT_ID}, {"$set": tenant_doc})
        print(f"✅ Tenant '{TENANT_ID}' actualizado")
    else:
        tenant_doc["created_at"] = datetime.utcnow().isoformat()
        await db.tenants.insert_one(tenant_doc)
        print(f"✅ Tenant '{TENANT_ID}' creado")

    # ── 2. Quitar phone_number_id de demo-inmobiliaria ─────────────────
    demo = await db.tenants.find_one({"tenant_id": "demo-inmobiliaria"})
    if demo and demo.get("whatsapp_phone_number_id") == PHONE_NUMBER_ID:
        await db.tenants.update_one(
            {"tenant_id": "demo-inmobiliaria"},
            {"$set": {"whatsapp_phone_number_id": "", "updated_at": datetime.utcnow().isoformat()}}
        )
        print("✅ phone_number_id quitado de demo-inmobiliaria")
    else:
        print("ℹ️  demo-inmobiliaria no tenía ese phone_number_id (ok)")

    # ── 3. BusinessProfile ─────────────────────────────────────────────
    profile_doc = {
        "tenant_id": TENANT_ID,
        "business_name": "Automatik Media",
        "business_description": (
            "Suite de herramientas IA para inmobiliarias: "
            "InmoGen (creativos Meta Ads), InmoBot (calificación leads 24/7), "
            "InmoDesk (prospección B2B automática)."
        ),
        "industry": "Software SaaS — Inmobiliaria",
        "phone": "5491153250877",           # WhatsApp personal Marcelo
        "email": "marcelo.dv@automatik-media.com",
        "website": "https://automatik-media.com",
        "bot_name": "Asistente de Automatik Media",
        "advisor_name": "Marcelo",
        "city": "Buenos Aires, Argentina",
        "business_hours": "Lun-Vie 9-18hs Argentina",
        "updated_at": datetime.utcnow().isoformat(),
    }
    existing_profile = await db.business_profiles.find_one({"tenant_id": TENANT_ID})
    if existing_profile:
        await db.business_profiles.update_one({"tenant_id": TENANT_ID}, {"$set": profile_doc})
        print(f"✅ BusinessProfile '{TENANT_ID}' actualizado")
    else:
        await db.business_profiles.insert_one(profile_doc)
        print(f"✅ BusinessProfile '{TENANT_ID}' creado")

    # ── 4. Usuario admin del tenant ────────────────────────────────────
    from auth import get_password_hash
    existing_user = await db.agents.find_one({"email": ADMIN_EMAIL})
    user_doc = {
        "email": ADMIN_EMAIL,
        "name": "Marcelo Del Valle",
        "tenant_id": TENANT_ID,
        "role": "admin",
        "active": True,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing_user:
        await db.agents.update_one({"email": ADMIN_EMAIL}, {"$set": user_doc})
        print(f"✅ Usuario '{ADMIN_EMAIL}' actualizado")
    else:
        user_doc["password_hash"] = get_password_hash(ADMIN_PASSWORD)
        user_doc["created_at"] = datetime.utcnow().isoformat()
        await db.agents.insert_one(user_doc)
        print(f"✅ Usuario '{ADMIN_EMAIL}' creado con contraseña: {ADMIN_PASSWORD}")

    print("\n🚀 Setup completo.")
    print(f"   Tenant:      {TENANT_ID}")
    print(f"   Phone ID:    {PHONE_NUMBER_ID}")
    print(f"   Admin:       {ADMIN_EMAIL}")
    print(f"   Password:    {ADMIN_PASSWORD}")
    print(f"\n   ⚠️  Cambiá la contraseña en producción desde el dashboard.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
