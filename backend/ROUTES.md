# InmoBot SaaS - API Routes Reference

> Última actualización: 2026-04-28
> Todas las rutas están bajo el prefijo `/api`. Frontend debe llamarlas con `${process.env.REACT_APP_BACKEND_URL}/api/...`.

## Convención de prefijos

| Prefijo                 | Source                                  | Ejemplos                                                  |
|-------------------------|-----------------------------------------|-----------------------------------------------------------|
| `/api`                  | `api_router` en `server.py`             | `/api/config`, `/api/flow/config`, `/api/leads`           |
| `/api/auth`             | `auth_router` (`auth_routes.py`)        | `/api/auth/login`, `/api/auth/me`, `/api/auth/tenant/branding` |
| `/api/catalog`          | `routers/catalog.py`                    | `/api/catalog/products`                                   |
| `/api/billing`          | `routers/billing.py`                    | `/api/billing/subscribe`, `/api/billing/portal`           |
| `/api/metrics`          | `routers/metrics.py`                    | `/api/metrics/leads`, `/api/metrics/funnel`               |
| `/api/widget`           | `routers/widget.py`                     | `/api/widget/track`                                       |
| `/api/superadmin`       | `routers/superadmin.py`                 | `/api/superadmin/dashboard`                               |
| `/api/templates`        | `routers/templates.py`                  | `/api/templates/list`                                     |
| `/api/uploads`          | `routers/uploads.py`                    | `/api/uploads/logo`                                       |
| `/api/onboarding`       | `routers/onboarding.py`                 | `/api/onboarding/auto-setup`                              |
| `/api/bot-config/*`     | `routers/bot_config_ai.py`              | `/api/bot-config/ai-edit`                                 |
| `/api/flow/*`           | `routers/flow_ai.py` (+ legacy en server.py) | `/api/flow/ai-edit`, `/api/flow/config`              |
| `/api/coach/*`          | `routers/coach.py`                      | `/api/coach/nudges`                                       |

---

## Tenant Branding (read + write de los settings de marca del tenant)

> ⚠️ La ruta correcta es **`/api/auth/tenant/branding`** porque el router de auth se monta con prefix `/auth`.
> Llamarla como `/api/tenant/branding` da 404.

### `GET /api/auth/tenant/branding`
**Auth:** Bearer token (cualquier usuario autenticado del tenant)

Devuelve los campos públicos de branding + información read-only de suscripción.

```json
{
  "tenant_id": "demo-inmobiliaria",
  "name": "Demo Inmobiliaria",
  "business_name": "Demo Inmobiliaria",
  "business_tagline": "...",
  "logo_url": "https://...",
  "primary_color": "#3b82f6",
  "accent_color": "#8b5cf6",
  "hero_bg_url": "",
  "template_id": "inmobiliaria",
  "contact_phone": "",
  "whatsapp_display_phone": "",
  "country": "AR",
  "custom_features": [],
  "custom_steps": [],
  "palette_warn_disabled": false,
  "subscription_plan": "basic",       // read-only
  "subscription_status": "active"      // read-only
}
```

### `PUT /api/auth/tenant/branding`
**Auth:** `require_admin` (admin del tenant)

Body acepta cualquier subset de los campos en `_BRANDING_ALLOWED_FIELDS` (ver `auth_routes.py` línea 372).
**No acepta** `subscription_plan` ni `subscription_status` (read-only en este endpoint).

---

## Asistentes IA

### `GET /api/bot-config/ai-edit/info` y `POST /api/bot-config/ai-edit`
Modifica `bot_config` (horarios, score handoff, mensaje de bienvenida).
Whitelist 9 campos. Rate-limit 10/h por tenant. Ver `routers/bot_config_ai.py`.

### `GET /api/flow/ai-edit/info` y `POST /api/flow/ai-edit`
Modifica el árbol del FlowBuilder (steps + welcome/completion/appointment messages).
7 operaciones whitelist. Rate-limit 8/h por tenant. Truncate a 20 ops por preview.
Cache de tenant lookup TTL 60s. Ver `routers/flow_ai.py`.

---

## Smart Onboarding Coach

### `GET /api/coach/nudges`
**Auth:** cualquier usuario autenticado.

Devuelve nudges activos (no descartados) del tenant. Tipos:
- `whatsapp_unconfigured` (high) — días ≥1 sin WhatsApp configurado
- `no_leads_yet` (warn) — días ≥3 sin leads, WhatsApp ya configurado
- `default_branding` (info) — días ≥5 con branding por defecto
- `ai_unused` (info) — días ≥7 sin usar Asistente IA

### `POST /api/coach/nudges/{nudge_id}/dismiss`
Marca un nudge como descartado. Idempotente.

### `POST /api/coach/run`
**Auth:** `require_admin`. Dispara el chequeo manualmente para el tenant actual.

> El scheduler corre el coach **cada 6 horas** automáticamente sobre todos los tenants activos.

---

## Onboarding (alta de tenant nuevo desde landing pública)

### `POST /api/onboarding/auto-setup`
Sin auth (público). Body: `{ business_name, description (>=20 chars), email, password (>=8) }`.
Genera tenant + admin + productos demo + token JWT.
Protegido contra race conditions con unique index sobre `tenants.tenant_id`.

---

## Health Check (interno)

### `GET /api/`
Health check.

### `GET /api/cache/stats` _(no expuesto público — futuro)_
Stats del cache TTL en memoria (`cache_util.py`).

---

## Rate-Limiting

Todos los endpoints AI usan `rate_limit.py` (Redis con fallback in-memory):
- `bot-cfg-ai:{tenant_id}` → 10/h
- `flow-ai:{tenant_id}` → 8/h
- `branding-ai-copy:{tenant_id}` → 5/h
- `widget-track` → más laxo, ver `routers/widget.py`

Cuando se excede: HTTP 429 con `detail: "Limite alcanzado (...). Reintentar en Ns"`.
El frontend parsea los segundos y muestra countdown en vivo.
