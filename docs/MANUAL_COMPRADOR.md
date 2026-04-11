# InmoBot - Manual del Comprador

## Guía Completa de Instalación, Configuración y Mantenimiento

---

# Índice

1. [Introducción](#introducción)
2. [Resumen: ¿Qué tengo que hacer?](#resumen-qué-tengo-que-hacer)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Requisitos Previos](#requisitos-previos)
5. [Opción 1: Deploy en Railway (Recomendado)](#opción-1-deploy-en-railway-recomendado)
6. [Opción 2: Deploy en DigitalOcean](#opción-2-deploy-en-digitalocean)
7. [Configuración de Variables de Entorno](#configuración-de-variables-de-entorno)
8. [Configuración de WhatsApp Business API](#configuración-de-whatsapp-business-api)
9. [Configuración de OpenAI (IA)](#configuración-de-openai-ia)
10. [Configuración de Stripe (Pagos)](#configuración-de-stripe-pagos)
11. [Configuración de Emails](#configuración-de-emails)
12. [Configuración del Dominio](#configuración-del-dominio)
13. [Uso del Dashboard](#uso-del-dashboard)
14. [Personalización del Bot](#personalización-del-bot)
15. [Mantenimiento y Actualizaciones](#mantenimiento-y-actualizaciones)
16. [Solución de Problemas Comunes](#solución-de-problemas-comunes)
17. [Costos Operativos Mensuales](#costos-operativos-mensuales)
18. [Contacto de Soporte](#contacto-de-soporte)

---

# Introducción

Felicitaciones por adquirir **InmoBot**, el bot de WhatsApp con inteligencia artificial para inmobiliarias.

Este documento contiene todas las instrucciones necesarias para:
- Instalar y configurar el sistema
- Conectar las integraciones (WhatsApp, IA, pagos)
- Usar el dashboard de gestión
- Mantener y actualizar el sistema
- Resolver problemas comunes

**Tiempo estimado de configuración inicial:** 2-4 horas

---

# Resumen: ¿Qué tengo que hacer?

## Diagrama de Opciones de Deploy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OPCIONES DE DEPLOYMENT                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    LO QUE RECIBÍS DEL VENDEDOR                       │   │
│   │                                                                      │   │
│   │    📁 Acceso al Repositorio GitHub                                  │   │
│   │    📄 Documentación completa                                        │   │
│   │    📞 1 hora de videollamada (handoff)                              │   │
│   │    🔑 Archivos .env.example con instrucciones                       │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│                         ┌─────────────────────┐                             │
│                         │  ELEGÍ TU OPCIÓN    │                             │
│                         └─────────────────────┘                             │
│                          /                    \                              │
│                         /                      \                             │
│                        ▼                        ▼                            │
│   ┌────────────────────────────┐    ┌────────────────────────────┐          │
│   │     OPCIÓN A: RAILWAY      │    │  OPCIÓN B: DIGITALOCEAN    │          │
│   │      (Recomendado)         │    │    + MONGODB ATLAS         │          │
│   ├────────────────────────────┤    ├────────────────────────────┤          │
│   │                            │    │                            │          │
│   │  ✅ Fácil (10-15 min)      │    │  ⚠️  Media (1-2 horas)     │          │
│   │  ✅ Todo en un lugar       │    │  ✅ Más control            │          │
│   │  ✅ Deploy automático      │    │  ✅ Menor costo mensual    │          │
│   │  💰 ~$20-40/mes            │    │  💰 ~$15-30/mes            │          │
│   │                            │    │                            │          │
│   │  Ideal si:                 │    │  Ideal si:                 │          │
│   │  • No tenés desarrollador  │    │  • Tenés desarrollador     │          │
│   │  • Querés simplicidad      │    │  • Querés control total    │          │
│   │                            │    │                            │          │
│   └────────────────────────────┘    └────────────────────────────┘          │
│                │                                   │                         │
│                ▼                                   ▼                         │
│   ┌────────────────────────────┐    ┌────────────────────────────┐          │
│   │        PASOS RAILWAY       │    │    PASOS DIGITALOCEAN      │          │
│   ├────────────────────────────┤    ├────────────────────────────┤          │
│   │                            │    │                            │          │
│   │  1. Crear cuenta Railway   │    │  1. Crear Droplet ($12/mes)│          │
│   │  2. Conectar GitHub        │    │  2. Crear DB en Atlas      │          │
│   │  3. Crear MongoDB (1 clic) │    │  3. Clonar repo en servidor│          │
│   │  4. Configurar variables   │    │  4. Instalar dependencias  │          │
│   │  5. ¡Listo! ✅             │    │  5. Configurar Nginx + SSL │          │
│   │                            │    │  6. ¡Listo! ✅             │          │
│   └────────────────────────────┘    └────────────────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Flujo Paso a Paso (Opción Railway)

```
   TU                          RAILWAY                        SERVICIOS
    │                             │                               │
    │  1. Crear cuenta            │                               │
    ├────────────────────────────►│                               │
    │                             │                               │
    │  2. Conectar repo GitHub    │                               │
    ├────────────────────────────►│                               │
    │                             │                               │
    │                             │  3. Deploy automático         │
    │                             ├──────────────────────────────►│
    │                             │                               │
    │  4. Crear MongoDB           │                               │
    ├────────────────────────────►│  (1 click)                    │
    │                             │                               │
    │  5. Configurar .env         │                               │
    ├────────────────────────────►│                               │
    │                             │                               │
    │  6. Conectar dominio        │                               │
    ├────────────────────────────►│                               │
    │                             │                               │
    │                      ✅ APP FUNCIONANDO                     │
    │◄────────────────────────────┼───────────────────────────────│
```

## Checklist Rápido

```
□ Paso 1: Recibir acceso al repositorio GitHub
□ Paso 2: Elegir plataforma (Railway o DigitalOcean)
□ Paso 3: Crear cuentas en servicios externos:
    □ Meta Business (WhatsApp)
    □ OpenAI (Inteligencia Artificial)
    □ Stripe (Pagos) - opcional
□ Paso 4: Seguir guía de deploy de la opción elegida
□ Paso 5: Configurar variables de entorno
□ Paso 6: Configurar webhook de WhatsApp
□ Paso 7: Conectar dominio personalizado
□ Paso 8: ¡Probar el bot!
```

---

# Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                         INMOBOT                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Frontend   │    │   Backend    │    │   MongoDB    │       │
│  │    (React)   │◄──►│   (Python)   │◄──►│  (Database)  │       │
│  │   Puerto 3000│    │  Puerto 8001 │    │ Puerto 27017 │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                             │                                    │
│                             ▼                                    │
│         ┌─────────────────────────────────────┐                 │
│         │        INTEGRACIONES EXTERNAS        │                 │
│         ├─────────────────────────────────────┤                 │
│         │  • WhatsApp Business API (Meta)     │                 │
│         │  • OpenAI GPT (Inteligencia Artificial)│              │
│         │  • Stripe (Procesamiento de pagos)  │                 │
│         │  • Resend/SMTP (Emails)             │                 │
│         └─────────────────────────────────────┘                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Estructura de Carpetas

```
inmobot/
├── backend/
│   ├── server.py          # Servidor principal FastAPI
│   ├── models.py          # Modelos de datos
│   ├── api.py             # Endpoints de la API
│   ├── scheduler.py       # Tareas programadas
│   ├── bot/
│   │   ├── bot_flow.py    # Lógica del bot
│   │   ├── handlers.py    # Manejadores de mensajes
│   │   └── llm_service.py # Servicio de IA
│   ├── services/
│   │   ├── email_service.py
│   │   └── payment_service.py
│   ├── requirements.txt   # Dependencias Python
│   └── .env               # Variables de entorno (PRIVADO)
│
├── frontend/
│   ├── src/
│   │   ├── pages/         # Páginas de la aplicación
│   │   ├── components/    # Componentes reutilizables
│   │   └── App.js         # Aplicación principal
│   ├── package.json       # Dependencias Node.js
│   └── .env               # Variables de entorno frontend
│
└── docs/                  # Documentación
```

---

# Requisitos Previos

Antes de comenzar, necesitarás:

## Cuentas Necesarias

| Servicio | Para qué sirve | Cómo obtenerla |
|----------|----------------|----------------|
| **Meta Business** | WhatsApp Business API | https://business.facebook.com |
| **OpenAI** | Inteligencia Artificial | https://platform.openai.com |
| **MongoDB Atlas** | Base de datos | https://www.mongodb.com/atlas |
| **Stripe** | Procesar pagos | https://stripe.com |
| **Resend** (o SMTP) | Enviar emails | https://resend.com |
| **GitHub** | Control de versiones | https://github.com |
| **Railway** o **DigitalOcean** | Hosting | https://railway.app / https://digitalocean.com |

## Herramientas en tu Computadora

- **Git** - Para clonar y actualizar el código
- **Node.js 18+** - Para el frontend
- **Python 3.11+** - Para el backend
- **Editor de código** - VS Code recomendado

---

# Configurar MongoDB Atlas (Paso Previo Obligatorio)

Antes de hacer deploy en cualquier plataforma, necesitas crear tu base de datos en MongoDB Atlas (gratis para empezar).

## Paso 1: Crear Cuenta en MongoDB Atlas

1. Andá a https://www.mongodb.com/atlas y hacé click en **"Try Free"**
2. Registrate con tu email o cuenta de Google
3. Completá el formulario inicial (podés poner cualquier cosa en "Organization" y "Project")

## Paso 2: Crear un Cluster (Base de Datos)

1. Una vez dentro del dashboard de Atlas, hacé click en **"Build a Database"** (o **"Create"**)
2. Elegí el plan **"M0 FREE"** (gratis, perfecto para empezar)
   - **Provider:** AWS, Google Cloud o Azure (cualquiera funciona)
   - **Region:** Elegí la más cercana a tus clientes (ej: `South America - São Paulo` para LATAM)
   - **Cluster Name:** Dejá el nombre por defecto o poné `inmobot-cluster`
3. Click en **"Create Deployment"**
4. Esperá 1-3 minutos mientras se crea el cluster

## Paso 3: Crear Usuario de Base de Datos

Inmediatamente después de crear el cluster, Atlas te pide crear un usuario:

1. En la sección **"Database Access"** (menú lateral izquierdo), click en **"Add New Database User"**
2. **Authentication Method:** Password
3. Completá:
   - **Username:** `inmobot_admin` (o el que quieras)
   - **Password:** Generá una contraseña segura (click en "Autogenerate Secure Password" y **copiala en un lugar seguro**)
4. **Database User Privileges:** Seleccioná **"Read and write to any database"**
5. Click en **"Add User"**

> **IMPORTANTE:** Guardá el usuario y la contraseña, los vas a necesitar para la connection string.

## Paso 4: Configurar Acceso de Red (IP Whitelist)

1. En el menú lateral, andá a **"Network Access"**
2. Click en **"Add IP Address"**
3. Click en **"Allow Access from Anywhere"** (agrega `0.0.0.0/0`)
   - Esto permite que tu servidor se conecte desde cualquier IP
   - Para mayor seguridad en producción, podés restringir a la IP de tu servidor después
4. Click en **"Confirm"**

## Paso 5: Obtener la Connection String (MONGO_URL)

1. Volvé a **"Database"** en el menú lateral
2. En tu cluster, hacé click en **"Connect"**
3. Seleccioná **"Drivers"** (o "Connect your application")
4. **Driver:** Python / Version 3.12 or later
5. Copiá la connection string. Se ve así:

```
mongodb+srv://inmobot_admin:<password>@inmobot-cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

6. **Reemplazá** `<password>` por la contraseña real que creaste en el Paso 3
7. **Agregá el nombre de la base de datos** antes de los parámetros:

```
mongodb+srv://inmobot_admin:TU_PASSWORD_REAL@inmobot-cluster.xxxxx.mongodb.net/inmobot_db?retryWrites=true&w=majority
```

> Esta es tu `MONGO_URL`. Copiala y usala en las variables de entorno del backend.

## Paso 6: Crear el Usuario Admin de InmoBot

Una vez que tu backend esté corriendo y conectado a MongoDB Atlas, ejecutá el script de inicialización:

```bash
cd backend
python init_admin.py
```

Esto crea el usuario administrador del dashboard:
- **Email:** admin@inmobot.com
- **Password:** Admin123!

> **Cambiá la contraseña** desde el dashboard después del primer login (Perfil → Cambiar Contraseña).

## Resumen de lo que necesitás de Atlas

| Dato | Dónde usarlo | Ejemplo |
|------|-------------|---------|
| **MONGO_URL** | Backend `.env` | `mongodb+srv://user:pass@cluster.mongodb.net/inmobot_db...` |
| **DB_NAME** | Backend `.env` | `inmobot_db` |

---


# Opción 1: Deploy en Railway (Recomendado)

Railway es la opción más simple. Deploy automático desde GitHub.

## Paso 1: Preparar el Repositorio

1. Creá una cuenta en GitHub: https://github.com
2. Creá un repositorio privado llamado `inmobot`
3. Subí el código:

```bash
cd inmobot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/inmobot.git
git push -u origin main
```

## Paso 2: Crear Proyecto en Railway

1. Andá a https://railway.app y creá una cuenta
2. Click en **"New Project"**
3. Seleccioná **"Deploy from GitHub repo"**
4. Conectá tu cuenta de GitHub y seleccioná el repositorio `inmobot`

## Paso 3: Configurar Servicios

Necesitás crear 3 servicios en Railway:

### Servicio 1: MongoDB
1. Click en **"New"** → **"Database"** → **"MongoDB"**
2. Railway te dará automáticamente una `MONGO_URL`
3. Copiá esta URL para usarla en el backend

### Servicio 2: Backend
1. Click en **"New"** → **"GitHub Repo"**
2. Seleccioná tu repo y configurá:
   - **Root Directory:** `backend`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
3. En **Variables**, agregá todas las del archivo `.env` (ver sección de variables)

### Servicio 3: Frontend
1. Click en **"New"** → **"GitHub Repo"**
2. Seleccioná tu repo y configurá:
   - **Root Directory:** `frontend`
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** `npx serve -s build -l $PORT`
3. En **Variables**, agregá:
   - `REACT_APP_BACKEND_URL` = URL del servicio backend

## Paso 4: Configurar Dominio

1. En el servicio Frontend, click en **"Settings"** → **"Domains"**
2. Agregá tu dominio personalizado (ej: `app.tuinmobiliaria.com`)
3. Configurá los DNS en tu proveedor de dominio (ver sección de dominio)

## Costo Estimado Railway

- **Hobby Plan:** $5/mes (incluye créditos)
- **Pro Plan:** ~$20-40/mes según uso

---

# Opción 2: Deploy en DigitalOcean

Para mayor control y menor costo a largo plazo.

## Paso 1: Crear Droplet

1. Creá cuenta en https://digitalocean.com
2. Click en **"Create"** → **"Droplets"**
3. Configuración recomendada:
   - **Image:** Ubuntu 22.04 LTS
   - **Plan:** Basic - $12/mes (2GB RAM, 1 CPU)
   - **Region:** El más cercano a tus clientes
   - **Authentication:** SSH Key (recomendado) o Password

## Paso 2: Conectar al Servidor

```bash
ssh root@TU_IP_DEL_SERVIDOR
```

## Paso 3: Instalar Dependencias

```bash
# Actualizar sistema
apt update && apt upgrade -y

# Instalar Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Instalar Python 3.11
apt install -y python3.11 python3.11-venv python3-pip

# Instalar MongoDB
apt install -y mongodb

# Instalar Nginx
apt install -y nginx

# Instalar Git
apt install -y git

# Instalar PM2 (gestor de procesos)
npm install -g pm2
```

## Paso 4: Clonar el Repositorio

```bash
cd /var/www
git clone https://github.com/TU_USUARIO/inmobot.git
cd inmobot
```

## Paso 5: Configurar Backend

```bash
cd /var/www/inmobot/backend

# Crear entorno virtual
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Crear archivo .env (ver sección de variables)
nano .env

# Iniciar con PM2
pm2 start "uvicorn server:app --host 0.0.0.0 --port 8001" --name inmobot-backend
pm2 save
```

## Paso 6: Configurar Frontend

```bash
cd /var/www/inmobot/frontend

# Instalar dependencias
npm install

# Crear archivo .env
echo "REACT_APP_BACKEND_URL=https://api.tudominio.com" > .env

# Compilar
npm run build
```

## Paso 7: Configurar Nginx

```bash
nano /etc/nginx/sites-available/inmobot
```

Contenido del archivo:

```nginx
# Frontend
server {
    listen 80;
    server_name app.tudominio.com;
    
    location / {
        root /var/www/inmobot/frontend/build;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}

# Backend API
server {
    listen 80;
    server_name api.tudominio.com;
    
    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Activar configuración:

```bash
ln -s /etc/nginx/sites-available/inmobot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

## Paso 8: Configurar SSL (HTTPS)

```bash
# Instalar Certbot
apt install -y certbot python3-certbot-nginx

# Obtener certificados
certbot --nginx -d app.tudominio.com -d api.tudominio.com

# Renovación automática (ya configurada por defecto)
```

---

# Configuración de Variables de Entorno

## Backend (.env)

Crear archivo `/var/www/inmobot/backend/.env`:

```env
# Base de datos
MONGO_URL=mongodb+srv://USUARIO:PASSWORD@cluster.mongodb.net/inmobot_db
DB_NAME=inmobot_db

# Seguridad
APP_SECRET=genera_una_clave_secreta_larga_y_aleatoria
CORS_ORIGINS=https://app.tudominio.com

# WhatsApp (Meta Business)
WHATSAPP_PHONE_NUMBER_ID=tu_phone_number_id
WHATSAPP_ACCESS_TOKEN=tu_access_token
WHATSAPP_BUSINESS_ACCOUNT_ID=tu_business_account_id
WEBHOOK_VERIFY_TOKEN=un_token_secreto_para_verificar

# OpenAI
OPENAI_API_KEY=sk-tu-api-key-de-openai

# Stripe
STRIPE_API_KEY=sk_live_tu_stripe_key

# Emails (opción Resend)
RESEND_API_KEY=re_tu_resend_key

# Emails (opción SMTP alternativa)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password
SMTP_FROM_EMAIL=tu_email@gmail.com
SMTP_FROM_NAME=InmoBot

# Notificaciones
NOTIFICATION_EMAILS=email1@ejemplo.com,email2@ejemplo.com
```

## Frontend (.env)

Crear archivo `/var/www/inmobot/frontend/.env`:

```env
REACT_APP_BACKEND_URL=https://api.tudominio.com
```

---

# Configuración de WhatsApp Business API

## Paso 1: Crear App en Meta Business

1. Andá a https://developers.facebook.com
2. Click en **"My Apps"** → **"Create App"**
3. Seleccioná **"Business"** → **"Next"**
4. Completá nombre y email → **"Create App"**

## Paso 2: Agregar WhatsApp

1. En tu app, buscá **"WhatsApp"** y click en **"Set Up"**
2. Seleccioná o creá una **Meta Business Account**
3. Agregá un número de teléfono para WhatsApp Business

## Paso 3: Obtener Credenciales

En el panel de WhatsApp:

| Variable | Dónde encontrarla |
|----------|-------------------|
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp → API Setup → Phone Number ID |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp → API Setup → Temporary Access Token (o crear permanente) |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | WhatsApp → API Setup → WhatsApp Business Account ID |

## Paso 4: Configurar Webhook

1. En WhatsApp → **Configuration** → **Webhook**
2. **Callback URL:** `https://api.tudominio.com/api/webhook`
3. **Verify Token:** El mismo que pusiste en `WEBHOOK_VERIFY_TOKEN`
4. Click en **"Verify and Save"**
5. Suscribirse a: `messages`, `message_status`

## Paso 5: Solicitar Permisos de Producción

Para salir del modo de prueba:

1. En tu App → **App Review** → **Permissions and Features**
2. Solicitá: `whatsapp_business_messaging`, `whatsapp_business_management`
3. Completá la verificación del negocio

---

# Configuración de OpenAI (IA)

## Paso 1: Crear Cuenta

1. Andá a https://platform.openai.com
2. Registrate o iniciá sesión
3. Agregá un método de pago (requerido para usar la API)

## Paso 2: Crear API Key

1. Click en tu perfil → **"View API Keys"**
2. Click en **"Create new secret key"**
3. Copiá la key (solo se muestra una vez)
4. Guardala en `OPENAI_API_KEY` del archivo `.env`

## Paso 3: Configurar Límites (Recomendado)

1. En **"Usage Limits"**
2. Configurá un límite mensual (ej: $50/mes)
3. Activá alertas por email

## Costo Estimado

- **GPT-4:** ~$0.03 por conversación promedio
- **100 leads/mes:** ~$3-5/mes en OpenAI

---

# Configuración de Stripe (Pagos)

## Paso 1: Crear Cuenta

1. Andá a https://stripe.com
2. Completá el registro y verificación del negocio

## Paso 2: Obtener API Keys

1. En el Dashboard → **"Developers"** → **"API Keys"**
2. Copiá la **Secret Key** (empieza con `sk_live_`)
3. Guardala en `STRIPE_API_KEY`

## Paso 3: Configurar Webhook de Stripe

1. En **"Developers"** → **"Webhooks"**
2. Click en **"Add endpoint"**
3. **URL:** `https://api.tudominio.com/api/stripe/webhook`
4. Eventos a escuchar:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`

## Modo de Prueba vs Producción

- **Test mode:** Keys empiezan con `sk_test_` (no cobra dinero real)
- **Live mode:** Keys empiezan con `sk_live_` (cobra dinero real)

---

# Configuración de Emails

## Opción A: Resend (Recomendado)

1. Creá cuenta en https://resend.com
2. Verificá tu dominio
3. Obtené la API Key
4. Configurá `RESEND_API_KEY` en `.env`

## Opción B: Gmail SMTP

1. Habilitá "Verificación en 2 pasos" en tu cuenta Google
2. Generá una "Contraseña de aplicación":
   - Google Account → Security → App Passwords
   - Seleccioná "Mail" y "Other"
   - Copiá la contraseña de 16 caracteres
3. Configurá en `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu_email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
```

---

# Configuración del Dominio

## Registros DNS Necesarios

En tu proveedor de dominio (GoDaddy, Namecheap, Cloudflare, etc.):

| Tipo | Nombre | Valor | TTL |
|------|--------|-------|-----|
| A | app | IP_DE_TU_SERVIDOR | 3600 |
| A | api | IP_DE_TU_SERVIDOR | 3600 |
| CNAME | www | app.tudominio.com | 3600 |

## Si usás Cloudflare

**IMPORTANTE:** Los registros deben estar en modo **"DNS only"** (nube gris), NO en "Proxied" (nube naranja), para que el SSL de tu servidor funcione correctamente.

---

# Uso del Dashboard

## Acceso Inicial

- **URL:** https://app.tudominio.com
- **Usuario por defecto:** admin@inmobot.com
- **Contraseña por defecto:** Admin123!

**¡IMPORTANTE!** Cambiá la contraseña inmediatamente después del primer acceso.

## Secciones del Dashboard

### 1. Dashboard Principal
- Resumen de métricas
- Leads del día
- Citas programadas
- Notificaciones

### 2. Leads
- Lista de todos los leads
- Filtros por estado, intención, fecha
- Acciones masivas (cambiar estado, asignar, eliminar)
- Exportar a CSV

### 3. Pipeline (Kanban)
- Vista visual del embudo de ventas
- Arrastrá leads entre columnas
- Estados: Nuevo → Contactado → Calificado → Cita → Cerrado

### 4. Calendario
- Todas las citas agendadas
- Vista mensual/semanal/diaria
- Click para ver detalles del lead

### 5. Broadcast
- Enviar mensajes masivos
- Filtrar por segmento
- Programar envíos

### 6. Configuración
- Datos de la empresa
- Usuarios del sistema
- Integraciones

---

# Personalización del Bot

## Cambiar Mensajes del Bot

Los mensajes están en `/backend/bot/bot_flow.py`

Ejemplo de mensaje de bienvenida:

```python
WELCOME_MESSAGE = """
¡Hola! 👋 Soy el asistente virtual de *{nombre_inmobiliaria}*.

¿En qué puedo ayudarte hoy?

1️⃣ Quiero *comprar* una propiedad
2️⃣ Quiero *alquilar* una propiedad
3️⃣ Quiero *vender* mi propiedad
4️⃣ Hablar con un asesor
"""
```

## Cambiar Flujos de Conversación

Los flujos están definidos en `/backend/bot/handlers.py`

## Cambiar Colores y Logo

- **Logo:** Reemplazá `/frontend/public/logo.png`
- **Colores:** Editá `/frontend/src/App.css` (variables CSS al inicio)
- **Favicon:** Reemplazá `/frontend/public/favicon.ico`

---

# Mantenimiento y Actualizaciones

## Actualizar el Sistema

### Si usás Railway

Railway actualiza automáticamente cuando hacés push a GitHub:

```bash
git add .
git commit -m "Descripción del cambio"
git push
```

### Si usás DigitalOcean

```bash
# Conectar al servidor
ssh root@TU_IP

# Ir al directorio
cd /var/www/inmobot

# Bajar cambios
git pull

# Backend: reinstalar dependencias si es necesario
cd backend
source venv/bin/activate
pip install -r requirements.txt
pm2 restart inmobot-backend

# Frontend: recompilar
cd ../frontend
npm install
npm run build
```

## Backups de Base de Datos

### Backup Manual (MongoDB Atlas)

1. Entrá a https://cloud.mongodb.com
2. Tu cluster → **"..."** → **"Command Line Tools"**
3. Copiá el comando de `mongodump`

### Backup Automático

MongoDB Atlas incluye backups automáticos en planes pagos.

## Monitoreo

### Ver Logs del Backend

```bash
# Railway
railway logs

# DigitalOcean con PM2
pm2 logs inmobot-backend
```

### Ver Estado de Servicios

```bash
pm2 status
```

---

# Solución de Problemas Comunes

## El bot no responde

1. **Verificar webhook:**
   ```bash
   curl https://api.tudominio.com/api/webhook
   ```
   Debería responder con status 200

2. **Verificar logs:**
   ```bash
   pm2 logs inmobot-backend --lines 100
   ```

3. **Verificar token de WhatsApp:**
   - Los tokens temporales expiran en 24hs
   - Generá un token permanente en Meta Business

## Error de conexión a base de datos

1. **Verificar MONGO_URL:**
   - Que no tenga comillas extra
   - Que el usuario y contraseña sean correctos

2. **Verificar IP whitelist en MongoDB Atlas:**
   - Network Access → Add IP Address → Allow Access from Anywhere (0.0.0.0/0)

## El frontend no carga

1. **Verificar build:**
   ```bash
   cd /var/www/inmobot/frontend
   npm run build
   ```

2. **Verificar Nginx:**
   ```bash
   nginx -t
   systemctl status nginx
   ```

## Error de CORS

1. **Verificar CORS_ORIGINS en backend:**
   ```env
   CORS_ORIGINS=https://app.tudominio.com
   ```

2. **Si hay múltiples dominios:**
   ```env
   CORS_ORIGINS=https://app.tudominio.com,https://www.tudominio.com
   ```

## Stripe no procesa pagos

1. **Verificar que estés usando keys de producción** (`sk_live_`, no `sk_test_`)
2. **Verificar webhook de Stripe** esté activo y respondiendo

---

# Costos Operativos Mensuales

## Estimación para 100 leads/mes

| Servicio | Costo Mensual | Notas |
|----------|---------------|-------|
| **Hosting (Railway/DO)** | $12-40 USD | Según plan |
| **MongoDB Atlas** | $0-25 USD | Free tier o M10 |
| **WhatsApp API** | $0-50 USD | Primeras 1000 conversaciones gratis |
| **OpenAI** | $5-15 USD | ~$0.03-0.10 por conversación |
| **Dominio** | ~$1 USD | $12/año |
| **SSL** | $0 | Let's Encrypt gratis |
| **Stripe** | 2.9% + $0.30 | Por transacción |
| **Resend** | $0-20 USD | 3000 emails/mes gratis |
| **TOTAL** | **$20-150 USD** | Según volumen |

---

# Contacto de Soporte

## Durante el período de soporte incluido

- **Email:** [TU_EMAIL]
- **WhatsApp:** [TU_NUMERO]
- **Horario:** Lunes a Viernes, 9:00 - 18:00

## Soporte extendido (post-período incluido)

- **Plan Básico:** $300/mes - Corrección de bugs, asistencia por email
- **Plan Premium:** $500/mes - Todo lo anterior + WhatsApp + prioridad

## Nuevas funcionalidades

Las nuevas funcionalidades se cotizan por separado según complejidad.

---

# Anexo: Comandos Útiles

## Servidor (DigitalOcean/VPS)

```bash
# Ver estado de servicios
pm2 status

# Reiniciar backend
pm2 restart inmobot-backend

# Ver logs en tiempo real
pm2 logs inmobot-backend

# Reiniciar Nginx
systemctl restart nginx

# Ver uso de recursos
htop
```

## Git

```bash
# Ver cambios
git status

# Actualizar código
git pull

# Guardar cambios locales
git stash
git pull
git stash pop
```

## Base de datos

```bash
# Conectar a MongoDB
mongosh "tu_mongo_url"

# Ver bases de datos
show dbs

# Usar base de datos
use inmobot_db

# Ver colecciones
show collections

# Ver leads
db.leads.find().pretty()
```

---

*Documento generado para InmoBot - Versión 1.0*
*Última actualización: Febrero 2025*
