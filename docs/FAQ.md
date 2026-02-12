# InmoBot - Preguntas Frecuentes (FAQ)

## General

### ¿Necesito saber programar para usar InmoBot?
**No para el uso diario.** El dashboard es completamente visual. Solo necesitarías conocimientos técnicos básicos para:
- Cambiar textos del bot (editar archivos de texto)
- Actualizar el sistema (comandos simples de git)

### ¿Puedo usar InmoBot en múltiples sucursales?
**Sí.** Cada sucursal puede tener su propio número de WhatsApp conectado. Se configura agregando múltiples `WHATSAPP_PHONE_NUMBER_ID`.

### ¿El bot responde en otros idiomas?
**Sí.** El bot usa GPT que entiende múltiples idiomas. Los mensajes predefinidos están en español pero pueden traducirse fácilmente.

---

## WhatsApp

### ¿Necesito WhatsApp Business o sirve WhatsApp normal?
**Necesitás WhatsApp Business API** (no la app normal). Se gestiona desde Meta Business Suite y tiene costo por conversación después de las primeras 1000 gratis/mes.

### ¿Puedo usar mi número actual de WhatsApp?
**No recomendado.** WhatsApp Business API requiere un número dedicado. Si usás tu número personal, perderás acceso a WhatsApp normal en ese número.

### ¿Por qué el bot no responde?
Causas comunes:
1. **Token expirado:** Los tokens temporales duran 24hs. Generá uno permanente.
2. **Webhook mal configurado:** Verificá que la URL sea correcta y accesible.
3. **Número no verificado:** Meta puede tardar en aprobar números nuevos.

### ¿Cuánto cuesta WhatsApp Business API?
- **Primeras 1000 conversaciones/mes:** Gratis
- **Conversaciones adicionales:** ~$0.05-0.15 según país y tipo
- **Más info:** https://developers.facebook.com/docs/whatsapp/pricing

---

## Inteligencia Artificial

### ¿Qué modelo de IA usa el bot?
**GPT-4** de OpenAI por defecto. Puede cambiarse a GPT-3.5 (más barato) editando `llm_service.py`.

### ¿Cuánto cuesta la IA por mes?
Aproximadamente:
- **GPT-4:** $0.03-0.10 por conversación
- **100 leads/mes:** $3-10/mes
- **GPT-3.5 (alternativa):** 10x más barato

### ¿El bot aprende de las conversaciones?
**No automáticamente.** GPT no guarda ni aprende de conversaciones individuales. Para "entrenar" al bot con información específica, debés editar los prompts en el código.

### ¿Puedo usar otro proveedor de IA?
**Sí.** El código puede adaptarse para usar:
- Claude (Anthropic)
- Gemini (Google)
- Modelos open source (Llama, Mistral)

---

## Pagos y Stripe

### ¿Stripe cobra comisión?
**Sí:** 2.9% + $0.30 por transacción exitosa en la mayoría de países.

### ¿Puedo usar otro procesador de pagos?
**Sí**, pero requiere modificar el código. Alternativas:
- MercadoPago (Latam)
- PayPal
- Transferencias bancarias (manual)

### ¿El sistema guarda datos de tarjetas?
**No.** Stripe maneja toda la información sensible. InmoBot solo recibe confirmación de pago.

---

## Base de Datos

### ¿Dónde se guardan los datos?
En **MongoDB**, que puede estar en:
- MongoDB Atlas (nube, recomendado)
- Servidor propio (más complejo)

### ¿Cómo hago backup de los datos?
- **MongoDB Atlas:** Backups automáticos incluidos en planes pagos
- **Manual:** Usar `mongodump` para exportar

### ¿Puedo exportar los leads?
**Sí.** Desde el dashboard podés exportar a CSV. También podés acceder directamente a la base de datos.

---

## Hosting y Servidor

