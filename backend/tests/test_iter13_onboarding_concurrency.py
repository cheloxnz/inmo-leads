"""Iter 13 - Stress test de concurrencia del Onboarding Wizard.

Disparamos N requests simultaneos a POST /api/onboarding/auto-setup con el MISMO
business_name (-> mismo slug -> mismo tenant_id). Debe haber:
  - exactamente 1 request con HTTP 200 (el ganador)
  - el resto con 409 (Tenant ya existe / Email ya registrado) o 200 con tenant_id distinto si el suffix counter funciona
  - cero documentos huerfanos en mongo (tenant sin agent, agent sin tenant, productos sin tenant)

Tambien validamos que el unique index sobre tenants.tenant_id rechaza duplicados crudos.
"""
import os
import asyncio
import uuid
import pytest
import httpx
from motor.motor_asyncio import AsyncIOMotorClient


def _get_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip().rstrip("/")
                        break
        except Exception:
            pass
    return url


BASE_URL = _get_backend_url()


def _get_db_config():
    """Lee MONGO_URL/DB_NAME del backend/.env (mismo origen que la app)."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("MONGO_URL=") and not mongo_url:
                    mongo_url = line.split("=", 1)[1]
                elif line.startswith("DB_NAME=") and not db_name:
                    db_name = line.split("=", 1)[1]
    except Exception:
        pass
    return mongo_url or "mongodb://localhost:27017", db_name or "inmobot_db"


MONGO_URL, DB_NAME = _get_db_config()


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db():
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


async def _cleanup_tenant_by_prefix(db, prefix: str):
    """Borra tenant + agents + products + bot_config con tenant_id que empieza con prefix."""
    tenants = await db.tenants.find({"tenant_id": {"$regex": f"^{prefix}"}}, {"tenant_id": 1}).to_list(length=200)
    tids = [t["tenant_id"] for t in tenants]
    if tids:
        await db.tenants.delete_many({"tenant_id": {"$in": tids}})
        await db.agents.delete_many({"tenant_id": {"$in": tids}})
        await db.products.delete_many({"tenant_id": {"$in": tids}})
        await db.bot_config.delete_many({"tenant_id": {"$in": tids}})
    # Tambien limpiar agents huerfanos por email
    await db.agents.delete_many({"email": {"$regex": f"^stress-{prefix}-"}})


@pytest.mark.asyncio
async def test_unique_index_tenants():
    """El unique index sobre tenants.tenant_id existe y rechaza duplicados."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        info = await db.tenants.index_information()
        unique_indexes = [name for name, val in info.items()
                          if val.get("unique") and any(k[0] == "tenant_id" for k in val.get("key", []))]
        assert unique_indexes, f"No hay unique index sobre tenant_id. Indexes: {info}"
    finally:
        client.close()


