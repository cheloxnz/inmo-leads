# InmoBot AI - Sistema de Automatización WhatsApp para Inmobiliarias

Sistema completo de calificación automática de leads inmobiliarios vía WhatsApp con IA, diseñado para inmobiliarias en Argentina.

## 🚀 Características Principales

- ✅ **Bot WhatsApp 24/7** - Respuesta automática a consultas inmobiliarias
- ✅ **Calificación Inteligente** - Sistema de scoring automático (0-12 puntos)
- ✅ **IA Conversacional** - GPT-4o para entender lenguaje natural
- ✅ **Clasificación de Leads** - 🔥 Calientes / 🟡 Tibios / ❄️ Fríos
- ✅ **Agendamiento Automático** - Integración con Google Calendar
- ✅ **CRM Mínimo** - Sincronización con Google Sheets
- ✅ **Handoff Inteligente** - Derivación automática a asesores humanos
- ✅ **Dashboard Web** - Panel de control en tiempo real

## 🏗️ Arquitectura

### Stack Tecnológico

**Backend:**
- FastAPI (Python 3.11)
- MongoDB (base de datos)
- OpenAI GPT-4o (LLM)
- WhatsApp Cloud API
- Google Sheets API
- Google Calendar API

**Frontend:**
- React 19
- React Router
- Axios
- Shadcn UI Components
- Tailwind CSS

**Infraestructura:**
- n8n Cloud (orquestador)
- WhatsApp Business Platform

## 📋 Prerequisitos

### 1. WhatsApp Business Platform (Meta)

