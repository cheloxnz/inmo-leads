"""
Demo Data Seeder
================

Genera datos ficticios pero verosímiles (productos + waitlist + leads opcionales)
para un tenant. Útil para demos comerciales en vivo: en 5 segundos el dashboard
muestra métricas creíbles.

Datasets diferenciados por `tenant.template_id` (inmobiliaria, restaurante,
ecommerce, clinica, servicios) con un fallback genérico.

Idempotencia: si el tenant ya tiene productos, requiere `force=True` para
agregar más (no borra los existentes — para eso usar `reset_demo_data` antes).
"""
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# Datasets de demo por vertical
DEMO_DATASETS: Dict[str, List[Dict]] = {
    "inmobiliaria": [
        {"name": "Departamento 2 amb. Palermo", "price": 145000, "stock": 0},
        {"name": "Casa 3 dorm. La Lucila", "price": 320000, "stock": 0},
        {"name": "PH 1 dorm. Caballito", "price": 89000, "stock": 1},
        {"name": "Departamento 3 amb. Belgrano", "price": 198000, "stock": 0},
        {"name": "Local comercial Av. Cabildo", "price": 240000, "stock": 1},
        {"name": "Loft Puerto Madero", "price": 380000, "stock": 0},
        {"name": "Casa quinta Pilar", "price": 290000, "stock": 2},
        {"name": "Monoambiente Recoleta", "price": 78000, "stock": 0},
        {"name": "Duplex 4 amb. San Isidro", "price": 410000, "stock": 0},
        {"name": "PH 2 amb. Villa Crespo", "price": 115000, "stock": 1},
        {"name": "Oficina céntrica 80m²", "price": 165000, "stock": 0},
        {"name": "Departamento 1 amb. Almagro", "price": 65000, "stock": 3},
    ],
    "ecommerce": [
        {"name": "iPhone 15 Pro 256GB", "price": 1399, "stock": 0},
        {"name": "AirPods Pro 2da Gen", "price": 249, "stock": 0},
        {"name": "MacBook Air M3 13''", "price": 1299, "stock": 0},
        {"name": "iPad Air M2 11''", "price": 599, "stock": 1},
        {"name": "Apple Watch Series 10", "price": 399, "stock": 0},
        {"name": "Samsung Galaxy S24 Ultra", "price": 1299, "stock": 0},
        {"name": "Sony WH-1000XM5", "price": 399, "stock": 2},
        {"name": "Dyson V15 Detect", "price": 749, "stock": 0},
        {"name": "Nintendo Switch OLED", "price": 349, "stock": 0},
        {"name": "Samsung 4K 65''", "price": 1199, "stock": 1},
        {"name": "PS5 Slim Digital", "price": 449, "stock": 0},
        {"name": "Kindle Paperwhite", "price": 159, "stock": 5},
    ],
    "restaurante": [
        {"name": "Reserva Sábado 21hs (4 pax)", "price": 80, "stock": 0},
        {"name": "Menú degustación maridaje", "price": 120, "stock": 0},
        {"name": "Cumpleaños privado salón", "price": 450, "stock": 0},
        {"name": "Reserva Viernes 22hs (2 pax)", "price": 60, "stock": 0},
        {"name": "Brunch Domingo 11hs", "price": 35, "stock": 1},
        {"name": "Cena romántica San Valentín", "price": 180, "stock": 0},
        {"name": "Catering corporativo (20 pax)", "price": 800, "stock": 1},
        {"name": "Mesa terraza Sábado almuerzo", "price": 50, "stock": 0},
    ],
    "clinica": [
        {"name": "Turno Cardiología (Dr. López)", "price": 80, "stock": 0},
        {"name": "Turno Dermatología (Dra. Pérez)", "price": 90, "stock": 0},
        {"name": "Estudio ergometría", "price": 150, "stock": 0},
        {"name": "Resonancia magnética", "price": 250, "stock": 1},
        {"name": "Análisis sangre completo", "price": 60, "stock": 0},
        {"name": "Consulta nutricionista", "price": 70, "stock": 0},
        {"name": "Sesión kinesiología", "price": 50, "stock": 2},
        {"name": "Vacuna antigripal", "price": 25, "stock": 0},
    ],
    "servicios": [
        {"name": "Plomería emergencia 24hs", "price": 80, "stock": 0},
        {"name": "Electricidad domiciliaria", "price": 60, "stock": 0},
        {"name": "Service heladera", "price": 90, "stock": 1},
        {"name": "Pintura monoambiente", "price": 350, "stock": 0},
        {"name": "Cerrajería urgencia", "price": 70, "stock": 0},
        {"name": "Limpieza profunda casa", "price": 120, "stock": 0},
        {"name": "Mudanza local 2 ambientes", "price": 280, "stock": 1},
        {"name": "Jardinería mantenimiento mensual", "price": 150, "stock": 2},
    ],
}

