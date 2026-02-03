# Templates de WhatsApp para InmoBot AI

## ¿Qué son los Templates de WhatsApp?

Los **Message Templates** son mensajes pre-aprobados por Meta que se pueden enviar fuera de la ventana de 24 horas. Cada template debe ser aprobado antes de usarlo (proceso tarda 24-48 horas).

---

## 📋 Templates Recomendados para Inmobiliarias

### 1. SEGUIMIENTO_LEAD_TIBIO
**Categoría:** UTILITY  
**Idioma:** es (Español)  
**Uso:** Reactivar leads tibios después de 3 días sin actividad

**Contenido:**
```
Hola {{1}},

Te escribo de [Nombre Inmobiliaria]. Vi que estabas buscando {{2}} en {{3}}.

Tenemos nuevas opciones disponibles que podrían interesarte dentro de tu presupuesto.

¿Te gustaría que te envíe información actualizada?

Respondé *SÍ* para recibir detalles.
```

**Variables:**
- {{1}} = Nombre del lead
- {{2}} = Tipo de propiedad (ej: "departamento de 2 ambientes")
- {{3}} = Zona (ej: "Palermo")

---

### 2. RECORDATORIO_CITA
**Categoría:** UTILITY  
**Idioma:** es (Español)  
**Uso:** Recordatorio de cita 24hs antes

**Contenido:**
```
Hola {{1}},

Te recordamos que mañana {{2}} tenés tu {{3}} agendada.

📅 Fecha: {{4}}
🕐 Hora: {{5}}
📍 Dirección: {{6}}

Si necesitás reprogramar, avisanos respondiendo este mensaje.

¡Te esperamos!
[Nombre Inmobiliaria]
```

**Variables:**
- {{1}} = Nombre del lead
- {{2}} = Día (ej: "martes")
- {{3}} = Tipo de cita (ej: "visita", "llamada")
- {{4}} = Fecha completa (ej: "15/02/2026")
- {{5}} = Hora (ej: "15:00hs")
- {{6}} = Dirección o "Por videollamada"

---

### 3. NUEVA_PROPIEDAD_COINCIDE
**Categoría:** UTILITY  
**Idioma:** es (Español)  
**Uso:** Notificar cuando hay nueva propiedad que coincide con búsqueda

**Contenido:**
```
¡Hola {{1}}! 

Tenemos una novedad que puede interesarte 🏡

{{2}} en {{3}}
💰 Precio: {{4}}

Características:
✓ {{5}}

¿Querés más información o agendar una visita?

Respondé este mensaje y te cuento todos los detalles.
```

**Variables:**
- {{1}} = Nombre del lead
- {{2}} = Tipo y ambientes (ej: "Departamento 2 ambientes")
- {{3}} = Zona
- {{4}} = Precio en USD
- {{5}} = Características principales (ej: "Balcón, cochera, seguridad 24hs")

---

### 4. BIENVENIDA_REENGANCHE
**Categoría:** UTILITY  
**Idioma:** es (Español)  
**Uso:** Reactivar conversación después de 7 días

**Contenido:**
```
Hola {{1}}, ¿cómo estás?

Hace unos días estuvimos en contacto por tu búsqueda de {{2}} en {{3}}.

¿Seguís buscando? Tenemos varias opciones nuevas esta semana.

Si querés retomar la búsqueda, responde este mensaje y te ayudo a encontrar la propiedad ideal.

Saludos,
[Nombre Inmobiliaria]
```

**Variables:**
- {{1}} = Nombre del lead
- {{2}} = Tipo de propiedad
- {{3}} = Zona

---

### 5. CONFIRMACION_AGENDAMIENTO
**Categoría:** UTILITY  
**Idioma:** es (Español)  
**Uso:** Confirmar cita inmediatamente después de agendar

**Contenido:**
```
¡Perfecto {{1}}! ✅

Tu {{2}} quedó confirmada:

📅 Día: {{3}}
🕐 Hora: {{4}}
👤 Asesor: {{5}}

Te vamos a estar enviando un recordatorio 24hs antes.

¡Nos vemos!
[Nombre Inmobiliaria]
```

**Variables:**
- {{1}} = Nombre del lead
- {{2}} = Tipo (ej: "visita", "llamada")
- {{3}} = Fecha (ej: "Lunes 15/02")
- {{4}} = Hora (ej: "15:00hs")
- {{5}} = Nombre del asesor

---

## 🚀 Cómo Crear y Aprobar Templates en Meta

