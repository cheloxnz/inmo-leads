#!/usr/bin/env python3
"""
InmoBot SaaS - Script de inicialización
Crea el superadmin (dueño del SaaS).
"""

import asyncio
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'inmobot_db')

    if not mongo_url:
        print("ERROR: MONGO_URL no configurada en .env")
        sys.exit(1)

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print("=" * 50)
    print("  INMOBOT SaaS - Inicializacion")
    print("=" * 50)
    print()

    # Check if superadmin exists
    existing = await db.agents.find_one({"role": "superadmin"})
    if existing:
        print(f"Ya existe un superadmin: {existing['email']}")
        resp = input("Crear otro? (s/n): ").strip().lower()
        if resp != 's':
            print("Cancelado.")
            client.close()
            return

    # Create superadmin
    from auth import get_password_hash

    email = input("Email del superadmin [admin@inmobot.com]: ").strip() or "admin@inmobot.com"
    password = input("Password [Admin123!]: ").strip() or "Admin123!"
    name = input("Nombre [Super Admin]: ").strip() or "Super Admin"

    superadmin = {
        "tenant_id": "__superadmin__",
        "name": name,
        "email": email,
        "phone": "",
        "password_hash": get_password_hash(password),
        "role": "superadmin",
        "specialties": [],
        "zones": [],
        "max_concurrent_leads": 0,
        "active": True,
        "created_at": datetime.utcnow().isoformat()
    }

    await db.agents.insert_one(superadmin)

    print()
    print("Superadmin creado exitosamente!")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print(f"  Rol: superadmin")
    print()

    # Ask to create a demo tenant
    create_demo = input("Crear tenant de ejemplo? (s/n): ").strip().lower()
    if create_demo == 's':
        tenant_id = input("  ID del tenant [demo-inmobiliaria]: ").strip() or "demo-inmobiliaria"
        tenant_name = input("  Nombre [Demo Inmobiliaria]: ").strip() or "Demo Inmobiliaria"
        admin_email = input("  Email admin del tenant [demo@inmobot.com]: ").strip() or "demo@inmobot.com"
        admin_pass = input("  Password admin [Demo123!]: ").strip() or "Demo123!"

        # Create tenant
        tenant = {
            "tenant_id": tenant_id,
            "name": tenant_name,
            "plan": "basic",
            "active": True,
            "whatsapp_phone_number_id": "",
            "whatsapp_access_token": "",
            "whatsapp_business_account_id": "",
            "webhook_verify_token": "",
            "max_leads": 500,
            "max_agents": 5,
            "subscription_status": "active",
            "subscription_plan": "basic",
            "contact_email": admin_email,
            "contact_phone": "",
            "country": "",
            "business_name": tenant_name,
            "business_tagline": "",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        await db.tenants.insert_one(tenant)

        # Create tenant admin
        tenant_admin = {
            "tenant_id": tenant_id,
            "name": "Administrador",
            "email": admin_email,
            "phone": "",
            "password_hash": get_password_hash(admin_pass),
            "role": "admin",
            "specialties": [],
            "zones": [],
            "max_concurrent_leads": 15,
            "active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        await db.agents.insert_one(tenant_admin)

        print()
        print(f"Tenant '{tenant_name}' creado!")
        print(f"  Admin: {admin_email} / {admin_pass}")

    print()
    print("Inicializacion completada!")
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
