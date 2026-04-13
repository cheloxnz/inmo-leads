# CONTEXTO COMPLETO DE INMOBOT PARA GENERAR MASTERCLASS
## Pasarle esto a Claude para que genere el contenido de la masterclass

---

## QUE ES INMOBOT
InmoBot es un sistema completo de ventas con IA para inmobiliarias. Incluye un bot de WhatsApp con GPT-4, un dashboard de gestión, y automatizaciones. Stack: React + FastAPI (Python) + MongoDB + OpenAI GPT-4 + Whisper + WhatsApp Cloud API + Stripe.

---

## FLUJO COMPLETO DEL BOT (bot_flow.py)

### Etapas del flujo de conversación:
1. **WELCOME** → Saludo + botones interactivos (Comprar / Alquilar / Vender)
2. **INTENT** → Clasificación de intención con GPT-4 si no es un botón directo. Detecta: comprar, alquilar, vender, inversión
3. **NAME** → Captura nombre completo
4. **ZONE** → GPT-4 extrae zona/barrio del mensaje libre (ej: "por palermo" → "Palermo")
5. **BUDGET** → GPT-4 extrae presupuesto (ej: "200 lucas" → "USD 200.000"). Descalifica si < USD 50,000 para compra
6. **PROPERTY_TYPE** → Botones: Departamento / Casa / PH. También acepta: local, terreno, oficina
7. **BEDROOMS** → Botones: 1 ambiente / 2 ambientes / 3 o más
8. **MUST_HAVE** → Texto libre: requisitos (balcón, cochera, seguridad, etc.)
9. **URGENCY** → Botones: Urgente (semanas) / Próximo mes / Próximos meses
10. **FINANCING** → Solo para compradores. Botones: Efectivo / Crédito hipotecario / No sé
11. **SCORING** → Se calcula score automático y se clasifica (Hot/Warm/Cold)
12. **APPOINTMENT_OFFER** → Botones: Sí visita / Sí llamada / No ahora
13. **SELECT_DAY** → Parseo inteligente de fechas ("mañana", "jueves 12", "15/02", "7 de febrero")
14. **SELECT_TIME** → Botones: Mañana (9-12hs) / Tarde (14-17hs) / Noche (17-20hs)
15. **COMPLETED** → Cita confirmada + notificación a asesor

### Flujo especial para VENDEDORES:
- Pregunta zona de la propiedad → tipo de propiedad → ofrece tasación gratuita → agenda visita

### Flujos de gestión de citas:
- **Reagendamiento**: Detecta "cambiar cita", "reagendar", etc. → Confirmación → Nueva fecha → Nuevo horario
- **Cancelación**: Detecta "cancelar", "anular", etc. → Opciones: Cancelar / Reagendar / Mantener
- **Post-visita**: 48hs después envía follow-up con botones

### Funciones de IA (llm_service.py):
- `classify_intent()` → Clasifica intención libre con GPT-4
- `extract_zone()` → Extrae zona/barrio de texto libre
- `extract_budget()` → Extrae y normaliza presupuesto
- `generate_smart_response()` → Respuestas inteligentes para consultas generales usando contexto del lead
- `parse_free_text_response()` → Parseo de respuestas en lenguaje natural
- `validate_response()` → Valida si la respuesta del usuario es apropiada

### Transcripción de audio (audio_service.py):
- Usa OpenAI Whisper para transcribir mensajes de voz de WhatsApp
- El audio se descarga, se envía a Whisper, y el texto se procesa como mensaje normal

---

## SISTEMA DE SCORING (scoring.py)

### Criterios de puntuación (máximo 12 puntos):
| Criterio | Puntos |
|----------|--------|
| Presupuesto definido | +2 |
| Zona definida | +2 |
| Tipo de propiedad definido | +1 |
| Urgencia Alta (semanas) | +3 |
| Urgencia Media (mes) | +2 |
| Urgencia Baja (meses) | +1 |
| Solo mirando | +0 |
| Financiamiento definido (no "no sé") | +1 |
| Intención de compra (vs alquiler) | +1 |
| Requisitos específicos | +1 |

