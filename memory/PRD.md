# InmoBot - PRD (Product Requirements Document)

## Original Problem Statement
Plataforma SaaS para automatización de inmobiliarias con bot de WhatsApp, IA y CRM completo.

## Core Requirements
1. **Bot de WhatsApp con IA**
   - Respuestas automáticas 24/7
   - Calificación de leads
   - Agendamiento de citas
   - Transcripción de audio (Whisper)
   - Respuestas inteligentes (GPT)

2. **Dashboard de Administración**
   - Gestión de leads
   - Calendario de citas
   - Métricas y gráficos
   - Notificaciones en tiempo real
   - Sistema de etiquetas
   - Vista Kanban para pipeline

3. **SaaS Comercial**
   - Página de precios con 4 planes (Starter, Profesional, Agencia, Enterprise)
   - Integración con Stripe
   - Email de bienvenida automático

## User Personas
- **Inmobiliarias pequeñas:** Plan Starter ($49/mes)
- **Inmobiliarias en crecimiento:** Plan Profesional ($129/mes)
- **Grandes operaciones:** Plan Agencia ($299/mes)
- **Enterprise:** Precio dinámico por cantidad de líneas

---

## Changelog

### 2026-04-28 (Sesión Actual - AI Flow Editor + Hardening completo + Onboarding stress)
- **AI Flow Editor (`/api/flow/ai-edit`):** asistente IA que edita el árbol del FlowBuilder en lenguaje natural. Whitelist de 7 operaciones: `add_step`, `update_step`, `remove_step`, `reorder_step`, `update_welcome`, `update_completion`, `update_appointment`. Cada op valida tipo (text/buttons/list), límite de botones WhatsApp (max 3), preview en 2 pasos con `confirmed_ops`, audit log con diff completo, rate-limit 8/h por tenant.
  - UI: `AIFlowAssistant.js` integrado arriba del editor en `/flujo`. Iconografía + colores diferenciados por tipo de op, contador de pasos `current → preview`, mismas mejoras que AIBotConfig (countdown retry-after, deshabilitado durante 429).
- **Hardening AI Bot Config Assistant:**
  - `llm_service.py` ahora expone método público `send_message(system, user, max_tokens)` que levanta `RuntimeError` si no hay client. Routers AI consumen este método (no más `_send_message` privado).
  - `bot_config_ai.py`: el chequeo de `llm.client` ocurre ANTES del rate-limit → no se gastan slots cuando IA no está configurada.
  - Frontend `AIBotConfigAssistant.js`:
    - Countdown en vivo del `retry_after` cuando se recibe 429 (parser regex extrae los segundos del detail, `setInterval` decrementa cada 1s, deshabilita preview button hasta que llegue a 0).
    - Banner upsell post-apply (`Crown` icon, gradient amber) que sugiere upgrade a Plan Profesional con CTA a `/billing`. Solo se muestra si `subscription_plan` del tenant NO es `profesional/agencia/enterprise`.
    - Cierre dismissible del banner (`X`).
- **Auth global 401 interceptor (`AuthContext.js`):** `axios.interceptors.response.use` registrado en `useEffect([], [])`. Si una request retorna 401 con token presente → limpia sesión + redirect a `/login?expired=1`. No requiere cambios en componentes individuales.
- **`/api/auth/tenant/branding` ahora devuelve `subscription_plan` y `subscription_status`** (read-only) para condiciones de UI tipo upsell.
- **Tests E2E concurrencia Onboarding (P1) — `test_iter13_onboarding_concurrency.py`:**
  - 3 tests con `pytest-asyncio` + `httpx.AsyncClient` + `motor`.
  - Test 1: valida unique index sobre `tenants.tenant_id`.
  - Test 2: dispara 15 requests simultáneos al mismo `business_name` → asserta 0 errores 5xx, 0 documentos huérfanos (tenant sin agent o agent sin tenant), todos los 200 tienen documento real en MongoDB.
  - Test 3: 2 requests con MISMO email → uno gana 200, otro 409, exactamente 1 agent en DB.
  - **Resultado:** 3/3 PASS.
