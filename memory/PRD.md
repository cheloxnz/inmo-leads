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

### 2026-04-29 (Sesión Actual - Iter24 - Feature Flags por tenant)
- **Sistema de Feature Flags multi-tenant** — patrón estándar SaaS B2B para personalizar funcionalidades por cliente sin forkear código.
- **Backend `/app/backend/feature_flags.py`** (nuevo módulo):
  - **Registry** central con 8 flags iniciales agrupados por categoría:
    - `bot`: `mortgage_calculator`, `voice_response_tts`, `ai_lead_summary`
    - `dashboard`: `advanced_analytics_export`
    - `integrations`: `salesforce_sync`, `custom_webhook_lead_hot`
    - `beta`: `priority_support`, `white_label`
  - Cada flag tiene `{key, label, description, category, default}`.
  - **Helpers:** `has_feature(tenant, name)` (acepta bool o dict como override), `get_tenant_features(tenant)` (devuelve estado efectivo de TODAS las flags), `update_tenant_feature(db, tid, name, enabled, config?)`.
- **Endpoints SuperAdmin (3 nuevos en `routers/superadmin.py`):**
  - `GET /api/superadmin/feature-flags/registry` — catálogo para construir UI.
  - `GET /api/superadmin/tenants/{tid}/features` — estado efectivo + raw_overrides.
  - `PUT /api/superadmin/tenants/{tid}/features` body `{feature, enabled, config?}` — validaciones: 400 si feature desconocida, 404 tenant. Escribe `audit_log` con `action="feature_flag_updated"` + email del superadmin.
- **`/api/auth/tenant/branding`** ahora incluye campo `features: dict` con todos los flags resueltos. Permite al frontend gateaer UI condicionalmente sin requerir endpoints adicionales.
- **Modelo `Tenant`** (en `models.py`): nuevo campo `features: dict = {}`.
- **UI SuperAdminPanel:**
  - Nuevo botón **"Feature Flags"** en cada `TenantCard` (junto a "Editar branding"), `data-testid="feature-flags-btn-{tid}"`.
  - Componente nuevo **`/app/frontend/src/components/TenantFeatureFlags.js`** que carga el registry + features del tenant en paralelo y renderiza switches agrupados por categoría con colores propios.
  - Cada flag muestra: label en negrita, descripción, key en monospace + botón toggle (estado "Activo" gradient morado / "Inactivo" outline). Toast al guardar. Persistencia inmediata.
- **Hook `/app/frontend/src/hooks/useFeature.js`** (nuevo):
  - `useFeatures()` → `{features, hasFeature, loading}` con cache módulo (1 fetch por sesión).
  - `useFeature(name)` → `{enabled, loading}` para checks granulares.
  - `invalidateFeaturesCache()` exportado y llamado desde `AuthContext.logout()` para evitar leak entre tenants.
- **CSS:** estilos `.sa-ff-*` (gradient violeta sutil, switches con feedback visual on/off, responsive). Tema dark soportado.
- **Tests:** Backend `test_iter24_feature_flags.py` 20/20 PASS:
  - Helper unit tests (5): default, truthy override, dict override, dict disabled, unknown.
  - `get_tenant_features` retorna todas las keys del registry.
  - Registry endpoint: 403 tenant, 401 sin auth, 200 superadmin con shape correcto.
  - GET tenant features: 403 tenant, 200 superadmin, 404 unknown tenant.
  - PUT toggle: 403 tenant, 400 unknown feature, 404 unknown tenant, 200 enable+persist, 200 disable, audit_log escrito.
  - Branding incluye features (todas las keys del registry, refleja overrides en vivo).
  - **Total backend acumulado: 92/92 PASS** (iter21+iter22+iter23+iter24+regression iter17-20).
  - Frontend E2E 100% (testing_agent_v3_fork iteration_23.json) — expand tenant → click FF button → toggle on/off + persistencia + reset.
- **Archivos:** `/app/backend/feature_flags.py` (nuevo), `/app/backend/routers/superadmin.py` (3 endpoints), `/app/backend/auth_routes.py` (features en branding), `/app/backend/models.py` (Tenant.features), `/app/frontend/src/components/TenantFeatureFlags.js` (nuevo), `/app/frontend/src/hooks/useFeature.js` (nuevo), `/app/frontend/src/pages/SuperAdminPanel.js` (botón + montaje), `/app/frontend/src/context/AuthContext.js` (cache invalidation on logout), `/app/frontend/src/App.css` (estilos `.sa-ff-*`), `/app/backend/tests/test_iter24_feature_flags.py` (nuevo).
- **Cómo agregar un nuevo flag** (para el agente futuro): (1) agregar entrada en `FEATURE_FLAGS` dict en `feature_flags.py`, (2) usar `has_feature(tenant, "tu_flag")` en backend o `useFeature("tu_flag")` en frontend para gateaer. La UI del SuperAdmin se actualiza sola.

