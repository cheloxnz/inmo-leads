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
    # Detectar si el producto estaba agotado ANTES del update para disparar
    # notificación back-in-stock si el stock sube de 0 a >0.
    was_out = False
    if "stock_quantity" in body:
        before = await catalog_service.get_product_by_id(current_user.tenant_id, product_id)
        was_out = bool(before and catalog_service.is_out_of_stock(before))
    success = await catalog_service.update_product(current_user.tenant_id, product_id, body)
    if not success:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    notified = 0
    if was_out:
        try:
            notified = await catalog_service.notify_back_in_stock(current_user.tenant_id, product_id)
        except Exception:
            notified = 0
    return {"message": "Producto actualizado", "notified_leads": notified}


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

    # template_id: prefer tenant.template_id, fallback bot_config.template_id, default servicios
    template_id = tenant.get("template_id")
    if not template_id:
        bot_cfg = await _db.bot_config.find_one({"tenant_id": tenant_id}, {"_id": 0, "template_id": 1})
        template_id = (bot_cfg or {}).get("template_id", "servicios")

    # Quitar tenant_id de la respuesta publica (no leak)
    for p in products:
        p.pop("tenant_id", None)

    return {
        "tenant": {
            "name": tenant.get("name", ""),
            "business_name": tenant.get("business_name", ""),
            "business_tagline": tenant.get("business_tagline", ""),
            "country": tenant.get("country", ""),
            "whatsapp_phone": tenant.get("contact_phone", ""),
            "whatsapp_display_phone": tenant.get("whatsapp_display_phone", ""),
            "template_id": template_id,
            "logo_url": tenant.get("logo_url", ""),
            "primary_color": tenant.get("primary_color", ""),
            "accent_color": tenant.get("accent_color", ""),
            "hero_bg_url": tenant.get("hero_bg_url", ""),
            "custom_features": tenant.get("custom_features") or [],
            "custom_steps": tenant.get("custom_steps") or [],
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


# ============================================================
# Smart Substitution endpoints (Iter31)
# ============================================================

@router.patch("/catalog/products/{product_id}/stock")
async def set_product_stock(
    product_id: str,
    body: dict,
    current_user: User = Depends(require_admin),
):
    """Admin: actualiza stock_quantity de un producto.

    Body: `{"stock_quantity": 5}` | `{"stock_quantity": 0}` (agotado) | `{"stock_quantity": null}` (sin tracking).
    Cuando stock<=0, se marca también como inactive para que no aparezca en listados.
    """
    if "stock_quantity" not in body:
        raise HTTPException(status_code=400, detail="stock_quantity es requerido")
    stock = body["stock_quantity"]
    if stock is not None and not isinstance(stock, int):
        raise HTTPException(status_code=400, detail="stock_quantity debe ser int o null")
    # Detectar transición agotado → disponible para disparar notificaciones
    before = await catalog_service.get_product_by_id(current_user.tenant_id, product_id)
    was_out = bool(before and catalog_service.is_out_of_stock(before))
    ok = await catalog_service.set_stock(current_user.tenant_id, product_id, stock)
    if not ok:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product = await catalog_service.get_product_by_id(current_user.tenant_id, product_id)
    notified = 0
    if was_out and not catalog_service.is_out_of_stock(product):
        try:
            notified = await catalog_service.notify_back_in_stock(current_user.tenant_id, product_id)
        except Exception:
            notified = 0
    return {
        "ok": True,
        "product_id": product_id,
        "stock_quantity": product.get("stock_quantity"),
        "active": product.get("active"),
        "availability_status": catalog_service.get_availability_status(product),
        "notified_leads": notified,
    }


@router.put("/catalog/products/{product_id}/substitutes")
async def set_product_substitutes(
    product_id: str,
    body: dict,
    current_user: User = Depends(require_admin),
):
    """Admin: configura sustitutos manuales para un producto.

    Body: `{"substitute_product_ids": ["pid-1", "pid-2", "pid-3"]}`.
    Lista vacía = sin sustitutos manuales (se usan los automáticos).
    """
    subs = body.get("substitute_product_ids", [])
    if not isinstance(subs, list):
        raise HTTPException(status_code=400, detail="substitute_product_ids debe ser array")
    if len(subs) > 10:
        raise HTTPException(status_code=400, detail="max 10 sustitutos")
    ok = await catalog_service.set_substitutes(current_user.tenant_id, product_id, subs)
    if not ok:
        raise HTTPException(status_code=404, detail="Producto no encontrado o algún sustituto no existe")
    product = await catalog_service.get_product_by_id(current_user.tenant_id, product_id)
    return {
        "ok": True,
        "product_id": product_id,
        "substitute_product_ids": product.get("substitute_product_ids", []),
    }


@router.post("/catalog/substitute-preview")
async def substitute_preview(
    body: dict,
    current_user: User = Depends(require_admin),
):
    """Preview del flujo de sustitución desde el panel admin.

    Body: `{"query": "tienen el iPhone 15?"}` o `{"product_id": "pid-xxx"}`.
    Retorna el producto agotado detectado + la lista de sustitutos que le
    mostraría el bot + el mensaje exacto que se enviaría por WhatsApp.
    """
    tenant_id = current_user.tenant_id
    query = (body or {}).get("query", "").strip()
    product_id = (body or {}).get("product_id")

    out_of_stock = None
    if product_id:
        p = await catalog_service.get_product_by_id(tenant_id, product_id)
        if p and catalog_service.is_out_of_stock(p):
            out_of_stock = p
    elif query:
        out_of_stock = await catalog_service.find_out_of_stock_match(tenant_id, query)

    if not out_of_stock:
        return {
            "out_of_stock_product": None,
            "substitutes": [],
            "message": None,
            "reason": "no se detectó match con producto agotado",
        }

    substitutes = await catalog_service.find_substitute(
        tenant_id, out_of_stock, max_results=3,
    )
    message = catalog_service.build_substitute_message(out_of_stock, substitutes)
    return {
        "out_of_stock_product": out_of_stock,
        "substitutes": substitutes,
        "message": message,
    }



@router.get("/catalog/waitlist")
async def get_waitlist(current_user: User = Depends(require_admin)):
    """Admin: leads esperando que vuelvan productos agotados.

    Retorna sólo las entradas pendientes de notificar (notified_at=None),
    agrupadas por producto para mostrar en el panel.
    """
    db = catalog_service.db
    items = await db.product_waitlist.find(
        {"tenant_id": current_user.tenant_id, "notified_at": None},
        {"_id": 0},
    ).sort("asked_at", -1).to_list(500)
    # Agrupar por product_id
    grouped: dict = {}
    for it in items:
        pid = it.get("product_id", "")
        if pid not in grouped:
            grouped[pid] = {
                "product_id": pid,
                "product_name": it.get("product_name", ""),
                "leads": [],
            }
        grouped[pid]["leads"].append({
            "lead_phone": it.get("lead_phone", ""),
            "asked_at": it.get("asked_at"),
        })
    return {
        "total_pending": len(items),
        "by_product": list(grouped.values()),
    }