- **Tests:** Backend total 25/25 passed (iter12+iter13+iter14, 1 skip esperado de rate-limit cuando no hay OpenAI key — comportamiento correcto del hardening). Frontend E2E 100% (data-testids correctos en `/config` y `/flujo`).
- **Archivos:** `/app/backend/routers/flow_ai.py` (nuevo), `/app/backend/llm_service.py` (método público), `/app/backend/auth_routes.py` (branding extendido), `/app/backend/server.py` (router registrado), `/app/frontend/src/components/AIFlowAssistant.js` (nuevo), `/app/frontend/src/components/AIBotConfigAssistant.js` (countdown+upsell), `/app/frontend/src/components/FlowBuilder.js` (integración), `/app/frontend/src/context/AuthContext.js` (401 interceptor), `/app/backend/tests/test_iter13_onboarding_concurrency.py` (nuevo).

### 2026-04-28 (Sesión Actual - AI Configuration Assistant + Hardening)
- **AI Configuration Assistant** (`POST /api/bot-config/ai-edit`, `GET /api/bot-config/ai-edit/info`):
  - Tenant admin escribe en lenguaje natural (ej. "Cambia horario a 9-19hs y los sabados de 10 a 13") y la IA traduce a JSON contra whitelist de 9 campos del modelo `BotConfig` (business_hours_start/end, business_days, saturday_hours_*, auto_handoff_score, warm_lead_reactivation_days, appointment_reminder_hours, welcome_message).
  - Flujo de 2 pasos: (1) preview con LLM → devuelve `actions` válidas + `invalid` + `summary` + `previous` para diff visual; (2) apply manda `confirmed_actions` ya validadas (sin llamar LLM otra vez) → evita drift entre preview y apply.
  - Defensa en capas: type check, rangos por campo (0-23 horas, 1-12 score, 1-72hs reminder, 1-30 días reactivación), validación de días contra set fijo, normalización a minúsculas.
  - Rate-limit: 10 req/h por tenant (sliding window Redis/in-memory). Solo se consume cuando se llama al LLM, no en la rama apply ni cuando IA no está configurada (503 antes de consumir slot).
  - Audit log `audit_log` con `action=bot_config_ai_edit`, `instruction`, `applied_changes` (campo + valor para compliance/debug).
  - UI en `/config` (Configuration.js): tarjeta destacada "Asistente IA de Configuración" con badge Beta, textarea (max 500 chars + counter), 5 chips de ejemplos clickeables, indicador de rate-limit, panel de preview con diff `previous → new` color-coded (verde válido, rojo rechazado), botones Previsualizar/Aplicar/Reiniciar.
  - Tests: backend 11/11 PASS (info, validaciones 400, no-auth 401/403, sin-key 503, rate-limit 429, regresión /api/config), frontend E2E 12/12 PASS.
  - Archivos: `/app/backend/routers/bot_config_ai.py`, `/app/frontend/src/components/AIBotConfigAssistant.js`, integración en `Configuration.js` + `server.py`.

### 2026-04-28 (Sesión Anterior - Rate-limit AI + Upload Logo + Paleta + Auto-onboarding)
- **Rate-limit `/ai-generate`:** sliding window in-memory 5 calls/hora por tenant. Header rate_limit en respuesta. 429 cuando se excede con segundos de retry.
- **Comparación paleta primary vs accent (`evaluatePaletteHarmony`):**
  - <1.5 → warn-low "casi idénticos, no se va a notar"
  - >14 → warn-high "muy contrastante, agresiva"
  - 2-8 → ok "paleta coherente"
  - UI: hint debajo del card de Colores en LandingEditor.
- **Upload logo (`routers/uploads.py`):**
  - `POST /api/uploads/logo` (admin) acepta jpg/png/webp/svg/gif, max 2MB, valida content-type.
  - `GET /api/uploads/logos/{filename}` sirve archivos con regex anti-traversal + verificación path absoluto.
  - UI: botón "Subir" al lado del input URL en LandingEditor + preview de imagen.
