# InmoBot — Changelog público

> Listado de mejoras, nuevas funciones y fixes que vamos liberando.
> Si querés que te avisemos cuando salga algo grande, escribinos a soporte@inmobot.com.

---

## Abril 2026

### 🚀 Observabilidad y producción
- **Logs estructurados (JSON)**: ahora cada request lleva un `request_id` único que podés
  pasar a soporte para que rastreemos exactamente qué pasó en tu cuenta.
- **Health checks mejorados**: nuevo endpoint `/api/health/ping` ultra-liviano para que
  servicios de monitoreo (UptimeRobot, Pingdom) puedan validar uptime sin sobrecargar la base.
- **MongoDB Atlas**: migramos toda la base a Atlas con backups automáticos diarios y
  réplicas geográficas. **Tu data ahora es a prueba de balas.**
- **Monitoreo de errores en tiempo real (Sentry)**: detectamos cualquier error del backend
  o frontend en menos de 1 minuto. Nadie nos cuenta los problemas — los vemos solos.
- **Hardening de seguridad**: rate limiting por endpoint, headers HSTS/CSP/X-Frame-Options,
  límite de payload 5MB. **Tu cuenta y la de tus referidos están protegidas contra abusos.**

### 🤖 IA Lead Summary (premium)
- Resúmenes automáticos de conversaciones generados con GPT-4: narrativa del lead,
  urgencia (1-10), próximo paso recomendado, insights y señales de compra detectadas.
- Cache inteligente: 7 días de TTL pero invalida solo si la conversación creció.
- Disponible para clientes con plan premium. Activá tu trial desde Configuración.

### 🎁 Programa de Referidos con Cupones de Stripe
- Generamos un código de cupón único por cliente (ej. `INMOBOT-XXXXXX`).
- Cualquier referido tuyo ingresa el código en Stripe Checkout y recibe **5% off el primer mes**.
- Vos ganás **$5/mes durante 12 meses** por cada referido activo. Top: 100% del valor de tu plan.
- UTM tracking persistente: aunque el referido pierda el link, lo retenemos en `localStorage`.

### 📧 Emails automáticos
- **Email de bienvenida** al crear nuevo workspace.
- **Aviso de fin de trial** 1, 2 y 3 días antes (con dedupe).
- **Resumen semanal** con leads, conversiones y ahorro por referidos.
- **Notificación de nueva comisión** cuando un referido tuyo paga su primera factura.

### 🛠️ Feature Flags multi-tenant
- Sistema de feature flags por cliente (controlable desde panel SuperAdmin).
- Permite activar/desactivar funciones premium individuales sin tocar código.
- 8 flags iniciales: AI Lead Summary, voice TTS, Salesforce sync, white label y más.

---

## Marzo 2026

### 🎯 Marketing orgánico y viralidad
- **Open Graph image generator**: cuando compartís una "celebración" en redes,
  generamos automáticamente una imagen 1200×630 branded de tu negocio.
- **Captura de leads en share pages públicos**: el visitante puede dejar su email y se
  marca como `referral_lead` con atribución completa.
- **Marketing Effectiveness Dashboard** (`/marketing`): funnel completo de shares→vistas→leads→signups,
  desglose por plataforma (X/LinkedIn/download), top celebraciones por impacto.

### 🤖 AI Configuration Assistant
- Editá la configuración de tu bot en lenguaje natural. Ej: *"Cambiá el horario a 9-19hs y
  los sábados de 10 a 13"*. La IA traduce a JSON validado contra una whitelist de 9 campos.
- Flujo de 2 pasos (preview → apply) para que veas exactamente qué va a cambiar.

### 🤖 AI Flow Editor
- Editor visual de flujos de WhatsApp con asistente IA. *"Agregá un paso después del primero
  preguntando el presupuesto"* y la IA edita el árbol del FlowBuilder.

---

## Febrero 2026

### 🪄 Auto-Onboarding Wizard
- Setup en menos de 5 minutos: ingresás nombre del negocio, descripción y email.
  La IA detecta el rubro, genera tagline + features + steps de la landing, crea 3 productos demo
  y te loguea automáticamente.

### 🎨 Editor visual de landing
- Personalizá colores (con hints WCAG de contraste), logo, copy y custom features
  desde un editor con preview en tiempo real.
- Subida de logos hasta 2MB con validación de tipo.
- Generador de copy con IA: pegás una descripción y obtenés tagline + 3 features + 3 steps.

### 📦 Catálogo embebible
- Widget público de catálogo (`/p/catalogo/:tenantId`) embebible en cualquier sitio
  con un `<script>` drop-in.
- Recomendaciones IA contextuales para cada visitante.
- Tracking de conversiones widget→WhatsApp.

---

## Enero 2026

### 📱 Multi-tenant SaaS (lanzamiento)
- Arquitectura multi-tenant completa con aislamiento estricto por `tenant_id`.
- 3 planes: Basic ($49/mes), Pro ($99/mes), Enterprise ($249/mes).
- Stripe Subscriptions con webhooks completos (checkout, invoice, cancelación).
- 5 templates de bot por rubro (inmobiliaria, clínica, restaurante, ecommerce, servicios).

---

## Algo no funciona como esperás?

- **Email**: soporte@inmobot.com (respondemos en <4 hs hábiles).
- **Status page**: status.inmobot.com (próximamente).

---

¿Te gustaría una funcionalidad nueva? **Mandanos un email** o votala en el roadmap público
(coming soon).
