"""
InmoBot SaaS - Servicio de Catalogo/Productos
Gestión de productos por tenant + envío de carruseles por WhatsApp.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class CatalogService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create_product(self, tenant_id: str, product: dict) -> dict:
        """Crea un producto en el catálogo del tenant"""
        doc = {
            "product_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": product.get("name", ""),
            "description": product.get("description", ""),
            "price": product.get("price", 0),
            "currency": product.get("currency", "USD"),
            "category": product.get("category", ""),
            "image_url": product.get("image_url", ""),
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.products.insert_one(doc)
        doc.pop("_id", None)
        return doc

    async def get_products(self, tenant_id: str, category: str = None, active_only: bool = True) -> List[dict]:
        """Lista productos del tenant"""
        query = {"tenant_id": tenant_id}
        if active_only:
            query["active"] = True
        if category:
            query["category"] = category

        products = await self.db.products.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        # Backfill product_id con bulk_write si hay productos legacy sin id
        from pymongo import UpdateOne
        ops = []
        for p in products:
            if not p.get("product_id"):
                new_id = str(uuid.uuid4())
                p["product_id"] = new_id
                ops.append(UpdateOne(
                    {"tenant_id": tenant_id, "name": p["name"], "product_id": {"$exists": False}},
                    {"$set": {"product_id": new_id}}
                ))
        if ops:
            await self.db.products.bulk_write(ops, ordered=False)
        return products

    async def get_product_by_id(self, tenant_id: str, product_id: str) -> Optional[dict]:
        """Obtiene un producto por su ID, verificando tenant"""
        return await self.db.products.find_one(
            {"tenant_id": tenant_id, "product_id": product_id},
            {"_id": 0}
        )

    async def get_categories(self, tenant_id: str) -> List[str]:
        """Lista categorías únicas del tenant"""
        pipeline = [
            {"$match": {"tenant_id": tenant_id, "active": True}},
            {"$group": {"_id": "$category"}},
            {"$sort": {"_id": 1}}
        ]
        results = await self.db.products.aggregate(pipeline).to_list(50)
        return [r["_id"] for r in results if r["_id"]]

    async def update_product(self, tenant_id: str, product_id: str, update_data: dict) -> bool:
        """Actualiza un producto por ID (con validación tenant)"""
        update_data.pop("tenant_id", None)
        update_data.pop("_id", None)
        update_data.pop("product_id", None)
        result = await self.db.products.update_one(
            {"tenant_id": tenant_id, "product_id": product_id},
            {"$set": update_data}
        )
        return result.matched_count > 0

    async def delete_product(self, tenant_id: str, product_id: str) -> bool:
        """Elimina (desactiva) un producto por ID (con validación tenant)"""
        result = await self.db.products.update_one(
            {"tenant_id": tenant_id, "product_id": product_id},
            {"$set": {"active": False}}
        )
        return result.matched_count > 0

    def build_product_list_message(self, products: List[dict], header: str = "Nuestros productos") -> dict:
        """
        Construye mensaje interactivo tipo LIST para WhatsApp.
        Muestra hasta 10 productos como opciones seleccionables.
        WhatsApp permite max 10 sections con max 10 rows c/u.
        """
        # Group by category
        categories = {}
        for p in products[:30]:  # tope de productos a considerar
            cat = p.get("category", "General") or "General"
            if cat not in categories:
                categories[cat] = []
            if len(categories[cat]) < 10:  # WhatsApp limit: 10 rows per section
                categories[cat].append(p)

        sections = []
        total_rows = 0
        for cat_name, items in list(categories.items())[:10]:  # max 10 sections
            rows = []
            for item in items:
                if total_rows >= 10:  # WA also enforces 10 total rows in single list
                    break
                price_str = f"${item['price']} {item.get('currency', 'USD')}" if item.get('price') else ""
                rows.append({
                    "id": f"prod_{item.get('product_id', '')[:30]}",
                    "title": item["name"][:24],  # WhatsApp limit
                    "description": (f"{price_str} - {item.get('description', '')}")[:72]
                })
                total_rows += 1
            if rows:
                sections.append({
                    "title": cat_name[:24],
                    "rows": rows
                })
            if total_rows >= 10:
                break

        return {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": "Selecciona un producto para mas informacion:"},
            "action": {
                "button": "Ver catalogo",
                "sections": sections
            }
        }

    def build_single_product_message(self, product: dict) -> str:
        """Construye texto de detalle de un producto"""
        parts = [f"*{product['name']}*"]
        if product.get("description"):
            parts.append(product["description"])
        if product.get("price"):
            parts.append(f"\nPrecio: ${product['price']} {product.get('currency', 'USD')}")
        if product.get("category"):
            parts.append(f"Categoria: {product['category']}")
        return "\n".join(parts)

    def build_carousel_buttons(self, products: List[dict]) -> tuple:
        """
        Construye mensaje con botones para simular carrusel (max 3 productos).
        Retorna (body_text, buttons)
        """
        body_parts = []
        buttons = []

        for i, p in enumerate(products[:3]):  # WhatsApp limit: 3 buttons
            price_str = f" - ${p['price']}" if p.get('price') else ""
            body_parts.append(f"{i+1}. *{p['name']}*{price_str}")
            if p.get("description"):
                body_parts.append(f"   {p['description'][:60]}")
            body_parts.append("")

            buttons.append({
                "type": "reply",
                "reply": {
                    "id": f"prod_{p.get('product_id', '')[:30]}",
                    "title": f"Ver {p['name'][:17]}"
                }
            })

        body_text = "\n".join(body_parts)
        return body_text, buttons
