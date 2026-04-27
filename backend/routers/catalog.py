"""Router de catalogo de productos por tenant"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import get_current_user, require_admin, get_db
from catalog_service import CatalogService
from whatsapp_service import create_wa_service_for_tenant
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