### 2026-04-29 (Sesión Actual - Iter23 - Stripe Coupon Codes + Login genérico)
- **Stripe Coupon Codes para attribution nativa:**
  - **`commission_service._generate_referral_code(tenant_id)`**: genera código legible `PREFIX-XXXXXX` con charset sin chars confusos (excluye 0/O/1/I; conserva L). Prefijo del tenant_id slugified (max 6 chars), sufijo random de 6 chars cripto-seguros.
  - **`get_or_create_referral_code(db, tenant_id, create_in_stripe=True)`**: idempotente, retry x5 contra colisiones en mongo. Si STRIPE_API_KEY presente, crea lazy:
    1. `Coupon` global `INMOBOT_REFERRAL_5_PERCENT_OFF_FIRST_MONTH` (5% off primer mes, duration=once) — beneficio que el referido ve al pagar.
    2. `PromotionCode` mapeado al tenant via `metadata.referrer_tenant_id={tid}`.
    Best-effort: si Stripe falla, igual devuelve el código local + `stripe_enabled=false`.
  - **`find_referrer_by_promo_code`**: normaliza upper/strip, valida tenant active.
- **Endpoints nuevos:**
  - `GET /api/commissions/promo-code` (admin) → `{code, stripe_promotion_code_id, stripe_enabled}`.
  - `POST /api/commissions/resolve-promo` (público, body `{code}`) → `{valid, ref_tenant_id?, business_name?}`. Validaciones: 400 si vacío o >40 chars.
  - `GET /api/commissions/summary` ahora incluye `promo_code` en el response (1 request, no 2).
- **Webhook Stripe attribution via cupón:**
  - `PaymentService._attribute_via_promo_code(session, tenant_id)`:
    1. Lee `session.total_details.breakdown.discounts[].discount.promotion_code` (Stripe lo expone tras checkout completado).
    2. Hace `stripe.PromotionCode.retrieve(promo_id)` y lee `metadata.referrer_tenant_id` (path principal).
    3. Fallback: busca el `code` string en nuestra DB via `find_referrer_by_promo_code`.
    4. Si encuentra referrer → setea `tenant.referred_by` y `tenant.referred_via_promo_code`.
    **No sobreescribe** si el tenant ya tiene `referred_by` (atribución congelada).
  - Llamado al inicio de `_handle_checkout_completed` para que la atribución quede grabada antes de cualquier webhook posterior.
- **Stripe Checkout Session ahora con `allow_promotion_codes=True`** — el campo "Add promotion code" aparece nativo en el form de pago.
- **Index Mongo:** `tenants.referral_code` unique parcial (solo cuando `referral_code` es string), evita full scan en lookups públicos.
- **UI `/config Programa de referidos`** — nueva tarjeta morada arriba del link:
  - `data-testid="rp-promo-card"` con header "Tu código de cupón" + badge "Stripe activo" si Stripe está conectado.
  - Código en monospace 1.5rem con border dashed morado, `user-select: all`.
  - Botón copiar `data-testid="rp-promo-copy-btn"` con feedback `¡Copiado!`.
  - Hint explicativo: "Tus referidos pueden ingresar este código directo al pagar en Stripe Checkout y reciben 5% off el primer mes. Vos seguís ganando $5/mes durante 12 meses por cada uno que active su plan. Funciona aunque pierdan el link."
- **Login refresh genérico:**
  - `/app/frontend/public/logo-generic.svg` (nuevo) — SVG inline 120x120 con chat bubble blanca, ojos morados, sonrisa, sparkle dorado, fondo gradient indigo→violet. Reemplaza el PNG hardcoded de "lead-manager".
  - Texto: "Bot de WhatsApp con IA para tu negocio" (era "Sistema de Gestión de Leads Inmobiliarios").