### ¿Railway o DigitalOcean?
| Aspecto | Railway | DigitalOcean |
|---------|---------|--------------|
| Facilidad | Muy fácil | Media |
| Costo inicial | $5/mes | $12/mes |
| Escalabilidad | Automática | Manual |
| Control | Limitado | Total |

**Recomendación:** Railway para empezar, DigitalOcean si crecés mucho.

### ¿Cuántos leads soporta el sistema?
**Miles.** La arquitectura escala bien. Limitaciones típicas:
- MongoDB Atlas Free: 512MB (suficiente para ~50,000 leads)
- Railway Hobby: Suficiente para 500+ leads/mes

### ¿Qué pasa si el servidor se cae?
- **Railway:** Reinicio automático
- **DigitalOcean:** Configurar monitoreo con PM2 o UptimeRobot

---

## Personalización

### ¿Puedo cambiar los colores y logo?
**Sí:**
- Logo: Reemplazar `/frontend/public/logo.png`
- Colores: Editar variables CSS en `/frontend/src/App.css`
- Favicon: Reemplazar `/frontend/public/favicon.ico`

### ¿Puedo agregar nuevas funcionalidades?
**Sí**, tenés el código fuente completo. Funcionalidades comunes que podrías agregar:
- Integración con CRM externo
- Reportes personalizados
- Nuevos flujos de conversación

### ¿Puedo cambiar los mensajes del bot?
**Sí.** Todos los mensajes están en archivos de texto en `/backend/bot/`. Solo editá y reiniciá el servidor.

---

## Soporte y Actualizaciones

### ¿Qué incluye el soporte?
**Durante el período incluido:**
- Corrección de bugs
- Ayuda con configuración
- Respuesta en 24-48hs

**No incluye:**
- Nuevas funcionalidades
- Cambios de diseño mayores
- Capacitación adicional

### ¿Cómo recibo actualizaciones?
Durante los 6 meses de actualizaciones (Plan Premium):
1. Te notificamos por email cuando hay update
2. Vos hacés `git pull` en tu servidor
3. O Railway lo hace automático si está conectado

### ¿Qué pasa cuando termina el soporte?
- El sistema **sigue funcionando** sin problemas
- Solo no tendrás asistencia técnica incluida
- Podés contratar soporte extendido o un desarrollador externo

---

## Seguridad

### ¿Los datos están seguros?
**Sí:**
- Conexiones HTTPS encriptadas
- Passwords hasheados (bcrypt)
- Tokens JWT para autenticación
- MongoDB Atlas tiene seguridad enterprise

### ¿Cumplen con GDPR/protección de datos?
El sistema permite:
- Exportar datos de un usuario
- Eliminar datos de un usuario
- Ver historial de acciones (auditoría)

Pero **vos sos responsable** de:
- Política de privacidad
- Consentimiento de usuarios
- Cumplimiento legal local

### ¿Puedo limitar acceso por usuario?
**Actualmente:** Hay un solo nivel de admin.
**Futuro:** Se puede agregar sistema de roles si lo necesitás.

---

## Problemas Comunes

### "Error de conexión a base de datos"
1. Verificá que `MONGO_URL` no tenga comillas extra
2. Verificá que tu IP esté en whitelist de MongoDB Atlas
3. Verificá usuario y contraseña

### "El bot no responde a mensajes"
1. Verificá el token de WhatsApp (pueden expirar)
2. Verificá que el webhook esté configurado
3. Revisá los logs del backend

### "No puedo acceder al dashboard"
1. Verificá que el frontend esté corriendo
2. Verificá la URL de `REACT_APP_BACKEND_URL`
3. Limpiá caché del navegador

### "Los emails no llegan"
1. Verificá configuración SMTP/Resend
2. Revisá carpeta de spam
3. Verificá que el dominio esté validado en Resend

---

## Contacto

**Durante período de soporte:**
- Email: [TU_EMAIL]
- WhatsApp: [TU_NUMERO]
- Horario: Lun-Vie 9:00-18:00

**Emergencias fuera de horario:**
- Solo para sistema completamente caído
- Respuesta en 4-8 horas