### Clasificación automática:
- **HOT (7+ puntos)**: Lead caliente → Handoff a asesor humano + notificación email
- **WARM (4-6 puntos)**: Lead tibio → Seguimiento automático
- **COLD (0-3 puntos)**: Lead frío → Se mantiene en pipeline

### Handoff automático a humano cuando:
- Score >= 7 (lead caliente)
- Completó el flujo y aceptó agendar
- Tiene cita agendada

---

## VARIABLES CONFIGURABLES DEL BOT (BotConfig en models.py)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `business_hours_start` | 9 | Hora de apertura |
| `business_hours_end` | 20 | Hora de cierre |
| `business_days` | Lun-Vie | Días hábiles |
| `saturday_hours_start` | 10 | Apertura sábados |
| `saturday_hours_end` | 14 | Cierre sábados |
| `timezone` | America/Argentina/Buenos_Aires | Zona horaria |
| `auto_handoff_score` | 7 | Score mínimo para handoff automático |
| `warm_lead_reactivation_days` | 3 | Días sin actividad para reactivar lead tibio |
| `appointment_reminder_hours` | 24 | Horas antes para enviar recordatorio |
| `welcome_message` | "¡Hola! Soy el asistente virtual..." | Mensaje de bienvenida personalizable |

### Variables de entorno configurables (backend/.env):
- `OPENAI_API_KEY` → Modelo GPT-4o para IA
- `WHATSAPP_PHONE_NUMBER_ID` / `WHATSAPP_ACCESS_TOKEN` → WhatsApp Cloud API
- `WEBHOOK_VERIFY_TOKEN` → Verificación del webhook
- `STRIPE_API_KEY` → Pagos con Stripe
- `RESEND_API_KEY` → Emails transaccionales
- `SMTP_*` → Alternativa SMTP para emails
- `NOTIFICATION_EMAILS` → Emails que reciben alertas de leads calientes
- `APP_SECRET` → Clave JWT para autenticación
- `CORS_ORIGINS` → Dominios permitidos

### Variables del frontend (.env):
- `REACT_APP_BACKEND_URL` → URL del backend
- `REACT_APP_BUSINESS_NAME` → Nombre de la inmobiliaria (landing)
- `REACT_APP_BUSINESS_TAGLINE` → Frase del hero (landing)
- `REACT_APP_WHATSAPP_NUMBER` → Número de WhatsApp (landing)

---

## AUTOMATIZACIONES PROGRAMADAS

### 1. Recordatorio de cita (24hs antes):
- Por WhatsApp: Mensaje con botones Confirmar / Reagendar / Cancelar
- Por Email: Notificación al equipo

### 2. Follow-up post-visita (48hs después):
- WhatsApp con botones: "Sigo interesado" / "Quiero otra visita" / "No por ahora"

### 3. Encuesta NPS (7 días después de cerrar):
- WhatsApp con opciones: 9-10 (Excelente) / 7-8 (Bueno) / 1-6 (Regular)
- Clasifica en Promoters, Passives, Detractors

### 4. Reactivación de leads tibios (configurable, default 7 días):
- Email de reactivación automático
- Máximo 1 email cada 7 días por lead

### 5. Detección de urgencia en tiempo real:
- Palabras clave: "urgente", "necesito ya", "lo antes posible", "hoy mismo", etc.
- Marca el lead como urgente automáticamente

---

## DASHBOARD COMPLETO

### Páginas del dashboard:
1. **Dashboard General** → Métricas: leads por día, conversión, pipeline, gráficos
2. **Gestión de Leads** → Lista con filtros, búsqueda, acciones masivas (tag, status, asignar, eliminar)
3. **Pipeline Kanban** → 8 columnas: Nuevos, Contactados, Calificados, Cita Agendada, Calientes, Tibios, Fríos, Cerrados. Drag & drop
4. **Calendario** → Citas agendadas en vista calendario
5. **Gestión Asesores** → CRUD de asesores, asignación de zonas y especialidades
6. **Broadcast** → Mensajes masivos con filtros (zona, intención, status, tags)
7. **Auditoría** → Timeline de todas las acciones del sistema
8. **Flujo Bot** → Visualización del flujo conversacional
9. **Configuración** → Variables del bot editables desde UI
10. **Mi Dashboard** (asesor) → Métricas personales del asesor

