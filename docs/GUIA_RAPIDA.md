# InmoBot - Guía Rápida de Inicio

## Resumen Visual

```
┌─────────────────────────────────────────────────────────────┐
│                    SETUP EN 5 PASOS                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│    📁 REPO          🚂 RAILWAY         🔧 CONFIG             │
│    GITHUB    ───►   DEPLOY     ───►   VARIABLES             │
│                                                              │
│        │                │                   │                │
│        ▼                ▼                   ▼                │
│                                                              │
│    📱 WHATSAPP      🌐 DOMINIO        ✅ LISTO!             │
│    WEBHOOK    ───►   (opcional)  ───►   BOT ACTIVO          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Setup en 30 minutos (Railway)

### Paso 1: Cuentas necesarias (10 min)

Creá cuentas en:
- [ ] GitHub: https://github.com
- [ ] Railway: https://railway.app
- [ ] MongoDB Atlas: https://mongodb.com/atlas
- [ ] OpenAI: https://platform.openai.com
- [ ] Meta Business: https://business.facebook.com

---

### Paso 1.5: Crear Base de Datos en MongoDB Atlas (5 min)

1. Entrá a https://mongodb.com/atlas → **"Try Free"**
2. Creá un cluster **M0 FREE** (región cercana a tus clientes)
3. **Crear usuario de BD:** Database Access → Add New Database User
   - Username: `inmobot_admin`
   - Password: generá una segura y guardala
   - Permisos: "Read and write to any database"
4. **Abrir acceso de red:** Network Access → Add IP → "Allow Access from Anywhere" (`0.0.0.0/0`)
5. **Obtener connection string:** Database → Connect → Drivers → Copiá la URL
6. Reemplazá `<password>` y agregá `/inmobot_db`:

```
mongodb+srv://inmobot_admin:TU_PASSWORD@cluster.xxxxx.mongodb.net/inmobot_db?retryWrites=true&w=majority
```

> Esta es tu `MONGO_URL` para el `.env` del backend.
> Para más detalle, consultá la sección "Configurar MongoDB Atlas" en el MANUAL_COMPRADOR.md

---

### Paso 2: Subir código a GitHub (5 min)

```bash
cd inmobot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/inmobot.git
git push -u origin main
```

---

### Paso 3: Deploy en Railway (10 min)

1. **Railway** → New Project → Deploy from GitHub
2. **Crear MongoDB:** New → Database → MongoDB
3. **Crear Backend:** New → GitHub Repo → Root: `backend`
4. **Crear Frontend:** New → GitHub Repo → Root: `frontend`

---

### Paso 4: Variables de entorno (5 min)

**Backend (copiar y completar):**

```env
MONGO_URL=mongodb+srv://...
DB_NAME=inmobot_db
APP_SECRET=clave_secreta_random_larga
CORS_ORIGINS=https://tu-frontend.railway.app
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_BUSINESS_ACCOUNT_ID=
WEBHOOK_VERIFY_TOKEN=inmobot_verify_2024
OPENAI_API_KEY=sk-...
STRIPE_API_KEY=sk_live_...
RESEND_API_KEY=re_...
NOTIFICATION_EMAILS=tu@email.com
```

**Frontend:**

```env
REACT_APP_BACKEND_URL=https://tu-backend.railway.app
```

---

### Paso 5: Configurar WhatsApp Webhook

1. Meta Business → Tu App → WhatsApp → Configuration
2. **Callback URL:** `https://tu-backend.railway.app/api/webhook`
3. **Verify Token:** `inmobot_verify_2024`
4. Suscribirse a: `messages`

---

### Listo!

Tu bot está funcionando. Ahora creá el usuario admin:

```bash
cd backend
python init_admin.py
```

Accedé al dashboard:
- **URL:** https://tu-frontend.railway.app
- **Usuario:** admin@inmobot.com
- **Password:** Admin123!

> Cambiá la contraseña después del primer login.

---

## Checklist Post-Instalación

- [ ] Cambiar contraseña del admin
- [ ] Probar enviar mensaje al bot
- [ ] Verificar que llegan notificaciones
- [ ] Conectar dominio personalizado
- [ ] Configurar SSL

---

## Comandos útiles

```bash
# Actualizar (tras cambios en GitHub)
git push  # Railway actualiza automáticamente

# Ver logs en Railway
railway logs
```

---

## Ayuda

- **Manual completo:** MANUAL_COMPRADOR.md
- **Soporte:** [TU_EMAIL]
