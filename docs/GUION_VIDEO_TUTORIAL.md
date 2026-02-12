# InmoBot - Guion Video Tutorial

## Información del Video

- **Duración estimada:** 15-20 minutos
- **Formato:** Grabación de pantalla + voz en off
- **Herramienta sugerida:** Loom, OBS, o Camtasia
- **Resolución:** 1920x1080 (Full HD)

---

## INTRO (30 segundos)

### Pantalla
Mostrar logo de InmoBot con fondo profesional

### Narración
> "Hola, bienvenido al tutorial completo de InmoBot, el bot de WhatsApp con inteligencia artificial para inmobiliarias.
>
> En este video vas a aprender a configurar y usar todo el sistema. Vamos a cubrir desde la instalación inicial hasta el uso diario del dashboard."

---

## PARTE 1: Visión General (2 minutos)

### Pantalla
Mostrar el dashboard principal, luego navegar por las secciones

### Narración
> "InmoBot tiene dos partes principales:
>
> **Primero, el Bot de WhatsApp.** Este bot responde automáticamente a tus clientes las 24 horas. Califica leads, agenda citas, y te notifica cuando hay oportunidades importantes.
>
> **Segundo, el Dashboard de gestión.** Desde acá vas a ver todos tus leads, métricas, calendario de citas, y podés enviar mensajes masivos.
>
> Vamos a empezar con la configuración inicial."

---

## PARTE 2: Instalación en Railway (4 minutos)

### Pantalla
Compartir pantalla en railway.app

### Narración

> "Para instalar InmoBot, vamos a usar Railway, que es la opción más simple.
>
> **Paso 1:** Entramos a railway.app y creamos una cuenta si no tenés.
>
> **Paso 2:** Hacemos click en 'New Project' y seleccionamos 'Deploy from GitHub'.
>
> **Paso 3:** Conectamos nuestra cuenta de GitHub y seleccionamos el repositorio de InmoBot."

### Acciones en pantalla
1. Ir a railway.app
2. Click en New Project
3. Seleccionar GitHub
4. Mostrar la selección del repo

> "Ahora necesitamos crear tres servicios:
>
> **Primero, la base de datos.** Click en 'New', 'Database', 'MongoDB'. Railway la crea automáticamente.
>
> **Segundo, el backend.** Click en 'New', seleccionamos nuestro repo, y en 'Root Directory' ponemos 'backend'.
>
> **Tercero, el frontend.** Mismo proceso, pero el 'Root Directory' es 'frontend'."

### Acciones en pantalla
1. Crear MongoDB
2. Crear servicio backend
3. Crear servicio frontend

> "Una vez creados, necesitamos configurar las variables de entorno. Esto lo vemos en la siguiente sección."

---

## PARTE 3: Variables de Entorno (3 minutos)

### Pantalla
Mostrar panel de variables en Railway

### Narración

> "Las variables de entorno son las configuraciones secretas del sistema. Vamos a configurarlas.
>
> Hacemos click en el servicio backend, vamos a 'Variables', y agregamos una por una."

### Acciones en pantalla
Ir agregando variables mientras se explica

> "**MONGO_URL:** Esta la copiamos del servicio MongoDB que creamos. Click en MongoDB, copiamos la URL de conexión.
>
> **DB_NAME:** Ponemos 'inmobot_db'.
>
> **APP_SECRET:** Una clave secreta larga. Podés generar una en random.org.
>
> **Las de WhatsApp** las vamos a conseguir de Meta Business. Te muestro cómo en un momento.
>
> **OPENAI_API_KEY:** Esta la sacás de platform.openai.com, en la sección de API Keys.
>
> **STRIPE_API_KEY:** De tu cuenta de Stripe, en Developers > API Keys."

> "Para el frontend, solo necesitamos una variable:
>
> **REACT_APP_BACKEND_URL:** La URL de tu servicio backend en Railway."

---

## PARTE 4: Configurar WhatsApp Business (3 minutos)

### Pantalla
Compartir pantalla en developers.facebook.com

### Narración

> "Ahora vamos a conectar WhatsApp. Entramos a developers.facebook.com.
>
> **Paso 1:** Creamos una app nueva. Click en 'My Apps', 'Create App', seleccionamos 'Business'.
>
> **Paso 2:** Le ponemos un nombre y creamos.
>
> **Paso 3:** Buscamos 'WhatsApp' en los productos y hacemos click en 'Set Up'."

### Acciones en pantalla
1. Crear app en Meta
2. Agregar producto WhatsApp
3. Mostrar dónde están las credenciales

> "En la sección de WhatsApp vamos a encontrar tres cosas importantes:
>
> - **Phone Number ID:** Este es el ID de tu número de WhatsApp
> - **Access Token:** El token para enviar mensajes
> - **Business Account ID:** El ID de tu cuenta business
>
> Copiamos estos valores y los pegamos en las variables de entorno de Railway."

> "Ahora configuramos el Webhook. En 'Configuration' > 'Webhook':
>
> - **Callback URL:** Ponemos la URL de tu backend seguida de '/api/webhook'
> - **Verify Token:** El mismo que pusiste en WEBHOOK_VERIFY_TOKEN
>
> Click en 'Verify and Save' y suscribimos a 'messages'."

---

## PARTE 5: Uso del Dashboard (4 minutos)

### Pantalla
Mostrar el dashboard de InmoBot

### Narración