- **🌟 Auto-onboarding wizard (sugerencia SaaS):**
  - `routers/onboarding.py` con `slugify`, detección automática de template_id por keywords (inmobiliaria, clinica, restaurante, ecommerce, servicios), seed de 3 productos demo del rubro.
  - `POST /api/onboarding/suggest-tenant-id`: genera slug único.
  - `POST /api/onboarding/auto-setup`: crea tenant + agente admin + landing IA (tagline + features + steps generados con LLM con fallback) + 3 productos demo + JWT token para auto-login. Todo en una sola transacción.
  - **Wizard `/signup`** (3 pasos visuales): step 1 (negocio + descripción + rubro autodetect), step 2 (email + password con tenant_id sugerido), step 3 (resumen con CTAs "Ver mi landing" / "Ir al dashboard").
  - Stepper con estados visuales: completado (verde ✓), activo (gradient), pendiente (gris).
  - Botón "Crear mi bot gratis" agregado al hero de la landing genérica.
- **Testing 100% PASS (23/23 backend + frontend E2E):** `/app/test_reports/iteration_11.json`

### 2026-04-28 (Sesión Anterior - Validaciones Backend + IA Copy + Hints WCAG)
- **Backend validaciones (`auth_routes.py`):**
  - `_validate_branding_payload` con regex hex (`#rrggbb`), URL http(s), template_id en whitelist (5 rubros), custom_features/steps debe ser lista (max 5), max 500 chars por string.
  - 400 con `validation_errors` array para errores de tipo.
  - **Audit log**: cada PUT con campos rechazados por whitelist se persiste en `db.audit_log` con `tenant_id, user_email, action='branding_rejected_fields', rejected_fields, timestamp`.
- **🌟 IA Copy Generator (sugerencia SaaS):**
  - `LLMService.generate_landing_copy(description)` → JSON estructurado: `business_tagline`, 3 features `{icon, title, desc}`, 3 steps. Iconos validados (home/calendar/message/shield/bot), title truncado a 50 chars, desc a 120.
  - Endpoint `POST /api/auth/tenant/branding/ai-generate` (admin only).
  - Fallback graceful sin LLM (`ai_enabled=false` con tagline genérico).
  - UI: box morado "Generar con IA" en LandingEditor que aplica el copy generado al form (incluso fallback, con toast warning).
- **Separación `whatsapp_display_phone`:**
  - Nuevo campo en branding whitelist + helper text en UI: "WhatsApp principal" (recibe mensajes) vs "WhatsApp para mostrar" (CTA de la landing).
  - DynamicLanding usa `whatsapp_display_phone || contact_phone`.