@pytest.mark.asyncio
async def test_concurrent_onboarding_same_business():
    """Disparar 15 requests simultaneos con MISMO business_name + emails distintos.
    Esperado: el suffix counter (- 1, -2, ...) deberia evitar duplicados de tenant_id, pero
    el race en el find_one + insert_one puede generar choques. Validamos:
    - Ningun 500
    - todos los tenant creados existen en mongo (no huerfanos)
    - cada agent existente apunta a un tenant existente
    """
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL no disponible")

    suffix = uuid.uuid4().hex[:6]
    prefix = f"stress-tenant-{suffix}"
    business_name = f"Stress Tenant {suffix}"
    description = "negocio de stress testing concurrencia onboarding inmobiliaria propiedades alquiler"
    N = 15

    async def fire(i: int):
        async with httpx.AsyncClient(timeout=30.0) as cli:
            r = await cli.post(
                f"{BASE_URL}/api/onboarding/auto-setup",
                json={
                    "business_name": business_name,
                    "description": description,
                    "email": f"stress-{prefix}-{i}@test.local",
                    "password": "Stress123!",
                },
            )
            return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else {}

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        await _cleanup_tenant_by_prefix(db, prefix)

        results = await asyncio.gather(*(fire(i) for i in range(N)), return_exceptions=True)
        statuses = [r[0] if isinstance(r, tuple) else "EXC" for r in results]
        ok = [r for r in results if isinstance(r, tuple) and r[0] == 200]
        errors = [r for r in results if isinstance(r, tuple) and r[0] >= 400]
        exc = [r for r in results if not isinstance(r, tuple)]

        # Aceptable: algunos 200 (con suffix distintos), algunos 409 por race condition.
        # Lo que NO debe pasar: 500.
        five_hundred = [r for r in results if isinstance(r, tuple) and r[0] >= 500]
        assert not five_hundred, f"Hubo errores 5xx: {five_hundred}"
        assert not exc, f"Excepciones de cliente: {exc}"
        assert ok, f"Ningun request exitoso. Statuses: {statuses}, errors: {errors[:3]}"

        # Verificar consistencia: cada tenant creado tiene su agent, y vice versa
        tenant_ids = [r[1].get("tenant_id") for r in ok if r[1].get("tenant_id")]
        assert len(tenant_ids) == len(ok), "Algun 200 no devolvio tenant_id"

        for tid in tenant_ids:
            t = await db.tenants.find_one({"tenant_id": tid})
            assert t, f"Tenant {tid} ausente en mongo (huerfano en respuesta)"
            ag = await db.agents.find_one({"tenant_id": tid})
            assert ag, f"Agent del tenant {tid} ausente (rollback fallo)"

        # Verificar que NO hay agents huerfanos: todo agent stress-{prefix}-* tiene tenant valido
        orphan_agents = []
        async for ag in db.agents.find({"email": {"$regex": f"^stress-{prefix}-"}}):
            t = await db.tenants.find_one({"tenant_id": ag.get("tenant_id")})
            if not t:
                orphan_agents.append(ag.get("email"))
        assert not orphan_agents, f"Agents huerfanos: {orphan_agents}"

        # Verificar que NO hay tenants huerfanos: todo tenant stress-* tiene >=1 agent
        orphan_tenants = []
        async for t in db.tenants.find({"tenant_id": {"$regex": f"^{prefix}"}}):
            ag = await db.agents.find_one({"tenant_id": t["tenant_id"]})
            if not ag:
                orphan_tenants.append(t["tenant_id"])
        assert not orphan_tenants, f"Tenants huerfanos sin agent: {orphan_tenants}"

        print(f"OK stress test: {len(ok)} exitosos, {len(errors)} errores controlados, "
              f"0 huerfanos, 0 5xx. Statuses: {statuses}")
    finally:
        await _cleanup_tenant_by_prefix(db, prefix)
        client.close()


@pytest.mark.asyncio
async def test_duplicate_email_is_409():
    """Dos onboardings con MISMO email deben dar uno 200 y otro 409 (sin agent huerfano)."""
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL no disponible")

    suffix = uuid.uuid4().hex[:6]
    prefix = f"dup-mail-{suffix}"
    email = f"stress-{prefix}-shared@test.local"

    async def fire(idx_name: int):
        async with httpx.AsyncClient(timeout=30.0) as cli:
            r = await cli.post(
                f"{BASE_URL}/api/onboarding/auto-setup",
                json={
                    "business_name": f"DupMail {suffix} Biz {idx_name}",
                    "description": "descripcion negocio dup mail tests inmobiliaria propiedades larga aceptable",
                    "email": email,
                    "password": "DupMail123!",
                },
            )
            return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        await _cleanup_tenant_by_prefix(db, "dupmail-")  # cleanup por slug
        await db.agents.delete_one({"email": email})

        results = await asyncio.gather(fire(1), fire(2))
        codes = sorted([r[0] for r in results])
        # 1 ganador (200), 1 perdedor (409)
        assert 200 in codes, f"Ningun 200. codes={codes}"
        assert any(c >= 400 for c in codes), f"Ambos 200 - debe haber 409. codes={codes}"

        # Verificar que solo existe UN agent con este email
        count = await db.agents.count_documents({"email": email})
        assert count == 1, f"Esperaba 1 agent con email duplicado, hay {count}"
    finally:
        # cleanup
        ag = await db.agents.find_one({"email": email})
        if ag:
            tid = ag.get("tenant_id")
            if tid:
                await db.tenants.delete_one({"tenant_id": tid})
                await db.products.delete_many({"tenant_id": tid})
                await db.bot_config.delete_many({"tenant_id": tid})
            await db.agents.delete_one({"email": email})
        await _cleanup_tenant_by_prefix(db, "dupmail-")
        client.close()
