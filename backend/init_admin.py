#!/usr/bin/env python3
"""
Script de inicialización de InmoBot
Crea el usuario administrador inicial

Uso:
    python init_admin.py

El script creará:
    - Usuario: admin@inmobot.com
    - Contraseña: Admin123!
    
IMPORTANTE: Cambiar la contraseña después del primer login
"""

import os
import sys
from datetime import datetime, timezone

# Agregar el directorio backend al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
from passlib.context import CryptContext

# Configuración
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'inmobot_db')

# Hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_admin():
    """Crear usuario administrador inicial"""
    
    if not MONGO_URL:
        print("❌ Error: MONGO_URL no está configurada en .env")
        sys.exit(1)
    
    print("🔄 Conectando a MongoDB...")
    
    try:
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        
        # Verificar conexión
        client.admin.command('ping')
        print("✅ Conectado a MongoDB")
        
    except Exception as e:
        print(f"❌ Error conectando a MongoDB: {e}")
        sys.exit(1)
    
    # Datos del admin
    admin_email = "admin@inmobot.com"
    admin_password = "Admin123!"
    
    # Verificar si ya existe
    existing = db.users.find_one({"email": admin_email})
    
    if existing:
        print(f"⚠️  El usuario {admin_email} ya existe.")
        response = input("¿Deseas resetear la contraseña? (s/n): ").strip().lower()
        
        if response == 's':
            db.users.update_one(
                {"email": admin_email},
                {"$set": {
                    "password_hash": get_password_hash(admin_password),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            print(f"✅ Contraseña reseteada para {admin_email}")
        else:
            print("ℹ️  No se realizaron cambios.")
            return
    else:
        # Crear nuevo usuario admin
        admin_user = {
            "email": admin_email,
            "username": "Administrador",
            "password_hash": get_password_hash(admin_password),
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        db.users.insert_one(admin_user)
        print(f"✅ Usuario administrador creado")
    
    print("")
    print("=" * 50)
    print("  CREDENCIALES DE ACCESO")
    print("=" * 50)
    print(f"  📧 Email:      {admin_email}")
    print(f"  🔑 Contraseña: {admin_password}")
    print("=" * 50)
    print("")
    print("⚠️  IMPORTANTE: Cambia la contraseña después del primer login")
    print("")

def create_sample_data():
    """Crear datos de ejemplo (opcional)"""
    
    response = input("¿Deseas crear leads de ejemplo? (s/n): ").strip().lower()
    
    if response != 's':
        return
    
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Verificar si ya hay leads
    if db.leads.count_documents({}) > 0:
        print("⚠️  Ya existen leads en la base de datos. No se crearán ejemplos.")
        return
    
    sample_leads = [
        {
            "phone": "+5491155551234",
            "name": "María García (Ejemplo)",
            "intent": "comprar",
            "zone": "Palermo",
            "budget_text": "USD 150.000 - 200.000",
            "score": 9,
            "status": "hot",
            "flow_stage": "welcome",
            "source": "whatsapp",
            "created_at": datetime.now(timezone.utc),
            "last_message_at": datetime.now(timezone.utc),
            "tags": ["ejemplo", "comprador"],
            "conversation_history": []
        },
        {
            "phone": "+5491166662345",
            "name": "Carlos López (Ejemplo)",
            "intent": "alquilar",
            "zone": "Belgrano",
            "budget_text": "ARS 500.000/mes",
            "score": 6,
            "status": "warm",
            "flow_stage": "welcome",
            "source": "whatsapp",
            "created_at": datetime.now(timezone.utc),
            "last_message_at": datetime.now(timezone.utc),
            "tags": ["ejemplo", "alquiler"],
            "conversation_history": []
        }
    ]
    
    db.leads.insert_many(sample_leads)
    print(f"✅ Se crearon {len(sample_leads)} leads de ejemplo")

if __name__ == '__main__':
    print("")
    print("=" * 50)
    print("  INMOBOT - Script de Inicialización")
    print("=" * 50)
    print("")
    
    create_admin()
    create_sample_data()
    
    print("🎉 Inicialización completada!")
    print("")