- **Tests:** Backend 23/23 iter23 PASS + 22/22 iter21+iter22 + 15/15 iter19 = **72/72 backend**. Frontend E2E 100% (testing_agent_v3_fork iteration_22.json — login text + SVG load + promo card + monospace + copy button + regression UTM/banner OK).
- **Archivos:** `/app/backend/commission_service.py` (helpers + lazy Stripe), `/app/backend/routers/commissions.py` (2 endpoints + summary extension), `/app/backend/payment_service.py` (`_attribute_via_promo_code` + `allow_promotion_codes`), `/app/backend/server.py` (index parcial), `/app/frontend/public/logo-generic.svg` (nuevo), `/app/frontend/src/pages/Login.js` (logo + tagline), `/app/frontend/src/components/ReferralProgramSection.js` (tarjeta promo), `/app/frontend/src/App.css` (estilos `.rp-promo-*`), `/app/backend/tests/test_iter23_stripe_coupons.py` (nuevo).

### 2026-04-29 (Sesión Actual - Iter22 - Retención + Atribución sobre Comisiones)
- **Email automático "Conseguiste un nuevo referido"** (`email_service.send_new_referral_commission`):
  - HTML branded (gradient verde) con headline "+$5/mes · 12 meses", grid de stats (crédito activo + referidos activos), nota especial cuando `is_capped` ("¡Tu suscripción es gratis!").
  - Disparado en `commission_service.create_commission_on_first_payment` tras `insert_one` cuando se crea la commission ACTIVE — best-effort (no bloquea flujo si falla SMTP).
  - Lookup automático del email del admin del referrer (`agents.role=admin AND active`).
  - Skip silencioso si SMTP no configurado.
- **Banner en `/marketing`** con "Llevás $X ahorrados en facturación gracias a referidos":
  - `data-testid="marketing-referral-savings-banner"`, gradient verde, sparkles icon, sublínea con `active_count` + estado `is_capped`.
  - Fuente: nuevo campo `commission_summary` en `GET /api/coach/effectiveness` (función `_commission_summary_for_marketing`) — devuelve `{active_count, capped_amount_usd, total_credited_usd, is_capped, plan_price_usd}`.
  - Visible solo si `active_count>0 OR total_credited_usd>0`.
  - CTA "Ver detalle" → `/config`.
- **Trial ending soon — Nudge + Email:**
  - `routers/coach.py`: `TRIAL_DURATION_DAYS=14`, `TRIAL_WARN_THRESHOLD_DAYS=3`. Helper `_trial_days_left(tenant)` retorna None si `subscription_status=active`, días restantes si está en trial, 0 si expiró.
  - Nuevo nudge `trial_ending_soon` (severity=high, `days_min=11`) agregado a `_CHECKS`. Mensaje contextual según días restantes (1, 2, 3 o 0 días).
  - Scheduler task `send_trial_ending_emails` (cada 24h): itera tenants con `_trial_days_left ≤3`, envía `send_trial_ending_soon` al admin email; dedupe via `email_logs` por `(email_type, days_left bucket)` para no enviar 2 veces el mismo aviso.
- **Email digest semanal** (`scheduler.send_weekly_digest_emails`):
  - Disparo: lunes 09:00 UTC, una vez por semana (`last_run_iso = now.strftime('%G-W%V')` evita duplicados).
  - Modo dev: env var `DIGEST_FORCE=1` para trigger inmediato.
  - Stats por tenant: leads_new (7d), leads_total, conversiones (hot/appointment/completed en 7d), ai_messages (collection `usage_log`), `referral_credit_capped_usd` + `referral_active_count`.
  - HTML responsive con grid 2 cols + bloque destacado verde para ahorro de referidos.
- **UTM tracking + atribución persistente:**
  - `ReferralProgramSection.js`: el link copiable ahora incluye `?ref={tenant_id}&utm_source=referral&utm_medium=link&utm_campaign=tenant_share`.
  - `Signup.js`: persiste `?ref=` + `utm_*` en `localStorage.inmobot_ref_attribution` con TTL 30 días. Si el usuario navega/recarga sin query string, lee del storage y mantiene atribución (badge "Te trajo X" sigue apareciendo). Tras conversión exitosa, limpia el storage para no contaminar futuros usuarios del mismo navegador.
- **EmailType enum** extendido: `NEW_REFERRAL_COMMISSION`, `TRIAL_ENDING_SOON`, `WEEKLY_DIGEST`.
- **Tests:** Backend `test_iter22_retention_emails.py` 10/10 PASS:
  - Effectiveness incluye commission_summary (shape + datos seed).
  - Email new commission disparado con SMTP configurado (mock); NO disparado sin SMTP.
  - `_trial_days_left` para 3 escenarios (active=None, mid-trial, expired=0).
  - Nudge `trial_ending_soon` creado solo en warning window con sub no-active.
  - EmailService expone los 3 nuevos métodos.
  - Combinado con iter21: 22/22 PASS. Regression iter17-20: 48/48 PASS. Frontend E2E: banner + UTM + Signup persistence todos validados.
