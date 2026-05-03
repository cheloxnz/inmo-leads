"""One-shot seed for two demo leads needed by iter45 frontend testing.
Carlos Test: last message from customer (UI should show suggestions card).
Maria Test:  last message from agent  (UI should NOT show suggestions card).
Idempotent: upserts by (tenant_id, phone).
"""
from dotenv import load_dotenv
load_dotenv()
import asyncio, os, uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

TENANT = "demo-inmobiliaria"

def now_iso(offset_min=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_min)).isoformat()

CARLOS = {
    "tenant_id": TENANT,
    "phone": "5491100000001",
    "name": "Carlos Test",
    "status": "warm",
    "score": 6,
    "last_message_at": now_iso(0),
    "conversation_history": [
        {"from": "customer", "text": "Hola! Vi un depto en Palermo, sigue disponible?", "timestamp": now_iso(-30)},
        {"from": "agent",    "text": "Si Carlos, todavía está disponible. ¿Querés que te pase los detalles?", "timestamp": now_iso(-25)},
        {"from": "customer", "text": "Cuanto vale rentar el inmueble en Palermo?", "timestamp": now_iso(-1)},
    ],
}

MARIA = {
    "tenant_id": TENANT,
    "phone": "5491100000002",
    "name": "Maria Test",
    "status": "warm",
    "score": 5,
    "last_message_at": now_iso(0),
    "conversation_history": [
        {"from": "customer", "text": "Hola, hay disponibilidad para el sábado?", "timestamp": now_iso(-20)},
        {"from": "agent",    "text": "Hola Maria, sí tenemos disponibilidad. ¿A qué hora preferís?", "timestamp": now_iso(-1)},
    ],
}


async def upsert(db, lead):
    lead = {**lead}
    if "id" not in lead:
        lead["id"] = str(uuid.uuid4())
    await db.leads.update_one(
        {"tenant_id": lead["tenant_id"], "phone": lead["phone"]},
        {"$set": lead, "$setOnInsert": {"created_at": now_iso(0)}},
        upsert=True,
    )


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    await upsert(db, CARLOS)
    await upsert(db, MARIA)
    cnt = await db.leads.count_documents({"tenant_id": TENANT})
    print(f"demo-inmobiliaria leads now: {cnt}")


if __name__ == "__main__":
    asyncio.run(main())
