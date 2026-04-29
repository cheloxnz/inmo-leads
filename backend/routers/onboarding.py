"""Router de auto-onboarding: crea tenant + usuario + landing + catalogo demo desde una descripcion."""
import re
import unicodedata
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth_routes import get_db
from auth import get_password_hash, create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["onboarding"])


def slugify(text: str, max_len: int = 40) -> str:
    """Convierte texto a slug (lowercase, alfanumerico + dashes)."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug[:max_len]


# Templates de catalogo demo por rubro
DEMO_PRODUCTS = {
    "inmobiliaria": [
        {"name": "Departamento 2 ambientes", "category": "Departamentos", "price": 120000, "currency": "USD", "description": "Luminoso, balcón, próximo al subte."},
        {"name": "Casa con jardín", "category": "Casas", "price": 220000, "currency": "USD", "description": "3 dormitorios, jardín, parrilla."},
        {"name": "PH 3 ambientes", "category": "PH", "price": 180000, "currency": "USD", "description": "Sin expensas, terraza propia."},
    ],
    "clinica": [
        {"name": "Consulta general", "category": "Consultas", "price": 8000, "currency": "ARS", "description": "Primera consulta clínica."},
        {"name": "Limpieza dental", "category": "Odontología", "price": 12000, "currency": "ARS", "description": "Limpieza completa con detartraje."},
        {"name": "Implante dental", "category": "Odontología", "price": 180000, "currency": "ARS", "description": "Implante de titanio + corona."},
    ],
    "restaurante": [
        {"name": "Menú del día", "category": "Almuerzos", "price": 4500, "currency": "ARS", "description": "Plato principal + bebida + postre."},
        {"name": "Pizza muzarella", "category": "Pizzas", "price": 6500, "currency": "ARS", "description": "Pizza grande, masa madre."},
        {"name": "Hamburguesa clásica", "category": "Hamburguesas", "price": 5500, "currency": "ARS", "description": "Smash, cheddar, tocino."},
    ],
    "ecommerce": [
        {"name": "Producto destacado A", "category": "Destacados", "price": 9999, "currency": "ARS", "description": "Reemplazá esta descripción con tu producto real."},
        {"name": "Producto destacado B", "category": "Destacados", "price": 14999, "currency": "ARS", "description": "Editá precio y detalles desde el dashboard."},
        {"name": "Combo promocional", "category": "Promos", "price": 19999, "currency": "ARS", "description": "Combina varios productos."},
    ],
    "servicios": [
        {"name": "Servicio básico", "category": "Servicios", "price": 0, "currency": "USD", "description": "Editá nombre, precio y descripción desde el dashboard."},
        {"name": "Servicio premium", "category": "Servicios", "price": 0, "currency": "USD", "description": "Personalizá según tu rubro."},
        {"name": "Consultoría", "category": "Asesoría", "price": 0, "currency": "USD", "description": "Una hora de asesoría profesional."},
    ],
}


@router.post("/onboarding/suggest-tenant-id")
async def suggest_tenant_id(
    body: dict,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Genera un tenant_id sugerido a partir del business_name. Verifica disponibilidad."""
    name = (body or {}).get("business_name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="business_name requerido")
    base = slugify(name) or "negocio"
    candidate = base
    suffix = 0
    while await db.tenants.find_one({"tenant_id": candidate}, {"_id": 1}):
        suffix += 1
        candidate = f"{base}-{suffix}"
        if suffix > 50:
            from secrets import token_hex
            candidate = f"{base}-{token_hex(3)}"
            break
    return {"tenant_id": candidate, "available": True}


@router.post("/onboarding/auto-setup")
async def auto_setup_tenant(
    body: dict,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Crea un tenant completo a partir de una descripcion del negocio:
    1. Genera tenant_id desde business_name
    2. Detecta template_id desde la descripcion (palabras clave)
    3. Crea tenant en MongoDB
    4. Crea usuario admin (password temp generada)
    5. Llama IA para generar tagline + features + steps
    6. Inserta 3 productos demo del rubro
    7. Devuelve credenciales + token JWT para auto-login
    """
    business_name = (body or {}).get("business_name", "").strip()
    description = (body or {}).get("description", "").strip()
    email = (body or {}).get("email", "").strip().lower()
    password = (body or {}).get("password", "").strip()
    template_hint = (body or {}).get("template_id", "").strip()
    ref_tenant_id = (body or {}).get("ref", "").strip()[:60] or None
    ref_celebration_id = (body or {}).get("ref_celebration_id", "").strip()[:60] or None

    if not business_name or not description or not email or not password:
        raise HTTPException(status_code=400, detail="business_name, description, email y password son requeridos")
    if len(description) < 20:
        raise HTTPException(status_code=400, detail="description minimo 20 caracteres")
    if len(description) > 500:
        raise HTTPException(status_code=400, detail="description demasiado larga (>500 chars)")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="password minimo 8 caracteres")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="email invalido")

    # 1. Slug
    base = slugify(business_name) or "negocio"
    tenant_id = base
    suffix = 0
    while await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 1}):
        suffix += 1
        tenant_id = f"{base}-{suffix}"
        if suffix > 50:
            from secrets import token_hex
            tenant_id = f"{base}-{token_hex(3)}"
            break

    # 2. Detectar template desde descripcion
    desc_lower = description.lower()
    keywords = {
        "inmobiliaria": ["inmobiliaria", "propiedad", "alquiler", "departamento", "casa", "venta", "bien raiz"],
        "clinica": ["clinica", "salud", "consultorio", "odontologia", "medico", "doctora", "doctor", "dentista", "kinesio", "psicolog", "tratamiento"],
        "restaurante": ["restaurante", "restaurant", "bar", "cafeteria", "menu", "delivery", "comida", "pizza", "gastronom"],
        "ecommerce": ["ecommerce", "tienda", "venta online", "productos", "envios", "ropa", "moda", "indumentaria"],
    }
    detected = "servicios"
    if template_hint and template_hint in DEMO_PRODUCTS:
        detected = template_hint
    else:
        for tpl, kws in keywords.items():
            if any(kw in desc_lower for kw in kws):
                detected = tpl
                break

    # 3. Email duplicado check
    existing_user = await db.agents.find_one({"email": email}, {"_id": 1})
    if existing_user:
        raise HTTPException(status_code=409, detail="Email ya registrado")

    # 4. Crear tenant + agent + productos con rollback ante fallos
    from pymongo.errors import DuplicateKeyError
    now_iso = datetime.now(timezone.utc).isoformat()
    tenant_doc = {
        "tenant_id": tenant_id,
        "name": business_name,
        "business_name": business_name,
        "business_tagline": "",
        "template_id": detected,
        "active": True,
        "subscription_plan": "trial",
        "subscription_status": "trialing",
        "max_leads": 100,
        "max_ai_messages": 200,
        "primary_color": "#3b82f6",
        "accent_color": "#8b5cf6",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    # Referral attribution: persistir SOLO si el ref_tenant_id existe en la DB y NO es auto-referido
    referrer_ip = (request.client.host if request and request.client else None)
    fraud_reason = None
    if ref_tenant_id:
        ref_exists = await db.tenants.find_one(
            {"tenant_id": ref_tenant_id, "active": True}, {"_id": 1}
        )
        if ref_exists:
            from commission_service import is_self_referral
            is_fraud, fraud_reason = await is_self_referral(
                db, ref_tenant_id, email, referrer_ip
            )
            if not is_fraud:
                tenant_doc["referred_by"] = ref_tenant_id
                if ref_celebration_id:
                    tenant_doc["referred_via_celebration"] = ref_celebration_id
            else:
                logger.info(
                    f"Anti-fraud: ref={ref_tenant_id} descartado para {email}. "
                    f"Reason={fraud_reason}"
                )

    # 5. Llamar IA para tagline + features + steps (mejor effort)
    try:
        from llm_service import create_llm_for_tenant
        llm = create_llm_for_tenant(tenant_doc)
        copy = await llm.generate_landing_copy(description)
        tenant_doc["business_tagline"] = copy.get("business_tagline") or "Atencion 24/7 con IA"
        if copy.get("features"):
            tenant_doc["custom_features"] = copy["features"]
        if copy.get("steps"):
            tenant_doc["custom_steps"] = copy["steps"]
        ai_used = copy.get("ai_enabled", False)
    except Exception:
        tenant_doc["business_tagline"] = "Atencion 24/7 con IA"
        ai_used = False

    # 6. INSERT tenant (atrapando race condition con index unique)
    try:
        await db.tenants.insert_one(tenant_doc)
    except DuplicateKeyError:
        # Race condition: otro request creo el tenant mientras procesabamos
        raise HTTPException(status_code=409, detail="Tenant ya existe (intentar de nuevo)")

    # 7. INSERT agent. Si falla, rollback del tenant.
    user_doc = {
        "email": email,
        "password_hash": get_password_hash(password),
        "name": business_name,
        "phone": "",
        "role": "admin",
        "active": True,
        "tenant_id": tenant_id,
        "created_at": now_iso,
    }
    try:
        await db.agents.insert_one(user_doc)
    except DuplicateKeyError:
        # Rollback tenant
        await db.tenants.delete_one({"tenant_id": tenant_id})
        raise HTTPException(status_code=409, detail="Email ya registrado")
    except Exception as e:
        await db.tenants.delete_one({"tenant_id": tenant_id})
        raise HTTPException(status_code=500, detail=f"Error creando usuario: {e}")

    # 8. INSERT productos demo. Si falla, rollback tenant + agent.
    import uuid
    demo = DEMO_PRODUCTS.get(detected, DEMO_PRODUCTS["servicios"])
    products_to_insert = []
    for p in demo:
        products_to_insert.append({
            "product_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "active": True,
            "created_at": now_iso,
            "image_url": "",
            **p,
        })
    if products_to_insert:
        try:
            await db.products.insert_many(products_to_insert)
        except Exception as e:
            # Rollback agent + tenant (productos no son criticos pero mantenemos consistencia)
            logger.warning(f"Falla seed productos, rollback completo: {e}")
            await db.products.delete_many({"tenant_id": tenant_id})
            await db.agents.delete_one({"email": email})
            await db.tenants.delete_one({"tenant_id": tenant_id})
            raise HTTPException(status_code=500, detail="Error inicializando catalogo demo")

    # 9. Token JWT para auto-login
    token = create_access_token({
        "sub": email,
        "tenant_id": tenant_id,
        "role": "admin",
    })

    # 10. Si vino con ref, marcar referral_lead como convertido + bump counter del referrer
    if tenant_doc.get("referred_by"):
        try:
            await db.referral_leads.update_many(
                {"ref_tenant_id": tenant_doc["referred_by"], "email": email,
                 "converted_tenant_id": None},
                {"$set": {
                    "converted_tenant_id": tenant_id,
                    "converted_at": datetime.now(timezone.utc),
                }},
            )
            await db.tenants.update_one(
                {"tenant_id": tenant_doc["referred_by"]},
                {"$inc": {"referral_stats.signups": 1}},
            )
            # Crear commission en estado PENDING (se activara cuando pague la 1ra factura)
            from commission_service import COMMISSION_AMOUNT_USD, COMMISSION_DURATION_DAYS
            from datetime import timedelta as _td
            now = datetime.now(timezone.utc)
            await db.commissions.update_one(
                {
                    "referrer_tenant_id": tenant_doc["referred_by"],
                    "referred_tenant_id": tenant_id,
                },
                {"$setOnInsert": {
                    "commission_id": __import__("uuid").uuid4().hex,
                    "referrer_tenant_id": tenant_doc["referred_by"],
                    "referred_tenant_id": tenant_id,
                    "referred_via_celebration": tenant_doc.get("referred_via_celebration"),
                    "amount_per_month_usd": COMMISSION_AMOUNT_USD,
                    "status": "pending",
                    "created_at": now,
                    "expires_at": now + _td(days=COMMISSION_DURATION_DAYS),
                    "total_credited_usd": 0.0,
                    "applied_invoices": [],
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"referral conversion tracking fallo: {e}")

    # Audit log con IP del signup (para anti-fraude cross-tenant futuro)
    try:
        await db.audit_log.insert_one({
            "tenant_id": tenant_id,
            "action": "tenant_signup",
            "ip": referrer_ip,
            "user_agent": (request.headers.get("user-agent") or "")[:300] if request else "",
            "ref_tenant_id": ref_tenant_id or None,
            "fraud_blocked_reason": fraud_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {
        "tenant_id": tenant_id,
        "template_id": detected,
        "ai_enabled": ai_used,
        "products_seeded": len(products_to_insert),
        "access_token": token,
        "user": {"email": email, "name": business_name, "role": "admin", "tenant_id": tenant_id},
        "landing_url": f"/inicio/{tenant_id}",
        "next_step": "/dashboard",
    }