- **Archivos:** `/app/backend/email_service.py` (3 métodos), `/app/backend/commission_service.py` (`_notify_referrer_new_commission`), `/app/backend/routers/coach.py` (trial helpers + nudge + commission_summary), `/app/backend/scheduler.py` (2 nuevas tasks), `/app/backend/models.py` (EmailType extendido), `/app/frontend/src/pages/MarketingEffectiveness.js` (banner), `/app/frontend/src/components/ReferralProgramSection.js` (UTM), `/app/frontend/src/pages/Signup.js` (persistencia), `/app/backend/tests/test_iter22_retention_emails.py` (nuevo).

### 2026-04-29 (Sesión Actual - Iter21 - Programa de Comisiones por Referidos)
- **Servicio `commission_service.py`**: lifecycle completo de comisiones por referidos.
  - **Reglas:** $5/mes por cada referido convertido y pagando, durante 365 días, topeado al 100% del precio del plan del referrer (`SUBSCRIPTION_PLANS[plan].price_monthly`).
  - **Estados:** `pending` (registrado, no pagó) → `active` (1ra factura paga) → `expired` (cumplió 365d) / `cancelled` (referido canceló).
  - **`is_self_referral(db, ref, email, ip)`**: anti-fraude triple — (1) email exacto coincide con un agent del referrer, (2) dominio corporativo no-free coincide (whitelist `gmail.com`, `yahoo.com`, etc. excluidos), (3) IP del signup matchea `audit_log` del referrer en últimas 24h.
  - **`create_commission_on_first_payment(db, referred_tenant_id)`**: idempotente por par `(referrer_tenant_id, referred_tenant_id)`. Si ya existía pending, la activa.
  - **`calculate_active_credit_for_tenant(db, referrer)`**: auto-expira las que vencieron + suma `amount_per_month_usd` de las activas + cap a `plan_price_usd`. Devuelve `{amount_usd, capped_amount_usd, plan_price_usd, plan_id, is_capped, active_count, breakdown[]}`.
  - **`cancel_commissions_for_referred`** + **`expire_due_commissions`** (cron 24h).
- **Stripe Webhooks (`payment_service.py`):**
  - `invoice.paid`: detecta 1ra factura paga (`prior_paid==0`) → si `tenant.referred_by`, llama `create_commission_on_first_payment`. Llama `_record_applied_commission` para distribuir el descuento facturado entre commissions activas (FIFO por `created_at`, suma a `total_credited_usd`, push a `applied_invoices`).
  - `invoice.upcoming`: ~1h antes del cobro, calcula `capped_amount_usd` del referrer y crea `stripe.InvoiceItem` con `amount=-int(round(amount*100))` cents (negativo = descuento).
  - `customer.subscription.deleted`: cancela commissions del referido.
- **Anti-fraude en onboarding (`routers/onboarding.py` L166-186):** captura IP via `request.client.host`, valida con `is_self_referral` antes de persistir `referred_by`. Si fraude detectado, log silencioso y no se persiste el ref.
- **Endpoint `GET /api/commissions/summary`** (admin): expone `{config: {amount_per_referral_usd, duration_days}, active_credit, total_lifetime_credit_usd, by_status, commissions[]}` enriquecido con `referred_business_name`, `applied_invoices_count`, fechas ISO.
- **Scheduler:** `run_commission_expiry` cada 24h marca como expired las que pasaron `expires_at`.
- **Indices Mongo (`server.py`):** `commissions.commission_id` unique, compuesto `(referrer_tenant_id, referred_tenant_id)` unique, `(referrer_tenant_id, status)`, `(status, expires_at)`.
- **UI `ReferralProgramSection.js`** (montado en `/config` debajo de Facturación):
  - Tres KPI cards: **Crédito activo este mes** (verde, capped o no), **Referidos activos**, **Total ahorrado histórico**.
  - **Banner de cap** (Sparkles): solo si `is_capped`, mensaje "¡Tu suscripción es gratis!".
  - **Link copiable**: `${origin}/signup?ref=${tenant_id}` con botones Copiar (toast inline `¡Copiado!`) y Compartir (navigator.share fallback a clipboard).
  - **Tabla de comisiones** con status pill (active/pending/expired/cancelled), $/mes, total acreditado, fecha de expiración + días restantes.
  - **Empty state** con icono Gift cuando `commissions.length === 0`.
  - SuperAdmin: `return null` (no aplicable a SuperAdmin).
