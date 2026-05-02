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
            # Smart Substitution fields (Iter31):
            # - stock_quantity: None = sin tracking de stock (solo active flag);
            #   0 = agotado; >0 = unidades disponibles.
            # - substitute_product_ids: lista manual ordenada de sustitutos
            #   preferidos (override de la lógica automática).
            "stock_quantity": product.get("stock_quantity"),
            "substitute_product_ids": list(product.get("substitute_product_ids") or []),
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
        """Actualiza un producto por ID (con validación tenant).

        Si el payload incluye `stock_quantity`, sincroniza `active` igual que
        `set_stock` para evitar la inconsistencia de tener active=true con
        stock=0 o active=false con stock>0.
        """
        update_data.pop("tenant_id", None)
        update_data.pop("_id", None)
        update_data.pop("product_id", None)
        if "stock_quantity" in update_data:
            stock = update_data["stock_quantity"]
            if stock is not None and stock <= 0:
                update_data["active"] = False
            elif stock is not None and stock > 0:
                update_data["active"] = True
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

    # ============================================================
    # Smart Substitution (Iter31)
    # ============================================================

    def is_out_of_stock(self, product: dict) -> bool:
        """Un producto está agotado si está inactivo O si stock_quantity==0."""
        if not product:
            return True
        if product.get("active") is False:
            return True
        stock = product.get("stock_quantity")
        if stock is not None and stock <= 0:
            return True
        return False

    def get_availability_status(self, product: dict) -> str:
        """
        Retorna 'available' | 'out_of_stock' | 'low_stock' | 'no_tracking'.
        Útil para la UI y para decidir copy del bot.
        """
        if self.is_out_of_stock(product):
            return "out_of_stock"
        stock = product.get("stock_quantity")
        if stock is None:
            return "no_tracking"
        if stock <= 3:
            return "low_stock"
        return "available"

    async def find_out_of_stock_match(
        self,
        tenant_id: str,
        query: str,
        min_similarity: float = 0.45,
    ) -> Optional[dict]:
        """Busca si la query del cliente hace match con un producto AGOTADO.

        Usa matching fuzzy (sustring + tokens en común) sobre nombre. Retorna
        el producto agotado con mejor score, o None si no hay match claro.

        Esta es la DETECCIÓN previa al flujo de sustitución: solo disparamos
        "está agotado pero tengo esta alternativa" si el cliente efectivamente
        mencionó un producto específico que ya no está disponible.

        Tokens cortos (<3 chars) como "15", "S24", "X" se conservan ya que
        muchos modelos de productos tienen números/letras significativas.
        Se quita la puntuación al final de cada token ("pro?" → "pro").
        """
        import string
        query = (query or "").strip().lower()
        if len(query) < 3:
            return None

        all_products = await self.db.products.find(
            {"tenant_id": tenant_id},
            {"_id": 0},
        ).to_list(500)

        out_of_stock = [p for p in all_products if self.is_out_of_stock(p)]
        if not out_of_stock:
            return None

        # Tokenizar quitando signos de puntuación al borde (pro? → pro, 15! → 15)
        # Stopwords comunes que no aportan semántica del producto.
        STOPWORDS = {
            "tienen", "tienes", "tenes", "hay", "venden", "vende", "quiero",
            "necesito", "busco", "que", "con", "del", "los", "las", "una",
            "uno", "esta", "este", "para", "cuanto", "cuesta", "vale",
            "precio", "info", "informacion", "sobre",
        }

        def tokenize(text: str) -> set:
            tokens = set()
            for raw in text.split():
                t = raw.strip(string.punctuation)
                if not t or t in STOPWORDS:
                    continue
                # Aceptamos tokens cortos si son alfanuméricos significativos:
                # - len >= 3 (palabras normales)
                # - len 2-3 con dígitos (S24, X9, M1, V8)
                # - len 2 alfanumérico mixto (4K, 8K, P9)
                if len(t) >= 3:
                    tokens.add(t)
                elif len(t) == 2 and any(ch.isdigit() for ch in t):
                    tokens.add(t)
            return tokens

        query_tokens = tokenize(query)
        if not query_tokens:
            return None

        best = None
        best_score = 0.0
        for p in out_of_stock:
            name = (p.get("name") or "").lower()
            if not name:
                continue
            name_tokens = tokenize(name)
            if not name_tokens:
                continue
            common = query_tokens & name_tokens
            token_score = len(common) / max(len(name_tokens), 1)
            substring_bonus = 0.3 if name in query or query in name else 0.0
            score = token_score + substring_bonus
            if score > best_score:
                best_score = score
                best = p

        if best and best_score >= min_similarity:
            return best
        return None

    async def find_substitute(
        self,
        tenant_id: str,
        out_of_stock_product: dict,
        max_results: int = 3,
    ) -> List[dict]:
        """Encuentra sustitutos para un producto agotado, en cascada:

        1. **Manual**: `substitute_product_ids` configurado por el admin.
        2. **Categoría + precio similar** (±30%): misma categoría, activo, stock>0.
        3. **GPT fallback**: recomendación semántica sobre todo el catálogo activo
           usando el nombre + descripción del agotado como query.

        Retorna lista de productos (puede estar vacía si no hay nada en stock).
        """
        if not out_of_stock_product:
            return []
        results: List[dict] = []
        seen_ids = set()

        # 1. Manual substitutes
        manual_ids = out_of_stock_product.get("substitute_product_ids") or []
        if manual_ids:
            manual_subs = await self.db.products.find(
                {"tenant_id": tenant_id, "product_id": {"$in": manual_ids}, "active": True},
                {"_id": 0},
            ).to_list(max_results * 2)
            # Preservar orden manual + filtrar agotados
            ordered = sorted(
                [s for s in manual_subs if not self.is_out_of_stock(s)],
                key=lambda s: manual_ids.index(s["product_id"]) if s.get("product_id") in manual_ids else 99,
            )
            for s in ordered[:max_results]:
                if s["product_id"] not in seen_ids:
                    results.append(s)
                    seen_ids.add(s["product_id"])

        if len(results) >= max_results:
            return results

        # 2. Same category + similar price
        category = out_of_stock_product.get("category")
        base_price = out_of_stock_product.get("price") or 0
        if category:
            candidates = await self.db.products.find(
                {"tenant_id": tenant_id, "category": category, "active": True,
                 "product_id": {"$ne": out_of_stock_product.get("product_id"), "$nin": list(seen_ids)}},
                {"_id": 0},
            ).to_list(50)
            # Filtrar agotados por stock_quantity
            in_stock = [c for c in candidates if not self.is_out_of_stock(c)]
            if base_price > 0:
                # Ordenar por proximidad de precio (±30% es ideal)
                in_stock.sort(key=lambda c: abs((c.get("price") or 0) - base_price))
            for c in in_stock[:max_results - len(results)]:
                if c["product_id"] not in seen_ids:
                    results.append(c)
                    seen_ids.add(c["product_id"])

        if len(results) >= max_results:
            return results

        # 3. GPT fallback: usa nombre + desc del agotado como query sobre todo el catálogo
        try:
            from llm_provider import create_llm_for_tenant
            tenant = await self.db.tenants.find_one(
                {"tenant_id": tenant_id}, {"_id": 0},
            )
            all_active = await self.get_products(tenant_id, active_only=True)
            in_stock_active = [
                p for p in all_active
                if not self.is_out_of_stock(p) and p["product_id"] not in seen_ids
                and p["product_id"] != out_of_stock_product.get("product_id")
            ]
            if in_stock_active and tenant:
                llm = create_llm_for_tenant(tenant)
                query = (
                    f"{out_of_stock_product.get('name', '')} "
                    f"{out_of_stock_product.get('description', '')}"
                ).strip()
                rec_ids = await llm.recommend_products(
                    query, in_stock_active, max_results=max_results - len(results),
                )
                for pid in rec_ids:
                    match = next((p for p in in_stock_active if p["product_id"] == pid), None)
                    if match and match["product_id"] not in seen_ids:
                        results.append(match)
                        seen_ids.add(match["product_id"])
                        if len(results) >= max_results:
                            break
        except Exception as e:
            logger.warning(f"[find_substitute] GPT fallback failed for tenant={tenant_id}: {e}")

        return results

    async def set_substitutes(
        self,
        tenant_id: str,
        product_id: str,
        substitute_ids: List[str],
    ) -> bool:
        """Configura sustitutos manuales para un producto. Valida que todos existan."""
        if substitute_ids:
            count = await self.db.products.count_documents(
                {"tenant_id": tenant_id, "product_id": {"$in": substitute_ids}}
            )
            if count != len(substitute_ids):
                return False
        result = await self.db.products.update_one(
            {"tenant_id": tenant_id, "product_id": product_id},
            {"$set": {"substitute_product_ids": list(substitute_ids or [])}},
        )
        return result.matched_count > 0

    async def set_stock(
        self,
        tenant_id: str,
        product_id: str,
        stock_quantity: Optional[int],
    ) -> bool:
        """Actualiza stock_quantity. None = sin tracking; 0 = agotado; >0 = disponible."""
        update = {"stock_quantity": stock_quantity}
        # Si marcamos como agotado, también desactivamos para que no aparezca en listados
        # (se puede re-activar al setear stock>0)
        if stock_quantity is not None and stock_quantity <= 0:
            update["active"] = False
        elif stock_quantity is not None and stock_quantity > 0:
            update["active"] = True
        result = await self.db.products.update_one(
            {"tenant_id": tenant_id, "product_id": product_id},
            {"$set": update},
        )
        return result.matched_count > 0

    # ============================================================
    # Back-in-stock waitlist (Iter32)
    # ============================================================

    async def add_to_waitlist(
        self,
        tenant_id: str,
        lead_phone: str,
        product_id: str,
        product_name: str = "",
    ) -> None:
        """Registra interés de un lead en un producto agotado.

        Upsert por (tenant_id, lead_phone, product_id) para evitar duplicados
        si el lead pregunta varias veces. Si ya existe y está notified, se
        resetea notified_at para que vuelva a recibir aviso cuando reponga.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.db.product_waitlist.update_one(
            {"tenant_id": tenant_id, "lead_phone": lead_phone, "product_id": product_id},
            {
                "$set": {
                    "product_name": product_name,
                    "asked_at": now,
                    "notified_at": None,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        # P1 quick win: dispara alerta al superadmin si el producto cruzó threshold
        # Best-effort: cualquier error se loguea pero NO interrumpe el flujo del bot.
        try:
            from waitlist_alert_service import maybe_alert_superadmin
            await maybe_alert_superadmin(self.db, tenant_id, product_id, product_name)
        except Exception as e:
            logger.warning(f"[waitlist_alert] hook failed tenant={tenant_id} product={product_id}: {e}")

    async def notify_back_in_stock(
        self,
        tenant_id: str,
        product_id: str,
    ) -> int:
        """Envía WhatsApp a todos los leads que esperaban este producto.

        Solo notifica entradas con notified_at=None. Retorna cantidad de
        mensajes enviados. Best-effort: si falla el envío a uno, continúa
        con los siguientes.
        """
        # Validar que el producto está realmente disponible
        product = await self.get_product_by_id(tenant_id, product_id)
        if not product or self.is_out_of_stock(product):
            return 0

        waiters = await self.db.product_waitlist.find(
            {
                "tenant_id": tenant_id,
                "product_id": product_id,
                "notified_at": None,
            },
            {"_id": 0},
        ).to_list(1000)
        if not waiters:
            return 0

        # WhatsApp service del tenant
        try:
            from whatsapp_service import create_wa_service_for_tenant
            tenant = await self.db.tenants.find_one(
                {"tenant_id": tenant_id}, {"_id": 0},
            )
            if not tenant:
                return 0
            wa = create_wa_service_for_tenant(tenant)
        except Exception as e:
            logger.warning(f"[back_in_stock] wa_service init failed: {e}")
            return 0

        price_str = (
            f" (${product['price']} {product.get('currency', 'USD')})"
            if product.get("price") else ""
        )
        name = product.get("name", "ese producto")
        message = (
            f"¡Buenas noticias! 🎉\n\n"
            f"*{name}*{price_str} volvió a estar disponible. "
            f"Me pediste que te avisara, así que acá estoy 👇\n\n"
            f"¿Querés reservarlo ahora o que te pase más info?"
        )

        sent = 0
        now = datetime.now(timezone.utc).isoformat()
        for w in waiters:
            try:
                await wa.send_message(w["lead_phone"], message)
                await self.db.product_waitlist.update_one(
                    {
                        "tenant_id": tenant_id,
                        "lead_phone": w["lead_phone"],
                        "product_id": product_id,
                    },
                    {"$set": {"notified_at": now}},
                )
                sent += 1
            except Exception as e:
                logger.warning(
                    f"[back_in_stock] send failed tenant={tenant_id} "
                    f"lead={w['lead_phone']} product={product_id}: {e}"
                )
        logger.info(
            f"[back_in_stock] tenant={tenant_id} product={product_id} "
            f"notified {sent}/{len(waiters)} leads"
        )
        return sent

    def build_substitute_message(
        self,
        out_of_stock_product: dict,
        substitutes: List[dict],
    ) -> str:
        """Genera el mensaje de WhatsApp con copy del bonus 'disponibilidad'."""
        name = out_of_stock_product.get("name", "ese producto")
        if not substitutes:
            return (
                f"Justo *{name}* está agotado por ahora 😕. "
                f"¿Querés que te avise cuando vuelva a estar disponible?"
            )
        if len(substitutes) == 1:
            alt = substitutes[0]
            price = (
                f" (${alt['price']} {alt.get('currency', 'USD')})"
                if alt.get("price") else ""
            )
            return (
                f"Justo *{name}* está agotado, pero tengo una buena noticia 👇\n\n"
                f"*{alt['name']}*{price} tiene características muy parecidas y "
                f"está disponible ahora. ¿Te cuento las diferencias?"
            )
        lines = [
            f"Justo *{name}* está agotado, pero tengo alternativas que te pueden "
            f"interesar 👇\n",
        ]
        for i, alt in enumerate(substitutes[:3], 1):
            price = (
                f" — ${alt['price']} {alt.get('currency', 'USD')}"
                if alt.get("price") else ""
            )
            lines.append(f"*{i}. {alt['name']}*{price}")
        lines.append("\n¿Cuál te interesa? Te cuento más en 30 segundos.")
        return "\n".join(lines)

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