# Nombres y phones de leads ficticios (para waitlist + leads opcionales)
DEMO_LEADS = [
    {"name": "María González", "phone": "5491112340001"},
    {"name": "Juan Rodríguez", "phone": "5491112340002"},
    {"name": "Lucía Fernández", "phone": "5491112340003"},
    {"name": "Carlos Martínez", "phone": "5491112340004"},
    {"name": "Ana Suárez", "phone": "5491112340005"},
    {"name": "Diego Pérez", "phone": "5491112340006"},
    {"name": "Sofía Ramírez", "phone": "5491112340007"},
    {"name": "Federico López", "phone": "5491112340008"},
    {"name": "Valentina Torres", "phone": "5491112340009"},
    {"name": "Matías Romero", "phone": "5491112340010"},
    {"name": "Camila Acosta", "phone": "5491112340011"},
    {"name": "Nicolás Silva", "phone": "5491112340012"},
    {"name": "Florencia Díaz", "phone": "5491112340013"},
    {"name": "Tomás Castro", "phone": "5491112340014"},
    {"name": "Julieta Méndez", "phone": "5491112340015"},
    {"name": "Lautaro Vega", "phone": "5491112340016"},
    {"name": "Antonella Ruiz", "phone": "5491112340017"},
    {"name": "Bruno Herrera", "phone": "5491112340018"},
    {"name": "Mía Aguirre", "phone": "5491112340019"},
    {"name": "Joaquín Núñez", "phone": "5491112340020"},
    {"name": "Renata Ortiz", "phone": "5491112340021"},
    {"name": "Benjamín Cabrera", "phone": "5491112340022"},
    {"name": "Catalina Reyes", "phone": "5491112340023"},
    {"name": "Iván Ojeda", "phone": "5491112340024"},
]


def _pick_dataset(template_id: str) -> List[Dict]:
    """Devuelve dataset según template; fallback a `servicios`."""
    return DEMO_DATASETS.get(template_id) or DEMO_DATASETS["servicios"]


