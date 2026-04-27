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

### 2026-04-27 (Sesión Actual - Action Items + Refactor)
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

