# InmoBot - Bot de WhatsApp con IA para Inmobiliarias

<div align="center">

![InmoBot Logo](frontend/public/logo.png)

**Automatiza la captación y calificación de leads inmobiliarios con Inteligencia Artificial**

[![React](https://img.shields.io/badge/React-18.x-61DAFB?logo=react)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-6.x-47A248?logo=mongodb)](https://mongodb.com/)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Business%20API-25D366?logo=whatsapp)](https://business.whatsapp.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-412991?logo=openai)](https://openai.com/)

[Demo en Vivo](https://app.inmobot-ia.com/demo) • [Documentación](#documentación) • [Instalación](#instalación-rápida)

</div>

---

## ✨ Características

### 🤖 Bot de WhatsApp Inteligente
- **Respuestas 24/7** con GPT-4
- **Calificación automática** de leads (score 0-12)
- **Multi-intención:** Compra, alquiler, venta e inversión
- **Agendamiento automático** de citas y tasaciones
- **Seguimiento inteligente** de leads inactivos

### 📊 Dashboard de Gestión
- **Vista Kanban** del pipeline de ventas
- **Métricas en tiempo real** (conversión, ROI, leads/día)
- **Calendario integrado** de citas
- **Acciones masivas** sobre leads
- **Exportación** a CSV y PDF
- **Notificaciones** en tiempo real con sonido

### 💰 Funcionalidades Comerciales
- **Integración Stripe** para cobros
- **Planes de suscripción** configurables
- **Calculadora ROI** interactiva
- **Landing page** lista para captar clientes

---

## 🖼️ Screenshots

<div align="center">
<table>
<tr>
<td><img src="docs/screenshots/dashboard.png" alt="Dashboard" width="400"/></td>
<td><img src="docs/screenshots/kanban.png" alt="Kanban" width="400"/></td>
</tr>
<tr>
<td align="center"><b>Dashboard Principal</b></td>
<td align="center"><b>Pipeline Kanban</b></td>
</tr>
</table>
</div>

---

## 🚀 Instalación Rápida

### Prerequisitos

- Node.js 18+
- Python 3.11+
- MongoDB (Atlas o local)
- Cuentas en: Meta Business, OpenAI, Stripe

### 1. Clonar repositorio

```bash
git clone https://github.com/tu-usuario/inmobot.git
cd inmobot
```

### 2. Configurar Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Configurar Frontend

```bash
cd frontend

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env
# Editar .env con la URL del backend
```

### 4. Iniciar servicios

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 - Frontend
cd frontend
npm start
```

### 5. Acceder

- **Dashboard:** http://localhost:3000
- **API:** http://localhost:8001/docs
- **Usuario:** admin@inmobot.com
- **Password:** Admin123!

---

## ⚙️ Configuración

### Variables de Entorno - Backend

```env
# Base de datos
MONGO_URL=mongodb+srv://usuario:password@cluster.mongodb.net/inmobot_db
DB_NAME=inmobot_db

# Seguridad
APP_SECRET=tu_clave_secreta_larga
CORS_ORIGINS=http://localhost:3000

# WhatsApp Business API
WHATSAPP_PHONE_NUMBER_ID=tu_phone_id
WHATSAPP_ACCESS_TOKEN=tu_access_token
WHATSAPP_BUSINESS_ACCOUNT_ID=tu_business_id
WEBHOOK_VERIFY_TOKEN=tu_verify_token

# OpenAI
OPENAI_API_KEY=sk-tu-api-key

# Stripe
STRIPE_API_KEY=sk_live_tu_stripe_key

# Emails
RESEND_API_KEY=re_tu_resend_key
NOTIFICATION_EMAILS=admin@tuempresa.com
```

### Variables de Entorno - Frontend

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## 📁 Estructura del Proyecto

```
inmobot/
├── backend/
│   ├── server.py           # Servidor FastAPI
│   ├── models.py           # Modelos Pydantic
│   ├── api.py              # Endpoints REST
│   ├── scheduler.py        # Tareas programadas
│   ├── bot/
│   │   ├── bot_flow.py     # Flujos de conversación
│   │   ├── handlers.py     # Manejadores de mensajes
│   │   └── llm_service.py  # Integración OpenAI
│   └── services/
│       ├── email_service.py
│       └── payment_service.py
│
├── frontend/
│   ├── src/
│   │   ├── pages/          # Páginas (Dashboard, Leads, etc.)
│   │   ├── components/     # Componentes reutilizables
│   │   └── App.js          # Aplicación principal
│   └── public/
│
└── docs/                   # Documentación
    ├── MANUAL_COMPRADOR.md
    ├── GUIA_RAPIDA.md
    └── FAQ.md
```

---

## 🔌 API Endpoints

### Autenticación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Iniciar sesión |
| POST | `/api/auth/register` | Registrar usuario |

### Leads
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/leads` | Listar todos los leads |
| GET | `/api/leads/kanban` | Leads agrupados por estado |
| GET | `/api/leads/{phone}` | Detalle de un lead |
| PUT | `/api/leads/{phone}/status` | Actualizar estado |
| DELETE | `/api/leads/{phone}` | Eliminar lead |

### WhatsApp
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET/POST | `/api/webhook` | Webhook de WhatsApp |
| POST | `/api/send-message` | Enviar mensaje |

### Reportes
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/reports/pdf` | Generar reporte PDF |
| GET | `/api/calculator/roi` | Calcular ROI |

### Pagos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/create-checkout-session` | Crear sesión Stripe |
| POST | `/api/stripe/webhook` | Webhook de Stripe |

---

## 🚢 Deploy en Producción

### Opción 1: Railway (Recomendado)

1. Conectar repositorio a Railway
2. Crear servicio MongoDB
3. Crear servicio Backend (root: `backend`)
4. Crear servicio Frontend (root: `frontend`)
5. Configurar variables de entorno
6. Conectar dominio personalizado

### Opción 2: DigitalOcean

Ver guía completa en `docs/MANUAL_COMPRADOR.md`

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [MANUAL_COMPRADOR.md](docs/MANUAL_COMPRADOR.md) | Guía completa de instalación y mantenimiento |
| [GUIA_RAPIDA.md](docs/GUIA_RAPIDA.md) | Setup en 30 minutos |
| [FAQ.md](docs/FAQ.md) | Preguntas frecuentes |
| [templates-whatsapp.md](docs/templates-whatsapp.md) | Plantillas de mensajes |

---

## 🛠️ Tecnologías

| Categoría | Tecnología |
|-----------|------------|
| **Frontend** | React 18, TailwindCSS, Chart.js |
| **Backend** | Python 3.11, FastAPI, Pydantic |
| **Base de datos** | MongoDB |
| **IA** | OpenAI GPT-4 |
| **Mensajería** | WhatsApp Business API |
| **Pagos** | Stripe |
| **Emails** | Resend / SMTP |

---

## 📄 Licencia

Este software se entrega bajo **licencia exclusiva**. El comprador tiene derecho a:
- ✅ Usar el software sin restricciones
- ✅ Modificar y personalizar el código
- ✅ Sublicenciar o revender

Ver términos completos en `docs/PROPUESTA_COMERCIAL.md`

---

## 🤝 Soporte

- **Email:** [tu-email@ejemplo.com]
- **WhatsApp:** [+XX XXX XXX XXXX]
- **Documentación:** [docs/](docs/)

---

<div align="center">

**InmoBot** - Convertí consultas en ventas, mientras dormís.

</div>
