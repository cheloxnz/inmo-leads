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

### 2025-02-12 (Sesión Actual)
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