- **Tests:** Backend 12/12 PASS (`/app/backend/tests/test_iter21_commissions.py`) — anti-fraud x3, lifecycle (create/idempotent/no-ref), credit cap (capped/not-capped/auto-expired), cancellation, summary endpoint shape + integration. Regression 48/48 (iter17-20). Frontend E2E 100%: rp-section visible para tenant admin, oculta para superadmin, KPIs/link/tabla/empty state OK. Único hallazgo cosmético: contraste del botón "Copiar" — corregido con `.rp-btn-primary` (background #6366f1).
- **Archivos:** `/app/backend/commission_service.py` (nuevo), `/app/backend/routers/commissions.py` (nuevo), `/app/backend/payment_service.py` (webhook hooks), `/app/backend/routers/onboarding.py` (anti-fraud), `/app/backend/scheduler.py` (expire job), `/app/backend/server.py` (indices + router), `/app/frontend/src/components/ReferralProgramSection.js` (nuevo), `/app/frontend/src/pages/Configuration.js` (mount), `/app/frontend/src/App.css` (estilos `.rp-*`), `/app/backend/tests/test_iter21_commissions.py` (nuevo).

### 2026-04-28 (Sesión Actual - Coach Effectiveness Dashboard)
- **Endpoint `GET /api/coach/effectiveness?days=N`** (admin):
  - **funnel agregado:** shares_explicit, preview_views, html_views, leads_captured, signups_converted.
  - **funnel_rates:** view_to_lead, lead_to_signup, share_to_view, overall_share_to_signup (clamped 100%, 1 decimal).
  - **by_platform:** breakdown twitter/linkedin/download.
  - **timeseries:** leads + converted por día YYYY-MM-DD via `$dateToString` (ascending).
  - **top_celebrations:** top 10 ordenadas por shares_total desc, con leads/converted por celebration.
  - **in_window:** counts limitados a la ventana temporal.
  - Query param `days` clamped 1..90 (default 30) con manejo robusto de TypeError/None/0.
- **Frontend `/marketing` (`MarketingEffectiveness.js`):**
  - 4 KPI cards (Compartidas, Vistas, Leads, Signups) con border-color por etapa.
  - Funnel visual con barras decrecientes proporcionales + porcentaje al siguiente paso (clamped 100%, sufijo `+` cuando overflow).
  - Time-series chart (recharts LineChart) con 2 líneas: leads y convertidos.
  - Platform breakdown (BarChart vertical horizontal) + iconos Twitter/LinkedIn/Download con counters.
  - Tabla "Top celebrations por impacto" con shares/vistas/leads/signups por celebration, sorted desc.
  - Selector de ventana 7d/30d/90d (`data-testid="window-selector"`) con refetch.
  - Estado de error con feedback al usuario (data-testid='marketing-error').
- **Nav sidebar:** nuevo link `🏆 Marketing` (`data-testid="nav-marketing"`) entre Landing y Auditoría.
- **Tests:** Backend 12/12 PASS (post-fix de `days=0` clamping). Frontend E2E 100%. Regression iter17+18+19+20: 47/48 → 48/48.
- **Archivos:** `/app/backend/routers/coach.py` (effectiveness endpoint), `/app/frontend/src/pages/MarketingEffectiveness.js` (nuevo), `/app/frontend/src/App.js` (route + nav link).

### 2026-04-28 (Sesión Anterior - Acquisition Loop sobre OG Share Pages)
- **Mini-form de captura de lead en el HTML público** (`/api/public/share/{tid}/{cid}`):
  - Form con input email + botón "Quiero mi bot" + script JS inline que POSTea a `/api/public/share/{tid}/{cid}/lead`.
  - Banner ámbar "✦ Te trajo {business_name}" (attribution visible al visitante).
  - Texto: "¿Querés un bot así para tu negocio? Probalo gratis 14 días. Sin tarjeta. Setup en 5 minutos."
  - Link secundario "o registrate completo ahora →" al wizard `/signup?ref={tid}&ref_celebration_id={cid}`.
- **Endpoint `POST /api/public/share/{tid}/{cid}/lead`** (público):
  - Validación email regex + max 200 chars + celebration debe existir (anti-abuse).
  - Si email ya es agent registrado → `{captured:false, reason:'already_registered'}`.
  - Upsert en collection `referral_leads`: `lead_id` UUID, `ref_tenant_id`, `ref_celebration_id`, `email` (lowercase), `ip`, `user_agent`, `created_at`, `converted_tenant_id`. Idempotente entre intentos no-convertidos.
  - Tracking via `BackgroundTasks`: bump `tenant.referral_stats.leads` (o `leads_repeat`).
- **Onboarding wizard acepta `ref` y `ref_celebration_id`:**
  - Si ref válido + tenant.active=true → persiste `referred_by` y `referred_via_celebration` en el tenant nuevo.
  - Tras crear el tenant: marca `referral_leads.converted_tenant_id` para email coincidente + bump `tenant.referral_stats.signups` del referrer.
  - Frontend `/signup?ref=...` muestra badge **"👤 Te trajo {business}"** (color ámbar) tras GET `/api/public/catalog/{ref}` para resolver el nombre.
- **Endpoint `GET /api/coach/referral-stats`** (admin):
  - Funnel completo: `shares_explicit`, `preview_views`, `html_views`, `leads_captured`, `signups_converted`, `tenant_signups_via_ref`, `conversion_rate` (clamped a 100%).
  - Permite al tenant medir el ROI de cada celebración compartida.
- **Hardening:** index compuesto `referral_leads (ref_tenant_id, email, converted_tenant_id)` evita full scan en upsert. `conversion_rate` clamped a 100% (edge case de leads borrados post-conversión).
- **Tests:** Backend iter19 15/15 PASS + 43/43 regression. Frontend E2E 100%. Cero bugs.
- **Archivos:** `/app/backend/routers/public_share.py` (form HTML + capture endpoint), `/app/backend/routers/onboarding.py` (ref+attribution+conversion tracking), `/app/backend/routers/coach.py` (referral-stats endpoint), `/app/backend/server.py` (indices), `/app/frontend/src/pages/Signup.js` (badge ref + envío ref en payload).

### 2026-04-28 (Sesión Anterior - OG Image meta tags + viralidad pasiva)
- **Endpoints públicos para preview automático en redes sociales:**
  - `GET /api/public/share/{tenant_id}/{celebration_id}.png` — renderiza PNG branded 1200x630 con Pillow + LiberationSans. Incluye gradient diagonal (primary→accent del tenant), card blanca, badge circular con inicial del celebration_type, título wrappeado a 3 líneas, métrica grande, business_name + "Hecho con InmoBot AI".
  - `GET /api/public/share/{tenant_id}/{celebration_id}` (sin `.png`) — HTML público con meta tags Open Graph + Twitter Card completas (`og:image:width=1200/height=630`, `twitter:card=summary_large_image`). Cuando el tenant pega esta URL en LinkedIn/X/WhatsApp/Slack/Discord, el crawler **previsualiza automáticamente la imagen branded** sin que el usuario tenga que adjuntar nada.
  - Hostname público detectado vía: env `PUBLIC_BASE_URL` > headers `X-Forwarded-Host/Proto` > `request.base_url` (fallback). Garantiza que `og:image` use la URL públicamente accesible (no host interno del cluster).
  - **ETag** basado en `sha1(title|metric|colors|business)` con conditional GET (304 Not Modified), `Cache-Control: public, max-age=3600, s-maxage=86400` (al menos a nivel backend; el ingress externo puede sobreescribir).
  - **Cache TTL 3600s** para PNG bytes en memoria. Render <100ms en caches hit, ~1-2s en cold (Pillow gradient pixel-by-pixel; aceptable con cache).
  - **Tracking via BackgroundTasks** (no bloquea response): cada GET incrementa `shares.preview_views` (PNG) o `shares.html_views` (HTML).
- **Frontend (`ShareCelebrationModal.js`):** nuevo botón **"Copiar link público"** (morado, destacado). Llama `navigator.clipboard.writeText(getPublicShareUrl())`. La URL copiada apunta al HTML (no al PNG) para que las redes lean meta tags. Twitter intent ahora incluye `&url=` con la URL pública (preview auto en X). Banner morado de tip de viralidad explica el flujo. Total 5 botones: Descargar / **Copiar link público** / Copiar imagen / X·Twitter / LinkedIn.
- **`coach.py`:** POST `/share` ahora devuelve `tenant_id` en `card_data` (necesario para construir la URL pública en frontend).
- **Tests:** Backend iter18 12/12 PASS — PNG/HTML endpoints, ETag conditional GET 304, X-Forwarded-Host honored, tracking shares incrementa, 404 missing celebrations. Regression iter12+13+16+17 32/32 PASS. Frontend E2E 100%.
- **Archivos:** `/app/backend/routers/public_share.py` (nuevo), `/app/backend/server.py` (router registered), `/app/backend/routers/coach.py` (tenant_id en card_data), `/app/frontend/src/components/ShareCelebrationModal.js` (copy public link + tip banner).

### 2026-04-28 (Sesión Anterior - Lifespan + share/marketing orgánico + SPA navigation + cache celebrations)
- **Marketing orgánico (share cards):** ShareCelebrationModal con canvas 1200x630 que renderiza la card branded del tenant (gradient primary→accent, emoji grande, título, métrica, business_name, "Hecho con InmoBot AI"). Botones: Descargar imagen, Copiar al clipboard, X/Twitter intent, LinkedIn intent.
  - Endpoint `POST /api/coach/celebrations/{id}/share` con body `{platform: twitter|linkedin|download|copy}`. Trackea `shares.{platform}` y `shares.total` en el doc + audit_log con `action='celebration_shared'`. Devuelve `card_data` con branding del tenant + `share_text` prellenado con hashtags `#SaaS #AI #WhatsApp #PyME`.
  - Validación: platform whitelist (fuera → `unknown`), 404 si celebration no existe.
- **FastAPI lifespan handler** (reemplaza `@app.on_event` deprecado): un único `@asynccontextmanager` para startup (indices, migración, scheduler) + shutdown (scheduler.stop, mongo.close). Sin warnings de deprecation.
- **`coach_nudges.created_at` y `dismissed_at` ahora BSON datetime** (consistencia + soporte TTL futuro). Migración one-shot al startup convierte legacy strings → datetime. Respuestas siguen exponiendo ISO string para JSON.
- **Cache `_detect_celebrations_for_tenant` TTL 60s** (`cache_util` namespace `celebrations_detected`): reduce N find_one por GET. Invalidación automática en dismiss para que la próxima detección vea el signal resuelto.
- **React Router Link en CTAs:** `CoachNudges` y `CoachCelebrations` usan `<Link to>` para URLs internas (SPA navigation sin reload), `<a target=_blank>` para externas.
- **Tests:** Backend iter17 9/9 PASS + 32/32 regression. Frontend E2E 100%. Cero bugs reportados.
- **Archivos:** `/app/backend/server.py` (lifespan), `/app/backend/routers/coach.py` (cache + share + BSON datetime), `/app/frontend/src/components/ShareCelebrationModal.js` (nuevo), `/app/frontend/src/components/CoachNudges.js` (Link), `/app/frontend/src/components/CoachCelebrations.js` (Link + share button + modal).

### 2026-04-28 (Sesión Anterior - TTL/Severity/visibilitychange/Mock tests/Celebrations)
- **TTL indexes en MongoDB:**
  - `coach_nudges.dismissed_at` con `expireAfterSeconds=90*86400` (90 días) — purge automático de nudges descartados.
  - `coach_celebrations.seen_at` con `expireAfterSeconds=30*86400` (30 días) — purge de celebraciones vistas.
  - Migración one-shot al startup: convierte `dismissed_at` legacy (string ISO) a BSON datetime para que el TTL aplique. Probado: 4 docs migrados live.
- **Severity Enum (`high|warn|info`)** en `routers/coach.py`. Validación defense-in-depth con fallback a `info` si check_fn devuelve valor inválido.
- **Sistema de Celebrations** (live metrics combinado con Coach):
  - 4 tipos: `whatsapp_connected`, `first_lead`, `branding_customized`, `first_ai_edit`. Cada uno con emoji, título festivo, body y CTA contextual.
  - Endpoint `GET /api/coach/celebrations` evalúa lazy en cada request y devuelve no-vistas. `POST .../seen` marca como vista. Idempotente por unique compound `(tenant_id, celebration_type)`.
  - Auto-trigger tras `dismiss` de nudge: si el signal subyacente está resuelto, crea celebración (mapping `whatsapp_unconfigured`→`whatsapp_connected`, etc.).
  - UI `CoachCelebrations.js`: gradient verde emerald/teal, emoji grande 3xl, sparkles icon, max 2 visibles a la vez, mark-seen sin reload, return null si vacío.
  - Integrado en Dashboard ARRIBA de CoachNudges para celebrar antes de nudgear.
- **`visibilitychange` listener** en `CoachNudges.js` y `CoachCelebrations.js`: refresca al volver a la pestaña sin requerir reload manual.
- **Tests E2E con OpenAI MOCKED via `respx`** (`test_iter16_llm_mocked.py`):
  - 9 tests usando FastAPI TestClient + respx interceptor del endpoint `chat.completions`.
  - Cubre: preview con LLM válido, JSON inválido → 502, OpenAI 5xx → 502, campos no-whitelist → invalid[], rate-limit 11vo=429, flow_ai truncate a 20 ops, apply path NO llama LLM (verificado por ausencia de mock match).
  - Sin gastar créditos OpenAI reales. Reproducible 100% en CI.
- **Tests:** Backend 9/9 iter16 + 35/36 regression (1 skip esperado). Frontend E2E 100%: dashboard renderiza celebraciones arriba de nudges, max 2, dismiss sin reload, visibilitychange OK.
- **Archivos:** `/app/backend/routers/coach.py` (Severity enum + celebrations), `/app/backend/server.py` (TTL indexes + migración), `/app/backend/tests/test_iter16_llm_mocked.py` (nuevo), `/app/frontend/src/components/CoachCelebrations.js` (nuevo), `/app/frontend/src/components/CoachNudges.js` (visibilitychange), `/app/frontend/src/pages/Dashboard.js` (integración).

### 2026-04-28 (Sesión Anterior - Smart Onboarding Coach + cache + truncate + ROUTES.md)
- **Smart Onboarding Coach (`/api/coach/*`):** sistema de nudges contextuales para retención del trial.
  - 4 tipos de nudges declarativos:
    - `whatsapp_unconfigured` (high, ≥1 día sin token de WhatsApp)
    - `no_leads_yet` (warn, ≥3 días con WhatsApp pero 0 leads)
    - `default_branding` (info, ≥5 días con colores/logo por defecto)
    - `ai_unused` (info, ≥7 días sin usar Asistente IA bot_config_ai/flow_ai)
  - Idempotencia: `(tenant_id, nudge_type, dismissed_at=None)` único activo por tipo. Tras dismiss, el mismo tipo SÍ puede recrearse.
  - Endpoints: `GET /api/coach/nudges`, `POST /api/coach/nudges/{id}/dismiss`, `POST /api/coach/run` (admin manual trigger).
  - Scheduler task `run_onboarding_coach` corre cada 6h sobre todos los tenants `active`.
  - Índice compuesto `coach_nudges (tenant_id, nudge_type, dismissed_at)` + unique `nudge_id`.
  - UI `CoachNudges.js` integrada en Dashboard (`/`): max 3 nudges visibles, severity styling (red/amber/blue), CTA contextual con icon, X dismiss sin reload, return null si no hay nudges (no contenedor vacío).
- **Cache util TTL (`cache_util.py`):** namespace dict + monotonic clock. Aplicado en `flow_ai.py` para `tenant.find_one` (TTL 60s), reduce carga si el endpoint se vuelve popular.
- **Truncate ops a 20 en flow_ai:** defensa ante respuestas LLM excesivas. `parsed.operations[:20]`, expone `preview.truncated=bool` y `preview.max_ops=20` para que la UI pueda alertar al usuario.
- **Documentación de rutas (`/app/backend/ROUTES.md`):** referencia completa de prefijos, foco en `/api/auth/tenant/branding` (común confusión por el prefix `/auth`). Incluye Coach, Asistentes IA, Onboarding, Rate-Limiting.
- **Tests:** Backend 10/10 passed (iter15) + 25/26 regression (1 skip esperado). Frontend E2E 100%: dashboard renderiza nudges con severity correcto, dismiss API integrado, idempotencia verificada.
- **Archivos:** `/app/backend/routers/coach.py` (nuevo), `/app/backend/cache_util.py` (nuevo), `/app/backend/ROUTES.md` (nuevo), `/app/backend/scheduler.py` (run_onboarding_coach task), `/app/backend/server.py` (router + indices), `/app/backend/routers/flow_ai.py` (cache + truncate), `/app/frontend/src/components/CoachNudges.js` (nuevo), `/app/frontend/src/pages/Dashboard.js` (integración).

### 2026-04-28 (Sesión Anterior - AI Flow Editor + Hardening completo + Onboarding stress)
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

