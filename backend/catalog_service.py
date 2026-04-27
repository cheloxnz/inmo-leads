"""
InmoBot SaaS - Servicio de Catalogo/Productos
Gestión de productos por tenant + envío de carruseles por WhatsApp.
"""
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class CatalogService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create_product(self, tenant_id: str, product: dict) -> dict:
        """Crea un producto en el catálogo del tenant"""
        doc = {
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
        return products

    async def get_categories(self, tenant_id: str) -> List[str]:
        """Lista categorías únicas del tenant"""
        pipeline = [
            {"$match": {"tenant_id": tenant_id, "active": True}},
            {"$group": {"_id": "$category"}},
            {"$sort": {"_id": 1}}
        ]
        results = await self.db.products.aggregate(pipeline).to_list(50)
        return [r["_id"] for r in results if r["_id"]]

    async def update_product(self, tenant_id: str, product_name: str, update_data: dict) -> bool:
        """Actualiza un producto"""
        update_data.pop("tenant_id", None)
        update_data.pop("_id", None)
        result = await self.db.products.update_one(
            {"tenant_id": tenant_id, "name": product_name},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_product(self, tenant_id: str, product_name: str) -> bool:
        """Elimina (desactiva) un producto"""
        result = await self.db.products.update_one(
            {"tenant_id": tenant_id, "name": product_name},
            {"$set": {"active": False}}
        )
        return result.modified_count > 0

    def build_product_list_message(self, products: List[dict], header: str = "Nuestros productos") -> dict:
        """
        Construye mensaje interactivo tipo LIST para WhatsApp.
        Muestra hasta 10 productos como opciones seleccionables.
        """
        sections = []
        # Group by category
        categories = {}
        for p in products[:10]:  # WhatsApp limit: 10 items in list
            cat = p.get("category", "General")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(p)

        for cat_name, items in categories.items():
            rows = []
            for item in items:
                price_str = f"${item['price']} {item.get('currency', 'USD')}" if item.get('price') else ""
                rows.append({
                    "id": f"prod_{item['name'][:20].replace(' ', '_').lower()}",
                    "title": item["name"][:24],  # WhatsApp limit
                    "description": f"{price_str} - {item.get('description', '')[:72]}"
                })
            sections.append({
                "title": cat_name[:24],
                "rows": rows
            })

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
                    "id": f"product_{p['name'][:15].replace(' ', '_').lower()}",
                    "title": f"Ver {p['name'][:17]}"
                }
            })

        body_text = "\n".join(body_parts)
        return body_text, buttons