1. Crear cuenta en [Meta for Developers](https://developers.facebook.com)
2. Crear nueva App y habilitar WhatsApp Product
3. Obtener:
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_BUSINESS_ACCOUNT_ID`
   - `APP_SECRET`

### 2. Google Cloud (Sheets & Calendar)

1. Crear proyecto en [Google Cloud Console](https://console.cloud.google.com)
2. Habilitar APIs:
   - Google Sheets API
   - Google Calendar API
3. Crear Service Account
4. Descargar JSON de credenciales
5. Crear Google Sheet con estructura de Leads (ver documentación)
6. Compartir Sheet con el email del Service Account

### 3. Emergent LLM Key (OpenAI GPT-4o)

La clave universal ya está configurada:
```
EMERGENT_LLM_KEY=sk-emergent-d56Ea1b880aA7Cc762
```

## ⚙️ Configuración

### 1. Variables de Entorno

Editar `/app/backend/.env`:

```bash
# MongoDB (ya configurado)
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"

# LLM (ya configurado)
EMERGENT_LLM_KEY=sk-emergent-d56Ea1b880aA7Cc762

# WhatsApp Business API (COMPLETAR)
WHATSAPP_PHONE_NUMBER_ID=tu_phone_number_id
WHATSAPP_ACCESS_TOKEN=tu_access_token
WHATSAPP_BUSINESS_ACCOUNT_ID=tu_business_account_id
APP_SECRET=tu_app_secret
WEBHOOK_VERIFY_TOKEN=inmobiliaria_argentina_2026

# Google Services (COMPLETAR)
GOOGLE_SHEETS_CREDENTIALS_JSON='{"type":"service_account",...}'
GOOGLE_CALENDAR_CREDENTIALS_JSON='{"type":"service_account",...}'
```

### 2. Configurar Webhook en Meta Dashboard

1. Ir a configuración de WhatsApp en Meta Dashboard
2. Configurar webhook:
   - **URL:** `https://tu-dominio.com/api/webhook`
   - **Verify Token:** `inmobiliaria_argentina_2026`
3. Suscribirse a eventos: `messages`

### 3. Instalar Dependencias

```bash
# Backend
cd /app/backend
pip install -r requirements.txt

# Frontend
cd /app/frontend
yarn install
```

### 4. Iniciar Servicios

```bash
sudo supervisorctl restart backend frontend
```

## 📊 Flujo Conversacional

El bot sigue este flujo de 12 pasos:

1. **Welcome** - Saludo inicial
2. **Intent** - ¿Comprar / Alquilar / Inversión?
3. **Zone** - Zona o barrio de interés (+2 pts)
4. **Budget** - Presupuesto en USD (+2 pts)
5. **Property Type** - Depto / Casa / PH (+1 pt)
6. **Bedrooms** - Cantidad de ambientes
7. **Must Have** - Requisitos obligatorios (+1 pt)
8. **Urgency** - Nivel de urgencia (+0 a +3 pts)
9. **Financing** - Tipo de financiamiento (+1 pt)
10. **Scoring** - Cálculo automático
11. **Appointment** - Oferta de agendar cita
12. **Confirmation** - Confirmación y handoff

## 🎯 Sistema de Scoring

### Puntuación (0-12 puntos)

- Presupuesto definido: **+2**
- Zona definida: **+2**
- Tipo de propiedad: **+1**
- Requisitos específicos: **+1**
- Intención de compra: **+1**
- Financiamiento definido: **+1**
- Urgencia:
  - Urgente: **+3**
  - Próximo mes: **+2**
  - Próximos meses: **+1**
  - Solo mirando: **0**

### Clasificación

- 🔥 **Hot (Caliente)**: Score ≥ 7
- 🟡 **Warm (Tibio)**: Score 4-6
- ❄️ **Cold (Frío)**: Score ≤ 3

## 🤝 Reglas de Handoff a Humano

El lead pasa automáticamente a asesor cuando:

1. Score ≥ 7 (lead caliente)
2. Cita agendada confirmada
3. Completó el flujo exitosamente
4. Solicitud explícita de hablar con asesor

## 📱 Endpoints API

### WhatsApp Webhook

```
GET  /api/webhook  - Verificación de webhook
POST /api/webhook  - Recepción de mensajes
```

### Gestión de Leads

```
GET  /api/leads              - Listar leads
GET  /api/leads/{phone}      - Obtener lead específico
PUT  /api/leads/{phone}      - Actualizar lead
GET  /api/leads/stats/summary - Estadísticas
```

### Configuración

```
GET  /api/config  - Obtener configuración
PUT  /api/config  - Actualizar configuración
```

### Agentes

```
GET  /api/agents  - Listar agentes
POST /api/agents  - Crear agente
```

## 📖 Documentación Completa

La aplicación incluye documentación técnica completa en la sección **Documentación**:

- Arquitectura del sistema
- Blueprint de workflow n8n
- Estructura de Google Sheets
- Checklist de implementación
- Solución de problemas comunes

## 🧪 Testing

### Test Manual - Flujo Completo

1. Enviar mensaje desde WhatsApp al número configurado
2. Responder las preguntas del bot
3. Verificar scoring en dashboard
4. Confirmar creación en Google Sheets
5. Verificar evento en Google Calendar

### Test de API

```bash
# Test de backend
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
curl "$API_URL/api/"

# Ver estadísticas
curl "$API_URL/api/leads/stats/summary"
```

## 🛠️ Desarrollo

### Estructura del Proyecto

```
/app
├── backend/
│   ├── server.py           # FastAPI server
│   ├── models.py           # Modelos Pydantic
│   ├── whatsapp_service.py # WhatsApp API
│   ├── llm_service.py      # OpenAI GPT-4o
│   ├── bot_flow.py         # Flow manager
│   ├── scoring.py          # Scoring engine
│   ├── google_services.py  # Sheets & Calendar
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── App.css
│   │   └── pages/
│   │       ├── Dashboard.js
│   │       ├── Leads.js
│   │       ├── LeadDetail.js
│   │       ├── FlowVisualization.js
│   │       ├── Configuration.js
│   │       └── Documentation.js
│   └── package.json
└── README.md
```

## 🔒 Seguridad

- ✅ Verificación HMAC-SHA256 de webhooks
- ✅ Tokens de acceso seguros en variables de entorno
- ✅ CORS configurado
- ✅ Sin credenciales hardcodeadas

## 📈 Métricas Recomendadas

Monitorear en las primeras 72 horas:

- Conversaciones iniciadas / día
- Tasa de finalización del flujo
- Distribución de leads (hot/warm/cold)
- Tasa de agendamiento
- Score promedio
- Errores de API/webhook

## 🐛 Solución de Problemas

### Webhook no recibe mensajes
- Verificar URL pública accesible
- Verificar HTTPS con certificado válido
- Revisar configuración en Meta Dashboard

### Error 131047 - Ventana 24h expirada
- Usar templates aprobados fuera de ventana de 24h

### LLM no extrae información
- Ajustar system messages en `llm_service.py`
- Agregar más ejemplos específicos

### Google Sheets no se actualiza
- Verificar permisos del Service Account
- Verificar credenciales en .env

## 🎓 Recursos Adicionales

- [WhatsApp Business API Docs](https://developers.facebook.com/docs/whatsapp)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [n8n Documentation](https://docs.n8n.io)

## 📞 Soporte

Para consultas sobre la implementación, revisa la sección **Documentación** en el dashboard o consulta los archivos de código fuente que incluyen comentarios detallados.

---

**Desarrollado con Emergent AI** 🚀