### Paso 1: Acceder a WhatsApp Manager
1. Ve a https://business.facebook.com
2. Selecciona tu Business Account
3. En el menú izquierdo: **WhatsApp Manager**
4. Click en **Message Templates**

### Paso 2: Crear Nuevo Template
1. Click en **Create Template**
2. Completa los campos:
   - **Name:** nombre en minúsculas sin espacios (ej: `seguimiento_lead_tibio`)
   - **Category:** UTILITY (para seguimiento) o MARKETING
   - **Languages:** Spanish (es)

### Paso 3: Contenido del Template
1. Ingresa el texto del template
2. Para variables usa el formato: `{{1}}`, `{{2}}`, etc.
3. **Importante:** Máximo 1024 caracteres
4. Evita lenguaje de venta agresiva
5. Incluye opt-out option (ej: "Respondé STOP para no recibir más mensajes")

### Paso 4: Enviar a Aprobación
1. Revisa el preview
2. Click en **Submit**
3. Espera 24-48 horas para la aprobación

### Paso 5: Usar en Código
Una vez aprobado, usalo así:

```python
# Ejemplo: Enviar template de seguimiento
wa_service.send_template_message(
    recipient_phone="5491134567890",
    template_name="seguimiento_lead_tibio",
    language_code="es",
    parameters=[
        {"type": "text", "text": "Juan"},  # {{1}} - Nombre
        {"type": "text", "text": "departamento 2 ambientes"},  # {{2}} - Tipo
        {"type": "text", "text": "Palermo"}  # {{3}} - Zona
    ]
)
```

---

## ✅ Checklist de Aprobación

Para que tus templates sean aprobados:

- ✅ **No incluir URLs acortadas** (usa URLs completas)
- ✅ **Lenguaje profesional** (sin emojis excesivos)
- ✅ **Información clara** sobre quién envía el mensaje
- ✅ **Opción de opt-out** ("Respondé STOP si no querés recibir mensajes")
- ✅ **Variables claras** ({{1}}, {{2}}, etc.)
- ✅ **No promesas falsas** o lenguaje engañoso
- ✅ **Cumplir políticas de WhatsApp Business**

---

## ⚠️ Errores Comunes a Evitar

❌ **URLs acortadas** (bit.ly, tinyurl, etc.)  
✅ Usar: `https://nombreinmobiliaria.com/propiedades`

❌ **Muchos emojis** 🏡🔥💰✨🎉  
✅ Usar: 1-2 emojis relevantes máximo

❌ **Lenguaje agresivo** ("¡Oferta limitada! Comprá YA!")  
✅ Usar: "Tenemos opciones que podrían interesarte"

❌ **Sin identificación** (no dice quién envía)  
✅ Siempre incluir: [Nombre Inmobiliaria]

❌ **Variables incorrectas** ({{nombre}} en vez de {{1}})  
✅ Usar: {{1}}, {{2}}, {{3}} secuencialmente

---

## 📊 Métricas de Templates

Una vez que uses los templates, monitorea:

- **Tasa de entrega** (delivery rate)
- **Tasa de lectura** (read rate)
- **Tasa de respuesta** (response rate)
- **Tasa de opt-out** (usuarios que piden dejar de recibir)

**Objetivo:**
- Delivery rate: >95%
- Read rate: >60%
- Response rate: >10%
- Opt-out rate: <2%

---

## 🔄 Integración con InmoBot AI

El sistema está preparado para usar templates automáticamente:

1. **Reactivación automática** (3 días): Usa `seguimiento_lead_tibio`
2. **Recordatorio de citas** (24hs antes): Usa `recordatorio_cita`
3. **Nuevas propiedades**: Usa `nueva_propiedad_coincide`

Los templates se activan cuando:
- El lead no responde en 24hs (ventana cerrada)
- El bot necesita enviar mensaje fuera de horario
- Seguimiento programado (3, 7 días)

---

## 📞 Soporte

Si tus templates son rechazados:
1. Revisa la razón del rechazo en WhatsApp Manager
2. Ajusta el contenido según las políticas
3. Reenvía a aprobación
4. Si persiste: contacta soporte de Meta

**Recursos:**
- [WhatsApp Business Policies](https://www.whatsapp.com/legal/business-policy)
- [Template Guidelines](https://developers.facebook.com/docs/whatsapp/message-templates/guidelines)
- [Meta Business Support](https://business.facebook.com/business/help)

---

**InmoBot AI** - Sistema de Automatización para Inmobiliarias 🏡
