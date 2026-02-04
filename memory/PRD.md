# InmoBot AI - PRD (Product Requirements Document)

## Descripción del Proyecto
Sistema CRM multi-agente para inmobiliarias con bot de WhatsApp para calificación automática de leads, asignación inteligente y gestión por roles.

## Estado Actual: ✅ Sistema Multi-Usuario Implementado

### Funcionalidades Implementadas

#### 1. ✅ Autenticación JWT
- Login con email/password
- Tokens JWT con expiración de 7 días
- Middleware de autenticación en endpoints protegidos
- Logout funcional

#### 2. ✅ Roles y Permisos
- **Admin**: 
  - Dashboard general con estadísticas globales
  - Ver todos los leads
  - Gestionar asesores (CRUD completo)
  - Configuración del sistema
- **Asesor**:
  - Dashboard personal con métricas propias
  - Ver solo leads asignados
  - Visualizar flujo del bot

#### 3. ✅ CRUD Asesores
- Crear nuevo asesor con:
  - Nombre, email, teléfono
  - Especialidades (comprar, alquilar, inversion, ambos)
  - Zonas asignadas (Palermo, Recoleta, etc.)
  - Límite máximo de leads concurrentes
- Editar información de asesores
- Activar/Desactivar asesores
- Eliminar asesores

#### 4. ✅ Asignación Automática Híbrida
- Cuando un lead se vuelve HOT, se asigna automáticamente
- Criterios de asignación:
  - Especialidad del asesor vs intención del lead
  - Zona del asesor vs zona del lead
  - Carga actual de trabajo (menor cantidad de leads activos)
- El asesor con mejor match y menor carga recibe el lead

#### 5. ✅ Dashboard por Asesor
- Métricas personales:
  - Leads activos / máximo
  - Total asignados
  - Con cita agendada
  - Tasa de conversión
  - Score promedio
- Secciones de alertas:
  - Citas próximas (1 hora)
  - Leads sin actividad (3+ días)
- Tabla de leads recientes asignados

#### 6. ✅ Métricas por Asesor (Admin)
- Vista de rendimiento de todos los asesores
- Indicador de sobrecarga (cuando excede max_concurrent_leads)
- Comparativa de conversiones

#### 7. ✅ Sistema de Notificaciones en Tiempo Real (WebSocket)
Backend implementado con los siguientes eventos:
- 🔥 Nuevo lead asignado
- 💬 Cliente respondió en WhatsApp
- 🎯 Lead de alto valor detectado (>$500k)
- ⏰ Recordatorio de cita próxima
- 🟡 Lead tibio sin actividad
- ⚠️ Asesor sobrecargado
- 🎉 Meta diaria alcanzada

### Credenciales de Prueba
- **Admin**: admin@inmobot.com / Admin123!
- **Asesor**: maria@inmobot.com / Maria123!

### Arquitectura Técnica

#### Backend (FastAPI)
```
/app/backend/
├── server.py          # API principal + WebSocket
├── auth.py            # JWT utils
├── auth_routes.py     # Endpoints de autenticación
├── assignment.py      # Motor de asignación
├── models.py          # Pydantic models
├── bot_flow.py        # Lógica del bot WhatsApp
├── email_service.py   # Notificaciones por email
└── scheduler.py       # Tareas programadas
```

#### Frontend (React)
```
/app/frontend/src/
├── App.js                     # Rutas y navegación
├── context/
│   ├── AuthContext.js         # Estado de autenticación
│   └── NotificationContext.js # WebSocket notificaciones
├── pages/
│   ├── Login.js               # Login
│   ├── Dashboard.js           # Dashboard admin
│   ├── MyDashboard.js         # Dashboard asesor
│   ├── AgentManagement.js     # Gestión asesores
│   ├── Leads.js               # Lista de leads
│   └── LeadDetail.js          # Detalle de lead
└── components/
    └── NotificationBell.js    # Campanita de notificaciones
```

### Endpoints API Principales
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Info usuario actual
- `GET /api/auth/agents` - Listar asesores
- `POST /api/auth/register` - Crear asesor
- `PUT /api/auth/agents/{email}` - Actualizar asesor
- `DELETE /api/auth/agents/{email}` - Eliminar asesor
- `GET /api/metrics/agent/{email}` - Métricas de un asesor
- `GET /api/metrics/all-agents` - Métricas de todos (admin)
- `GET /api/leads/assigned-to-me` - Leads del asesor actual
- `WS /ws/notifications?token=JWT` - WebSocket notificaciones

---

## Backlog y Próximos Pasos

### P1 - Prioridad Alta
- [ ] Mejorar UI del componente de notificaciones (campanita en header)
- [ ] Añadir filtros avanzados en la gestión de asesores
- [ ] Implementar cambio de contraseña
- [ ] Probar asignación automática con leads reales de WhatsApp

### P2 - Prioridad Media
- [ ] Exportar métricas a Excel/PDF
- [ ] Historial de asignaciones de leads
- [ ] Reasignación manual de leads entre asesores
- [ ] Notificaciones por email al asesor cuando recibe lead

### P3 - Prioridad Baja
- [ ] Dark mode
- [ ] Reportes semanales automáticos
- [ ] Integración con Google Analytics
- [ ] App móvil PWA

---

## Integraciones Activas
- ✅ WhatsApp Cloud API
- ✅ Gmail SMTP (notificaciones)
- ✅ Emergent LLM (GPT para conversaciones)
- 🔶 Google Sheets (configurado, pendiente credenciales)
- 🔶 Google Calendar (configurado, pendiente credenciales)

---

## Changelog

### 2026-02-04
- ✅ Implementado sistema completo de autenticación JWT
- ✅ Creado sistema de roles (Admin/Asesor)
- ✅ Implementado CRUD de asesores con especialidades y zonas
- ✅ Creado motor de asignación automática híbrida
- ✅ Implementado dashboard personal para asesores
- ✅ Agregadas métricas por asesor para admin
- ✅ Implementado WebSocket para notificaciones en tiempo real
- ✅ Corregido bug de ordenamiento de rutas (/leads/assigned-to-me)
- ✅ Testeado con pytest (95.5% success rate)