async def seed_demo_data(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    products_count: int = 12,
    waitlist_per_product: int = 5,
    include_leads: bool = False,
    force: bool = False,
) -> Dict:
    """Genera productos + waitlist (+ leads) para `tenant_id`.

    - Si `tenant_id` no existe → KeyError-like (caller convierte a 404).
    - Si ya tiene productos y `force=False` → retorna sin tocar nada.
    - Si `force=True` → agrega productos adicionales.
    - `waitlist_per_product` se usa solo para los productos sin stock (los
      "agotados") para que la métrica de demanda insatisfecha tenga sentido.
    - `include_leads=True` también crea leads + 1 conversación + mensajes
      sintéticos por cada lead (útil para llenar el dashboard de leads).
    """
    tenant = await db.tenants.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "tenant_id": 1, "template_id": 1, "name": 1},
    )
    if not tenant:
        return {"error": "tenant_not_found", "tenant_id": tenant_id}

    existing = await db.products.count_documents({"tenant_id": tenant_id})
    if existing > 0 and not force:
        return {
            "tenant_id": tenant_id,
            "skipped": True,
            "reason": f"tenant ya tiene {existing} productos. Pasá force=true para agregar más.",
            "existing_products": existing,
        }

    template_id = tenant.get("template_id") or "servicios"
    dataset = _pick_dataset(template_id)
    sample = dataset[: max(1, min(products_count, len(dataset)))]

    now = datetime.now(timezone.utc)
    inserted_products: List[str] = []

    for item in sample:
        pid = f"demo_{uuid.uuid4().hex[:10]}"
        await db.products.insert_one({
            "tenant_id": tenant_id,
            "product_id": pid,
            "name": item["name"],
            "price": item["price"],
            "currency": "USD",
            "stock_quantity": item["stock"],
            "active": True,
            "category": "demo",
            "description": "Producto de demostración generado automáticamente.",
            "created_at": now.isoformat(),
            "is_demo": True,
        })
        inserted_products.append(pid)

    # Waitlist: solo para productos con stock 0 (agotados)
    waitlist_inserted = 0
    out_of_stock_items = [
        (pid, item) for pid, item in zip(inserted_products, sample) if item["stock"] == 0
    ]
    for pid, item in out_of_stock_items:
        # waitlist_per_product leads ficticios distintos por producto
        leads_for_this = random.sample(
            DEMO_LEADS, k=min(waitlist_per_product, len(DEMO_LEADS))
        )
        for ld in leads_for_this:
            asked_at = now - timedelta(hours=random.randint(2, 168))
            await db.product_waitlist.insert_one({
                "tenant_id": tenant_id,
                "lead_phone": ld["phone"],
                "product_id": pid,
                "product_name": item["name"],
                "asked_at": asked_at.isoformat(),
                "notified_at": None,
                "created_at": asked_at.isoformat(),
                "is_demo": True,
            })
            waitlist_inserted += 1

    leads_inserted = 0
    convs_inserted = 0
    msgs_inserted = 0
    if include_leads:
        for ld in DEMO_LEADS[: min(20, len(DEMO_LEADS))]:
            lead_id = f"demo_lead_{uuid.uuid4().hex[:10]}"
            score = random.choice([2, 3, 4, 5, 7, 8, 9, 10, 11, 12])
            status = "hot" if score >= 9 else ("warm" if score >= 5 else "cold")
            created_at = now - timedelta(hours=random.randint(1, 240))
            await db.leads.insert_one({
                "tenant_id": tenant_id,
                "lead_id": lead_id,
                "name": ld["name"],
                "phone": ld["phone"],
                "score": score,
                "status": status,
                "tag": random.choice(["interesado", "frio", "caliente", "consulta", ""]),
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
                "is_demo": True,
            })
            leads_inserted += 1

            conv_id = f"demo_conv_{uuid.uuid4().hex[:10]}"
            await db.conversations.insert_one({
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "lead_phone": ld["phone"],
                "lead_name": ld["name"],
                "started_at": created_at.isoformat(),
                "is_demo": True,
            })
            convs_inserted += 1

            # 2-4 mensajes por conversación
            for i in range(random.randint(2, 4)):
                msg_at = created_at + timedelta(minutes=i * 3)
                await db.messages.insert_one({
                    "tenant_id": tenant_id,
                    "conversation_id": conv_id,
                    "lead_phone": ld["phone"],
                    "direction": "in" if i % 2 == 0 else "out",
                    "content": f"[demo msg {i + 1}]",
                    "timestamp": msg_at.isoformat(),
                    "is_demo": True,
                })
                msgs_inserted += 1

    logger.info(
        f"[seed_demo] tenant={tenant_id} template={template_id} "
        f"products={len(inserted_products)} waitlist={waitlist_inserted} "
        f"leads={leads_inserted}"
    )

    return {
        "tenant_id": tenant_id,
        "template_used": template_id,
        "products_inserted": len(inserted_products),
        "waitlist_inserted": waitlist_inserted,
        "leads_inserted": leads_inserted,
        "conversations_inserted": convs_inserted,
        "messages_inserted": msgs_inserted,
        "skipped": False,
    }