### Funcionalidades del dashboard:
- Modo oscuro/claro
- Sidebar colapsable con persistencia
- Notificaciones en tiempo real (WebSocket) con sonido
- Exportación CSV y reportes PDF
- Calculadora ROI
- Cambio de contraseña
- Banner de actualización disponible

---

## DETECCIÓN DE INTENCIÓN (Como se muestra en la imagen)

Sí, el bot maneja detección de intención automática:

### Trigger: "Quiero comprar" → Flujo de CIERRE RAPIDO
1. Confirma presupuesto
2. Pregunta zona y tipo
3. Propone 3 opciones
4. Agenda visita

### Trigger: "Estoy buscando" → Flujo de NUTRICION ACTIVA
1. Explora necesidades
2. Envía opciones variadas
3. Pregunta qué no le gusta
4. Propone reunión informal

### Trigger: "Cuánto vale mi casa" → Flujo de LEAD CAPTADO
1. Pide datos básicos
2. Ofrece tasación gratuita
3. Agenda visita presencial
4. Agrega como contacto

La detección se hace de 2 formas:
- **Botones interactivos**: Comprar / Alquilar / Vender (detección directa)
- **Texto libre con GPT-4**: Si el usuario escribe en lenguaje natural, GPT-4 clasifica la intención

---

## FAQ DEL BOT

El bot responde automáticamente sobre:
- Dirección/ubicación de la oficina
- Horarios de atención
- Formas de pago
- Contacto (teléfono, email, web)
- Requisitos para alquilar/comprar
- Precios (respuesta general + derivación a asesor)

Para preguntas que no están en el FAQ, usa GPT-4 para generar respuestas contextuales.

---

## MODELO DE DATOS DE UN LEAD

```
phone, name, flow_stage, intent (comprar/alquilar/vender/inversion),
zone, budget_text, property_type, bedrooms, must_have[], 
urgency (urgente/proximo_mes/meses/solo_mirando),
financing (efectivo/credito_hipotecario/credito_uva/procrear/mixto/no_se),
score (0-12), status (new/contacted/qualified/appointment/hot/warm/cold/completed),
appointment_type, appointment_datetime, is_urgent, tags[],
assigned_agent, conversation_history[], created_at, last_message_at
```

---

## PROPUESTA DE MASTERCLASS

**Título:** "Masterclass InmoBot: Secretos de Configuración Avanzada"

**Público:** Compradores recientes de InmoBot (inmobiliarias)

**Precio:** $15/mes (suscripción)

**Temas sugeridos para los módulos:**

1. **Módulo 1: Configuración del Bot para tu mercado**
   - Personalizar mensajes de bienvenida
   - Ajustar el scoring según tu tipo de operación
   - Configurar horarios y zonas
   - Personalizar el flujo de preguntas

2. **Módulo 2: Dominar la IA**
   - Cómo GPT-4 clasifica intenciones
   - Ajustar el prompt del bot para tu nicho
   - Usar Whisper para audios
   - Respuestas inteligentes personalizadas

3. **Módulo 3: Pipeline y Scoring Avanzado**
   - Entender el score de 12 puntos
   - Cuándo y cómo hacer handoff manual
   - Segmentación por temperatura (hot/warm/cold)
   - Acciones masivas y tags

4. **Módulo 4: Automatizaciones que Venden**
   - Recordatorios automáticos 24hs antes
   - Follow-up post-visita que recupera leads
   - Encuestas NPS que generan referidos
   - Reactivación de leads tibios

5. **Módulo 5: Broadcast y Campañas**
   - Mensajes masivos segmentados
   - Templates de WhatsApp que convierten
   - Timing óptimo para envíos
   - Personalización con {nombre}

6. **Módulo 6: Métricas y Reportes**
   - Leer el dashboard como un pro
   - KPIs que importan para inmobiliarias
   - Reportes PDF para dueños
   - Calculadora ROI

7. **Módulo 7: Hacks Avanzados**
   - Flujos personalizados para nichos (lujo, inversores, etc.)
   - Integración con CRM existente
   - Configurar múltiples asesores con zonas
   - Escalamiento: de 100 a 1000 leads/mes