- **Hints WCAG (`utils/colorContrast.js`):**
  - `evaluateColorContrast(primary)` calcula ratio WCAG 2.1 contra el peor caso real (white + #fafafa).
  - Niveles: AAA (≥7), AA (≥4.5), AA-large (≥3), fail (<3).
  - UI: badge debajo de cada color picker con color verde/rojo según nivel.
- **Testing 100% PASS (20/20 backend + UI E2E):** `/app/test_reports/iteration_10.json`
- **Mejoras post-test aplicadas** (sugeridas por testing agent):
  - colorContrast usa peor-caso real (no best-case).
  - LLM trunca title/desc para evitar UI rota.
  - Aplica tagline fallback aunque IA off (mejor UX).

### 2026-04-28 (Sesión Anterior - Editor SuperAdmin + Subdomain Routing + Editor Visual de Landing)
- **Editor de branding en SuperAdminPanel:** botón "Editar branding" en cada tenant card → form inline con business_name, tagline, template, phone, logo, colores. Botón "Ver landing" abre `/inicio/{tenant_id}`.
- **Editor Visual de Landing (`/landing/editor`)** para tenant admin:
  - Form completo + **vista previa en tiempo real** (lado derecho) que refleja cambios sin guardar.
  - Color pickers (primary + accent), upload URL de logo.
  - Custom features (hasta 5, cada uno con icon + título + desc), custom steps.
  - Botón "Usar default del template" carga features/steps del template seleccionado.
  - Botón "Preview" abre la landing pública en nueva pestaña.
- **Backend nuevos endpoints (auth_routes.py):**
  - `GET /api/auth/tenant/branding` (tenant admin) → lee branding del tenant del JWT (custom_features y custom_steps siempre [] por default).
  - `PUT /api/auth/tenant/branding` (tenant admin) → whitelist estricta: solo `business_name, business_tagline, logo_url, primary_color, accent_color, hero_bg_url, template_id, contact_phone, country, custom_features, custom_steps`. Campos sensibles (max_ai_messages, stripe_customer_id) bloqueados.
- **Subdomain routing (`utils/subdomain.js`):** Detecta `{tenant_id}.platform.com` solo si `REACT_APP_PLATFORM_DOMAIN` está seteado. Whitelist de reservados (www, app, api, admin, preview...). Redirige `/` y `/inicio` a `/inicio/{tenant_id}` cuando matchea. 10/10 tests unitarios PASS.
- **DynamicLanding** aplica `primary_color` / `accent_color` vía CSS vars (override del tema base) y usa `custom_features`/`custom_steps` si existen, sino fallback al template.
- **Endpoint público `/api/public/catalog/{tenant_id}`** ahora retorna también: `primary_color`, `accent_color`, `hero_bg_url`, `custom_features`, `custom_steps`.
- **Bug HIGH fixado** (testing agent iter_9): `GET /tenant/branding` devolvía `''` para `custom_features`/`custom_steps` cuando no existían → ahora devuelve `[]`.
- **Testing 100% PASS (11/11 + frontend E2E):** `/app/test_reports/iteration_9.json`

### 2026-04-28 (Sesión Anterior - Landing Dinámica por Tenant)
- **Landing dinámica `/inicio/:tenantId`** con copy adaptado por `template_id`:
  - 5 plantillas: `inmobiliaria`, `clinica`, `restaurante`, `ecommerce`, `servicios` (en `/app/frontend/src/data/landingTemplates.js`).
  - Cada plantilla define: hero_title (función con businessName), subtitle, CTA WhatsApp, 3 features con íconos, 3 steps de "cómo funciona".
  - `/inicio` sin tenant → landing genérica del SaaS InmoBot ("el bot inteligente para tu negocio").
- **Backend:** `GET /api/public/catalog/{tenant_id}` ahora retorna `template_id`, `logo_url` (con fallback a `bot_config.template_id` o `'servicios'`).
- **Branding:** Footer muestra "Powered by InmoBot" en cada landing de tenant. La marca InmoBot queda como bot platform genérica.
- **Reemplaza `/inicio` antiguo** (era hardcoded inmobiliaria) por componente dinámico `DynamicLanding.js`.

### 2026-04-28 (Sesión Anterior - Backlog: Rate-limit + Attribution + auto-resize + refactor)
- **Rate-limit en `/api/public/catalog/{tenant_id}/track`:** Sliding window en memoria (deque). 30 reqs/60s por IP+tenant; 429 si excede. _Nota:_ in-memory ⇒ válido sólo single-instance.
- **iframe auto-resize:** PublicCatalog (con `?embed=1`) emite `postMessage({type:'inmobot-resize', tenant, height})` con ResizeObserver. widget.js drop-in escucha y ajusta el iframe al contenido.
- **🌟 Lead Attribution Engine:** Lead que llega por WhatsApp con click_whatsapp <30min se marca con `source='widget'`, `referring_product_id`, `widget_session_id` y emite event `lead_generated`. UI muestra "Leads del widget / Total / Share %".
- **Refactor adicional:** `routers/templates.py` extraído.
- **Bugs HIGH fixados** (testing agent iter_7): `lead.source` ya no se sobreescribe por save_lead; `NameError updated_lead` en branch generic_flow resuelto.
- **Testing 100% PASS (19/20 backend - 1 skip intencional):** `/app/test_reports/iteration_8.json`

### 2026-04-28 (Sesión Anterior - Widget Tracking + SuperAdmin Dashboard)
- **🌟 Widget Conversion Tracking (sugerencia SaaS implementada):**
  - Servicio `widget_analytics_service.py` con eventos: `view`, `click_product`, `click_whatsapp`, `ai_search`, `lead_generated`. IP hasheada (SHA256 truncado, no PII).
  - Endpoint público `POST /api/public/catalog/{tenant_id}/track` (sin auth). 404 si tenant inactivo/inexistente.
  - Endpoint admin `GET /api/widget/analytics?days=30`: KPIs (vistas, únicos, clicks, IA, leads), CTR, conversion rate, by_day, top_products, top_queries.
  - Endpoint superadmin `GET /api/superadmin/widget/analytics`: rollup global por tenant.
  - Tracking integrado en `PublicCatalog.js` (view 1x/sesión, click_product, click_whatsapp, ai_search).
  - Página `/catalogo/analytics` con KPIs cards, snippet drop-in copiable, top productos/búsquedas, actividad diaria.
- **Widget.js Drop-in:**
  - `GET /api/public/catalog/{tenant_id}/widget.js` retorna JS que crea iframe auto-resizable.
  - Respeta `x-forwarded-proto` para HTTPS detrás del ingress, Cache-Control 5min, CORS abierto.
  - Uso: `<div id="inmobot-catalog"></div><script src=".../widget.js" async></script>`
- **SuperAdmin Dashboard Global:**
  - `GET /api/superadmin/metrics`: MRR, ARR, distribución por plan, churn rate 30d, overage total, revenue 30d, leads totales.
  - `GET /api/superadmin/tenants/usage`: tabla de uso del periodo por tenant.
  - Bloque "Global SaaS Metrics" añadido al inicio de SuperAdminPanel (5 cards: MRR, Activos, Churn, Overage, Revenue 30d).
- **Routers nuevos:** `routers/widget.py`, `routers/superadmin.py` (refactor pattern continuado).
- **Testing 100% PASS (22/22 + frontend E2E):** `/app/test_reports/iteration_6.json`

### 2026-04-28 (Sesión Anterior - Backlog + Sugerencia SaaS)
- **Backlog completados:**
  - **Bulk-write backfill** de `product_id` en `catalog_service.get_products` (1 op vs N ops).
  - **Router metrics.py** extraído: 5 endpoints (`/metrics/leads-by-day`, `/leads-by-status`, `/leads-by-intent`, `/conversion-funnel`, `/messages`).
  - **AI Recommendations** en `LLMService.recommend_products` + integración en `generic_flow._handle_catalog_request` (envía carrusel personalizado si LLM habilitado + lead tiene contexto).
- **Nueva Feature: Catálogo Público Embebible:**
  - `GET /api/public/catalog/{tenant_id}` (sin auth) retorna tenant info + products (sin tenant_id leak) + categorías. 404 si tenant no existe.
  - `POST /api/public/catalog/{tenant_id}/recommend` recomendaciones IA públicas.
  - `POST /api/catalog/recommend` (auth) para preview desde dashboard admin.
  - **React widget** `/p/catalogo/:tenantId`: página pública embebible con buscador IA, filtros, grid, CTA WhatsApp, modo embed (`?embed=1`), document.title con branding.
  - **UI dashboard** en `CatalogPage.js`: nuevo `catalog-pro-panel` con link público copiable + preview IA inline.
- **Testing 100% PASS** (21/21 iter_5 + regresión): `/app/test_reports/iteration_5.json`

### 2026-04-27 (Sesión Anterior - Action Items + Refactor)
- **Action Items completados:**
  - **product_id UUID:** Catalog migrado a `product_id` UUID. Backfill automático en `get_products` para productos legacy. Endpoints PUT/DELETE `/api/catalog/{product_id}` ahora usan UUID. Frontend (`CatalogPage.js`) actualizado.
  - **Cross-tenant validation:** `POST /api/catalog/send/{phone}` rechaza con 403 si el phone pertenece a otro tenant.
  - **Cron de overage:** `scheduler.py` agrega task `bill_monthly_overage` (corre día 1-3 a las 04:00 UTC, idempotente con `last_run_period`).
  - **Refactor a routers:** Extraídos a `/app/backend/routers/`:
    - `routers/catalog.py` (6 endpoints)
    - `routers/billing.py` (7 endpoints)
  - `server.py` reducido de 1908 → 1729 líneas (-179 líneas).
  - Bug pre-existente arreglado: `/api/leads/stats/summary` retornaba 500 cuando `avg_score=None` (sin leads con score).
- **Testing 100% PASS (29/29 backend + UI E2E):** ver `/app/test_reports/iteration_4.json`
- **Pattern establecido:** Más routers extraíbles en futuro (leads, metrics, broadcast, agents).

### 2026-04-27 (Sesión Anterior - Catálogo + Overage Billing)
- **P0 Catálogo de Productos (COMPLETADO):**
  - Backend CRUD `/api/catalog` (GET/POST/PUT/DELETE) con tenant isolation estricto
  - `/api/catalog/categories` lista categorías únicas del tenant
  - `/api/catalog/send/{phone}` envía catálogo/producto a WhatsApp como Interactive Message (List o Carrusel-Buttons según cantidad)
  - **Bot integration en `generic_flow.py`:**
    - `CATALOG_KEYWORDS`: detecta mensajes "catalogo", "productos", "mostrame", "menu", "ofertas", etc.
    - `_handle_catalog_request`: envía automáticamente Interactive Message con productos del tenant
    - `_handle_product_selection`: detecta IDs `prod_*` / `product_*` y responde con detalle del producto + CTA buttons
  - UI `/catalogo` (CatalogPage.js): grid de productos, filtros por categoría/búsqueda, modal CRUD
- **P1 Overage Billing en Stripe (COMPLETADO):**
  - `payment_service.bill_overage_for_tenant(tenant_id, period)`: crea `stripe.InvoiceItem` con el costo de overage del periodo
  - `payment_service.bill_all_overages(period)`: itera tenants activos. Si día <=3 del mes, factura el mes anterior (cron-friendly).
  - Idempotencia: marca `overage_billed=true` en `usage` para no facturar dos veces
  - Endpoint `POST /api/billing/bill-overage` (solo superadmin) con body opcional `{period, tenant_id}`
- **Testing 100% PASS (21/21 backend + UI E2E):** ver `/app/test_reports/iteration_3.json`
- **Refactor pendiente:** dividir `server.py` (1900+ líneas) en routers → backlog

### 2025-02-12 (Sesión Anterior)
- **Tarea Completada:**
  - Generación de Propuesta Comercial en PDF (`/app/docs/PROPUESTA_COMERCIAL.pdf`)
  - Script Python con ReportLab para convertir MD a PDF profesional
  - PDF incluye: portada, tablas de funcionalidades, comparativa de planes, ROI, proceso de implementación
  - **Precios actualizados a licencia exclusiva:** $10,000 (Completo) / $18,000 (Premium)
  - **Sección de Términos de Licencia agregada** con detalles de exclusividad, entrega, soporte y costos post-venta
- **Documentación para el Comprador:**
  - `/app/docs/MANUAL_COMPRADOR.md` - Manual completo (844 líneas) con:
    - Arquitectura del sistema
    - Deploy en Railway y DigitalOcean
    - Configuración de todas las integraciones
    - Personalización del bot
    - Mantenimiento y actualizaciones
    - Solución de problemas
  - `/app/docs/GUIA_RAPIDA.md` - Setup en 30 minutos
  - `/app/docs/FAQ.md` - Preguntas frecuentes (220 respuestas)
- **Documentos de Venta Disponibles:**
  - `/app/docs/PROPUESTA_COMERCIAL.md` (versión markdown)
  - `/app/docs/PROPUESTA_COMERCIAL.pdf` (versión PDF profesional)
  - `/app/docs/MENSAJES_VENTA.md` (mensajes cortos para contactar compradores)
- **Estado:** El foco del usuario es la venta de la aplicación, no nuevas funcionalidades

### 2026-02-10 (Sesión Anterior - Parte 3)
- **Nuevas Funcionalidades Implementadas:**
  - **Acciones Masivas en Leads:** Checkboxes para seleccionar múltiples leads y ejecutar acciones (tag, status, asignar, eliminar)
  - **Página de Historial de Auditoría:** Nueva ruta /auditoria con timeline de todas las acciones del sistema
  - **Página de Broadcast:** Nueva ruta /broadcast para enviar mensajes masivos por WhatsApp con filtros
  - Navegación actualizada con enlaces a Broadcast (📢) y Auditoría (📜)
- **Testing completado:** 100% tests pasados en iteration_2.json

### 2026-02-10 (Sesión Actual - Parte 2)
- **Mejoras de UI/UX:**
  - Sidebar colapsable con botón para expandir/contraer
  - Logo real del InmoBot en el sidebar
  - Favicon y título de página actualizados
  - Corrección del Kanban que se superponía con el sidebar
  - Estado del sidebar persiste en localStorage

### 2026-02-10 (Sesión Actual - Parte 1)
- **Vista Kanban integrada completamente:**
  - Agregado enlace "Pipeline (Kanban)" en navegación lateral
  - Corregido orden de rutas en backend (/leads/kanban antes de /leads/{phone})
  - 8 columnas de estados: Nuevos, Contactados, Calificados, Cita Agendada, Calientes, Tibios, Fríos, Cerrados
  - Drag & drop funcional para mover leads entre estados
  - Estilos CSS completos para el Kanban
- **Testing completado:**
  - 100% tests pasados en backend y frontend
  - Verificada generación de reportes PDF
  - Verificada calculadora ROI
  - Verificado login y autenticación

### Sesión Anterior (Completado)
- Bot WhatsApp funcional con IA
- Dashboard completo con métricas
- Calendario de citas
- Notificaciones con sonido
- Sistema de etiquetas
- Integración Stripe
- Página de precios
- Página de demo interactiva
- Video demo incrustado
- Modo oscuro
- Email de bienvenida automático
- Dominio personalizado (inmobot-ia.com)

---

## Roadmap

### P0 (Crítico) - COMPLETADO
- [x] Bot de WhatsApp funcional
- [x] Dashboard de leads
- [x] Integración Stripe
- [x] Página de precios
- [x] Video demo incrustado
- [x] Vista Kanban integrada
- [x] Sidebar colapsable
- [x] Acciones masivas en leads (UI)
- [x] Historial de auditoría (UI)
- [x] Mensajes broadcast (UI)
- [x] Propuesta comercial PDF para venta
- [x] Catálogo + Carruseles WhatsApp (UI + bot integration)
- [x] Facturación de overage de IA en Stripe (InvoiceItem)

### P1 (Alto) - Pendiente
- [ ] Tareas programadas (scheduler) - Testing real con citas
- [ ] Encuestas NPS en el bot
- [ ] Seguimiento post-visita automático

### P2 (Medio) - Futuro
- [ ] Alertas Push en navegador
- [ ] Calculadora ROI interactiva en dashboard
- [ ] Testimonios reales
- [ ] Más integraciones CRM
- [ ] App móvil

---

## Technical Architecture

```
/app
├── backend/
│   ├── server.py (FastAPI)
│   ├── bot_flow.py (WhatsApp bot logic)
│   ├── models.py (Pydantic models)
│   ├── scheduler.py (Tareas programadas)
│   └── services/
│       ├── llm_service.py (GPT)
│       ├── audio_service.py (Whisper)
│       ├── payment_service.py (Stripe)
│       └── email_service.py (Resend)
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Demo.js (con video)
│       │   ├── Pricing.js
│       │   ├── Dashboard.js
│       │   ├── Calendar.js
│       │   ├── KanbanView.js (Pipeline)
│       │   └── Login.js
│       └── components/
└── docs/
    └── GUION_VIDEO_DEMO.md
```

## Key Endpoints
- `POST /api/webhook` - WhatsApp messages
- `GET /api/leads` - List leads
- `GET /api/leads/kanban` - Kanban board data (8 columns)
- `PUT /api/leads/{phone}/status` - Update lead status (drag & drop)
- `POST /api/create-checkout-session` - Stripe checkout
- `GET /api/reports/pdf` - Generate PDF report
- `GET /api/calculator/roi` - ROI calculations
- `WS /api/ws/notifications` - Real-time notifications

## Credentials
- Email: `admin@inmobot.com`
- Password: `Admin123!`

## Integrations (Self-Hosted - Requiere API Keys del comprador)
- **OpenAI GPT-4 / Whisper:** Respuestas inteligentes y transcripción de audio (SDK directo `openai`)
- **Meta WhatsApp Cloud API:** Comunicación del bot
- **Stripe:** Procesamiento de pagos (SDK directo `stripe`)
- **Resend:** Emails transaccionales
- **MongoDB Atlas:** Base de datos en la nube (guía paso a paso incluida en docs)
- **Cloudflare:** DNS, redirecciones, routing de email

## Estado de Entrega del Código
- **BD:** Completamente vacía (0 usuarios, 0 leads). El comprador ejecuta `init_admin.py` para crear su admin.
- **`.env` backend:** Todas las keys vacías. El comprador configura sus propias credenciales.
- **`.env` frontend:** `REACT_APP_LANDING_MODE=inmobiliaria` por defecto. El comprador personaliza nombre, tagline y WhatsApp.
- **Landing dual:** Variable `REACT_APP_LANDING_MODE` alterna entre `venta` (para inmobot-ia.com) e `inmobiliaria` (para el comprador).
- **Opciones de deploy:** Railway (1-click), Docker Compose, DigitalOcean manual. Documentado paso a paso.
- **Archivos de deploy:** `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `railway.json`, `setup.sh`
- **Documentación:** MANUAL_COMPRADOR.md incluye guía paso a paso de MongoDB Atlas, personalización de landing, Railway detallado y Docker


## Arquitectura Multi-Tenant (SaaS)
- **Modelo:** Multi-tenant con `tenant_id` en todas las colecciones
- **Roles:** `superadmin` (dueño SaaS) → `admin` (dueño inmobiliaria) → `asesor`
- **Tenant isolation:** Todas las queries filtran por `tenant_id`. Superadmin ve todo.
- **Webhook routing:** Identifica tenant por `whatsapp_phone_number_id` del mensaje entrante
- **Endpoints de gestión:** POST/GET/PUT/DELETE `/api/auth/tenants` (solo superadmin)
- **Init:** `init_admin.py` crea superadmin + tenant de ejemplo opcional
- **OpenAI:** UNA sola key del dueño del SaaS para todos los clientes

## Billing con Stripe Subscriptions (Fase 4)
- 3 planes: Basic ($49/mes), Pro ($99/mes), Enterprise ($249/mes)
- Checkout con Stripe en modo `subscription` (recurrente mensual)
- Webhooks para: checkout completado, invoice pagada, pago fallido, suscripción actualizada/cancelada
- Auto-actualiza `subscription_status` y límites del tenant según el plan
- Endpoints: `POST /api/billing/subscribe`, `GET /api/billing`, `POST /api/billing/cancel`
- UI: Sección "Facturación y Plan" en Configuración con plan actual, status, límites, historial de pagos, y comparador de planes
- 5 templates disponibles: inmobiliaria, clinica, restaurante, servicios, ecommerce
- Cada template define: flujo de preguntas, botones, scoring, labels, mensajes, FAQ
- Motor genérico (`generic_flow.py`) procesa cualquier template
- Motor legacy (`bot_flow.py`) mantiene compatibilidad con inmobiliarias
- Endpoint público `GET /api/templates` lista todos los rubros
- Leads usan `custom_fields` (dict genérico) en vez de campos hardcodeados

## Flujo Configurable desde Dashboard (Generalización B)
- Editor visual en `/flujo`: Editar preguntas, tipo (texto/botones), campo, IA toggle y prompt
- Agregar/eliminar/reordenar pasos
- Editor de scoring: reglas custom con campo, condición, valor, puntos
- Editor de mensajes: bienvenida, cita, confirmación, labels
- "Restaurar template" para volver al flujo base del rubro
- Config custom en `bot_config` por tenant (sobreescribe template base)
- Endpoints: `GET/PUT /api/flow/config`, `POST /api/flow/reset`