> "Ahora que todo está configurado, vamos a ver cómo usar el sistema día a día.
>
> Entramos al dashboard con las credenciales por defecto: admin@inmobot.com y Admin123!"

### Acciones en pantalla
Login en el dashboard

> "En la pantalla principal vemos:
>
> - **Métricas del día:** Leads nuevos, citas agendadas, tasa de respuesta
> - **Notificaciones:** Alertas de leads calientes
> - **Gráficos:** Evolución de leads y conversiones"

### Acciones en pantalla
Navegar por el dashboard mostrando cada sección

> "En la sección de **Leads** vemos todos los contactos. Podemos:
>
> - Filtrar por estado, intención, o fecha
> - Ver el detalle de cada lead
> - Aplicar acciones masivas con los checkboxes"

### Acciones en pantalla
Mostrar filtros y selección de leads

> "El **Pipeline Kanban** es mi favorito. Acá ves visualmente dónde está cada lead.
>
> Podés arrastrar y soltar para cambiar estados. Por ejemplo, si un lead confirmó una cita, lo arrastrás a 'Cita Agendada'."

### Acciones en pantalla
Demostrar drag and drop en el Kanban

> "El **Calendario** muestra todas las citas programadas. Podés ver por día, semana o mes."

### Acciones en pantalla
Navegar por el calendario

---

## PARTE 6: El Bot en Acción (2 minutos)

### Pantalla
Mostrar WhatsApp Web o simulación de conversación

### Narración

> "Veamos cómo funciona el bot cuando un cliente escribe.
>
> El cliente escribe 'Hola' al número de WhatsApp Business.
>
> El bot responde automáticamente con las opciones: Comprar, Alquilar, Vender, o hablar con un asesor.
>
> Si elige 'Comprar', el bot le pregunta qué zona le interesa, cuál es su presupuesto, qué tipo de propiedad busca.
>
> Toda esta información queda guardada automáticamente en el dashboard."

### Acciones en pantalla
Mostrar la conversación del bot (puede ser un video pregrabado o simulación)

> "El bot califica al lead con un score de 0 a 12. Los leads con score alto aparecen como 'Calientes' y te llega una notificación inmediata."

---

## PARTE 7: Personalización (2 minutos)

### Pantalla
Mostrar archivos de código en VS Code

### Narración

> "Si querés personalizar los mensajes del bot, es muy simple.
>
> Los mensajes están en el archivo 'backend/bot/bot_flow.py'. Acá podés cambiar el texto de bienvenida, las opciones del menú, y las respuestas.
>
> Para los colores y el logo, editás el archivo 'frontend/src/App.css' y reemplazás el logo en 'frontend/public/logo.png'."

### Acciones en pantalla
Mostrar brevemente los archivos

---

## PARTE 8: Mantenimiento (1 minuto)

### Pantalla
Volver a mostrar Railway

### Narración

> "Para mantener el sistema actualizado, solo tenés que hacer cambios en GitHub y Railway los aplica automáticamente.
>
> Si algo falla, podés ver los logs en Railway haciendo click en tu servicio y yendo a 'Logs'.
>
> Los backups de la base de datos se hacen automáticamente si usás MongoDB Atlas con un plan pago."

---

## CIERRE (30 segundos)

### Pantalla
Mostrar logo de InmoBot y datos de contacto

### Narración

> "Eso es todo por este tutorial. Ahora tenés InmoBot funcionando y listo para captar leads automáticamente.
>
> Si tenés dudas, revisá la documentación en la carpeta 'docs' del proyecto, o contactame por email o WhatsApp.
>
> Muchas gracias por elegir InmoBot. ¡Éxitos con tu negocio!"

---

## RECURSOS PARA EL VIDEO

### Música de fondo sugerida
- Epidemic Sound: "Inspiring Corporate" o similar
- YouTube Audio Library: buscar "corporate background"
- Volumen: 10-15% para no tapar la voz

### Transiciones
- Usar transiciones simples (fade, slide)
- No abusar de efectos

### Texto en pantalla
- Mostrar los URLs cuando se mencionan
- Mostrar las credenciales cuando se dicen
- Usar subtítulos si es posible

### Grabación
- Hablar pausado y claro
- Grabar en un lugar silencioso
- Hacer zoom en las áreas importantes de la pantalla

---

## CHECKLIST PRE-GRABACIÓN

- [ ] Railway con proyecto de ejemplo listo
- [ ] Meta Business con app de prueba
- [ ] Dashboard con datos de ejemplo
- [ ] Micrófono probado
- [ ] Pantalla limpia (cerrar notificaciones, tabs innecesarias)
- [ ] Script impreso o en segundo monitor

---

## MINIATURAS Y TÍTULO SUGERIDOS

### Título
"InmoBot Tutorial Completo - Bot de WhatsApp con IA para Inmobiliarias"

### Descripción
```
Aprende a configurar y usar InmoBot, el bot de WhatsApp con inteligencia artificial para inmobiliarias.

Timestamps:
0:00 - Introducción
0:30 - Visión General
2:30 - Instalación en Railway
6:30 - Variables de Entorno
9:30 - Configurar WhatsApp
12:30 - Uso del Dashboard
16:30 - El Bot en Acción
18:30 - Personalización
20:00 - Mantenimiento

Documentación: [link al repo]
```

### Tags
InmoBot, Bot WhatsApp, Inmobiliaria, CRM Inmobiliario, Automatización, GPT, Inteligencia Artificial, Lead Generation, Real Estate Bot

---

*Guion preparado para InmoBot v1.0*
