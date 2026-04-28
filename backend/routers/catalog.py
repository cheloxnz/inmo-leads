"""Router de catalogo de productos por tenant"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import get_current_user, require_admin, get_db
from catalog_service import CatalogService
from whatsapp_service import create_wa_service_for_tenant
from llm_service import create_llm_for_tenant
from models import User

router = APIRouter(tags=["catalog"])

_db = get_db()
catalog_service = CatalogService(_db)


@router.get("/catalog")
async def get_catalog(category: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """Obtiene productos del catalogo del tenant"""
    return await catalog_service.get_products(current_user.tenant_id, category=category)


@router.get("/catalog/categories")
async def get_catalog_categories(current_user: User = Depends(get_current_user)):
    """Obtiene categorias del catalogo"""
    return await catalog_service.get_categories(current_user.tenant_id)


@router.post("/catalog")
async def create_product(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Crea un producto en el catalogo"""
    return await catalog_service.create_product(current_user.tenant_id, body)


@router.put("/catalog/{product_id}")
async def update_product(product_id: str, body: dict, current_user: User = Depends(require_admin)):
    """Admin: Actualiza un producto por product_id"""
    success = await catalog_service.update_product(current_user.tenant_id, product_id, body)
    if not success:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"message": "Producto actualizado"}


@router.delete("/catalog/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(require_admin)):
    """Admin: Elimina un producto del catalogo por product_id"""
    success = await catalog_service.delete_product(current_user.tenant_id, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"message": "Producto eliminado"}


@router.post("/catalog/send/{phone}")
async def send_catalog_to_lead(phone: str, body: dict, current_user: User = Depends(get_current_user)):
    """Envia catalogo o producto a un lead por WhatsApp.

    Valida que el telefono pertenezca al tenant del usuario antes de enviar.
    """
    category = body.get("category")
    product_id = body.get("product_id") or body.get("product_name")  # backward compat

    # Cross-tenant validation
    lead = await _db.leads.find_one(
        {"phone": phone, "tenant_id": current_user.tenant_id},
        {"_id": 0, "phone": 1}
    )
    other_tenant_lead = await _db.leads.find_one(
        {"phone": phone, "tenant_id": {"$ne": current_user.tenant_id}},
        {"_id": 0, "phone": 1}
    )
    if other_tenant_lead and not lead:
        raise HTTPException(status_code=403, detail="Este telefono no pertenece a tu tenant")

    tenant = await _db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    active_wa = create_wa_service_for_tenant(_db, tenant)

    if product_id:
        product = await catalog_service.get_product_by_id(current_user.tenant_id, product_id)
        if not product:
            products = await catalog_service.get_products(current_user.tenant_id)
            product = next((p for p in products if p["name"] == product_id), None)
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        msg = catalog_service.build_single_product_message(product)
        result = active_wa.send_text_message(phone, msg)
    else:
        products = await catalog_service.get_products(current_user.tenant_id, category=category)
        if not products:
            raise HTTPException(status_code=404, detail="No hay productos en el catalogo")

        if len(products) <= 3:
            body_text, buttons = catalog_service.build_carousel_buttons(products)
            result = active_wa.send_interactive_buttons(phone, body_text, buttons)
        else:
            list_data = catalog_service.build_product_list_message(products)
            result = active_wa.send_list_message(
                phone,
                list_data["body"]["text"],
                list_data["action"]["button"],
                list_data["action"]["sections"],
                header_text=list_data["header"]["text"]
            )

    return {"message": "Catalogo enviado", "result": result}


# ============================================
# Public Endpoints (sin auth) - para embebido en sitios web del tenant
# ============================================

@router.get("/public/catalog/{tenant_id}")
async def get_public_catalog(tenant_id: str, category: Optional[str] = None):
    """Catalogo publico del tenant. Sin auth - para widget/iframe externo."""
    # Validar que el tenant exista y este activo
    tenant = await _db.tenants.find_one({"tenant_id": tenant_id, "active": True}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado o inactivo")

    products = await catalog_service.get_products(tenant_id, category=category)
    categories = await catalog_service.get_categories(tenant_id)

    # Quitar tenant_id de la respuesta publica (no leak)
    for p in products:
        p.pop("tenant_id", None)

    return {
        "tenant": {
            "name": tenant.get("name", ""),
            "business_name": tenant.get("business_name", ""),
            "business_tagline": tenant.get("business_tagline", ""),
            "country": tenant.get("country", ""),
            "whatsapp_phone": tenant.get("contact_phone", "")
        },
        "products": products,
        "categories": categories
    }


@router.post("/public/catalog/{tenant_id}/recommend")
async def recommend_public_catalog(tenant_id: str, body: dict):
    """Recomendaciones IA del catalogo publico.
    Body: { "query": "busco depto 2 amb en Palermo", "max_results": 3 }
    """
    tenant = await _db.tenants.find_one({"tenant_id": tenant_id, "active": True}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado o inactivo")

    query = (body or {}).get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query es requerido")
    max_results = min((body or {}).get("max_results", 3), 10)

    products = await catalog_service.get_products(tenant_id)
    if not products:
        return {"recommendations": [], "reason": "catalogo vacio"}

    llm = create_llm_for_tenant(tenant)
    rec_ids = await llm.recommend_products(query, products, max_results=max_results)
    recommended = [p for p in products if p.get("product_id") in rec_ids]
    recommended.sort(key=lambda p: rec_ids.index(p["product_id"]) if p.get("product_id") in rec_ids else 99)
    for p in recommended:
        p.pop("tenant_id", None)

    return {
        "recommendations": recommended,
        "ai_enabled": llm.enabled
    }


@router.post("/catalog/recommend")
async def recommend_for_tenant(body: dict, current_user: User = Depends(get_current_user)):
    """Admin: recomendaciones IA sobre el propio catalogo (para preview/dashboard)"""
    query = (body or {}).get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query es requerido")

    tenant = await _db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    products = await catalog_service.get_products(current_user.tenant_id)
    if not products:
        return {"recommendations": [], "reason": "catalogo vacio"}

    llm = create_llm_for_tenant(tenant)
    rec_ids = await llm.recommend_products(query, products, max_results=body.get("max_results", 3))
    recommended = [p for p in products if p.get("product_id") in rec_ids]
    recommended.sort(key=lambda p: rec_ids.index(p["product_id"]) if p.get("product_id") in rec_ids else 99)
    return {
        "query": query,
        "recommendations": recommended,
        "ai_enabled": llm.enabled
    }
