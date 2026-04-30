# Load Tests con Locust

Tests de carga para validar la performance de InmoBot bajo tráfico realista.

## Setup

```bash
pip install locust
```

## Ejecución

### Modo Web UI (recomendado para análisis interactivo)
```bash
cd /app/load_tests
locust -f locustfile.py --host=https://inmobot-preview.preview.emergentagent.com
```

Abrí http://localhost:8089 y configurá:
- **Number of users**: 50 (subir gradualmente a 100)
- **Spawn rate**: 5 users/sec
- **Run time**: 5 minutos

### Modo CLI (para CI / scripts automatizados)
```bash
locust -f locustfile.py \
  --host=https://inmobot-preview.preview.emergentagent.com \
  --headless -u 50 -r 5 -t 5m --print-stats
```

## Targets (SLOs)

| Endpoint | p95 latencia | Tasa de error |
|---|---|---|
| `/api/health/ping` | < 200ms | 0% |
| `/api/health` | < 800ms | 0% (503 OK si Mongo degradado) |
| `/api/auth/login` | < 1500ms | < 1% (401 esperado en passwords inválidos) |
| `/api/auth/tenant/branding` | < 600ms | 0% |
| `/api/tenant/features-showcase` | < 500ms | 0% |

## Variables de entorno

- `LOAD_TEST_EMAIL`: email del usuario demo (default: `demo@inmobot.com`)
- `LOAD_TEST_PASSWORD`: password (default: `Demo123!`)

## Distribución de carga

- **80% Visitantes públicos** (peso=5): pings, landings, changelog, catálogos públicos.
- **20% Tenants autenticados** (peso=1): login + ciclo de dashboard típico.

## Métricas a monitorear durante el test

1. **Sentry** — buscar errores nuevos.
2. **MongoDB Atlas dashboard** — connections, ops/s, slow queries.
3. **Backend logs** — `tail -f /var/log/supervisor/backend.out.log | grep ERROR`.
4. **Locust dashboard** — fail rate, RPS, p95.

## Próximos pasos

- Programar este test en CI/CD antes de cada release significativo.
- Subir gradualmente la carga objetivo: 100 → 500 → 1000 usuarios concurrentes.
- Agregar test específico de webhooks de WhatsApp (carga de mensajes entrantes).
