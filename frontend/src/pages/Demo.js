import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useNavigate } from 'react-router-dom';
import { 
  MessageSquare, BarChart3, Calendar, Bell, 
  Users, Clock, Zap, CheckCircle, ArrowRight,
  Play, Smartphone, Monitor
} from 'lucide-react';

export default function Demo() {
  const navigate = useNavigate();
  const [activeFeature, setActiveFeature] = useState('bot');

  const features = {
    bot: {
      title: "Bot de WhatsApp con IA",
      description: "Tu asistente virtual que nunca duerme",
      points: [
        "Responde consultas automáticamente 24/7",
        "Califica leads según intención, presupuesto y zona",
        "Agenda citas sin intervención humana",
        "Entiende mensajes de voz con IA",
        "Detecta urgencias y notifica al instante"
      ],
      demo: {
        type: "chat",
        messages: [
          { from: "client", text: "Hola, busco un depto de 2 ambientes en Palermo" },
          { from: "bot", text: "¡Hola! 👋 Soy el asistente de la inmobiliaria. ¡Qué bueno que nos contactes!\n\n¿Estás buscando para comprar o alquilar?" },
          { from: "client", text: "Para alquilar" },
          { from: "bot", text: "Perfecto 🏠 ¿Cuál es tu presupuesto aproximado mensual?" },
          { from: "client", text: "Hasta 400 mil pesos" },
          { from: "bot", text: "¡Excelente! Tenemos varias opciones en Palermo dentro de ese rango.\n\n¿Te gustaría agendar una visita con un asesor?" },
          { from: "client", text: "Si, el jueves a la tarde" },
          { from: "bot", text: "✅ ¡Perfecto! Tu cita quedó agendada para:\n📅 Jueves 14/02 a las 15:00hs\n\nUn asesor te contactará para confirmar. ¡Gracias! 🙌" }
        ]
      }
    },
    dashboard: {
      title: "Dashboard Completo",
      description: "Todo tu negocio en una pantalla",
      points: [
        "Métricas en tiempo real",
        "Funnel de conversión visual",
        "Lista de leads con filtros avanzados",
        "Historial de conversaciones",
        "Exportación a Excel/CSV"
      ],
      demo: {
        type: "stats",
        stats: [
          { label: "Leads este mes", value: "147", trend: "+23%" },
          { label: "Citas agendadas", value: "52", trend: "+18%" },
          { label: "Tasa conversión", value: "35%", trend: "+5%" },
          { label: "Tiempo respuesta", value: "< 1 min", trend: "24/7" }
        ]
      }
    },
    calendar: {
      title: "Calendario Integrado",
      description: "Todas las citas en un solo lugar",
      points: [
        "Vista mensual de todas las citas",
        "Citas agendadas automáticamente por el bot",
        "Recordatorios 24hs antes",
        "Reagendamiento desde WhatsApp",
        "Sincronización con asesores"
      ],
      demo: {
        type: "calendar"
      }
    },
    notifications: {
      title: "Notificaciones Inteligentes",
      description: "Nunca pierdas un lead importante",
      points: [
        "Alertas de leads urgentes con sonido",
        "Notificación cuando un cliente responde",
        "Aviso de leads calientes (hot)",
        "Recordatorios de seguimiento",
        "Todo en tiempo real via WebSocket"
      ],
      demo: {
        type: "notifications",
        items: [
          { type: "urgent", title: "🚨 URGENTE", message: "Nuevo lead requiere atención inmediata", time: "Ahora" },
          { type: "hot", title: "🔥 Lead Caliente", message: "María García - Interesada en comprar", time: "2 min" },
          { type: "reply", title: "💬 Nueva respuesta", message: "Cliente confirmó visita para mañana", time: "5 min" },
          { type: "appointment", title: "📅 Cita agendada", message: "Juan Pérez - Jueves 15:00", time: "10 min" }
        ]
      }
    },
    team: {
      title: "Gestión de Equipo",
      description: "Asignación inteligente de leads",
      points: [
        "Asignación automática según zona/especialidad",
        "Balance de carga entre asesores",
        "Métricas por asesor",
        "Reasignación manual si es necesario",
        "Cada asesor ve solo sus leads"
      ],
      demo: {
        type: "team",
        agents: [
          { name: "María López", leads: 12, zone: "Palermo", status: "online" },
          { name: "Carlos García", leads: 8, zone: "Belgrano", status: "online" },
          { name: "Ana Martínez", leads: 15, zone: "Recoleta", status: "busy" }
        ]
      }
    }
  };

  const renderDemo = (feature) => {
    const demo = feature.demo;
    
    switch (demo.type) {
      case 'chat':
        return (
          <div className="demo-chat">
            <div className="chat-header">
              <Smartphone className="w-5 h-5" />
              <span>WhatsApp Business</span>
            </div>
            <div className="chat-messages">
              {demo.messages.map((msg, idx) => (
                <div key={idx} className={`chat-message ${msg.from}`}>
                  <div className="message-bubble">{msg.text}</div>
                </div>
              ))}
            </div>
          </div>
        );
      
      case 'stats':
        return (
          <div className="demo-stats">
            <div className="stats-header">
              <Monitor className="w-5 h-5" />
              <span>Dashboard</span>
            </div>
            <div className="stats-grid">
              {demo.stats.map((stat, idx) => (
                <div key={idx} className="stat-card">
                  <div className="stat-value">{stat.value}</div>
                  <div className="stat-label">{stat.label}</div>
                  <div className="stat-trend">{stat.trend}</div>
                </div>
              ))}
            </div>
          </div>
        );
      
      case 'notifications':
        return (
          <div className="demo-notifications">
            <div className="notifications-header">
              <Bell className="w-5 h-5" />
              <span>Notificaciones</span>
            </div>
            <div className="notifications-list">
              {demo.items.map((item, idx) => (
                <div key={idx} className={`notification-item ${item.type}`}>
                  <div className="notification-title">{item.title}</div>
                  <div className="notification-message">{item.message}</div>
                  <div className="notification-time">{item.time}</div>
                </div>
              ))}
            </div>
          </div>
        );
      
      case 'team':
        return (
          <div className="demo-team">
            <div className="team-header">
              <Users className="w-5 h-5" />
              <span>Equipo</span>
            </div>
            <div className="team-list">
              {demo.agents.map((agent, idx) => (
                <div key={idx} className="team-member">
                  <div className={`member-status ${agent.status}`}></div>
                  <div className="member-info">
                    <div className="member-name">{agent.name}</div>
                    <div className="member-zone">{agent.zone}</div>
                  </div>
                  <div className="member-leads">{agent.leads} leads</div>
                </div>
              ))}
            </div>
          </div>
        );
      
      case 'calendar':
        return (
          <div className="demo-calendar">
            <div className="calendar-header">
              <Calendar className="w-5 h-5" />
              <span>Febrero 2026</span>
            </div>
            <div className="calendar-grid-demo">
              {['L', 'M', 'M', 'J', 'V', 'S', 'D'].map((d, i) => (
                <div key={i} className="calendar-day-header">{d}</div>
              ))}
              {[...Array(31)].map((_, i) => (
                <div key={i} className={`calendar-day-demo ${[5, 8, 12, 15, 19, 22, 26].includes(i+1) ? 'has-event' : ''}`}>
                  {i + 1}
                </div>
              ))}
            </div>
          </div>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="demo-page" data-testid="demo-page">
      {/* Hero */}
      <section className="demo-hero">
        <Badge className="demo-badge">Demo Interactiva</Badge>
        <h1>Mirá InmoBot en Acción</h1>
        <p>Explorá cada funcionalidad y descubrí cómo puede transformar tu inmobiliaria</p>
      </section>

      {/* Video Demo */}
      <section className="demo-video-section" data-testid="demo-video-section">
        <div className="video-container">
          <h2>
            <Play className="video-play-icon" />
            Video Demostración
          </h2>
          <p className="video-subtitle">Mirá en 3 minutos cómo InmoBot puede transformar tu negocio</p>
          <div className="video-wrapper">
            <video 
              controls 
              className="demo-video"
              data-testid="demo-video"
            >
              <source 
                src="https://customer-assets.emergentagent.com/job_lead-manager-es/artifacts/tzee2168_demo-inmobot.mp4" 
                type="video/mp4" 
              />
              Tu navegador no soporta la reproducción de videos.
            </video>
          </div>
        </div>
      </section>

      {/* Feature Selector */}
      <section className="demo-content">
        <div className="feature-tabs">
          {Object.entries(features).map(([key, feature]) => (
            <button
              key={key}
              className={`feature-tab ${activeFeature === key ? 'active' : ''}`}
              onClick={() => setActiveFeature(key)}
            >
              {key === 'bot' && <MessageSquare className="w-4 h-4" />}
              {key === 'dashboard' && <BarChart3 className="w-4 h-4" />}
              {key === 'calendar' && <Calendar className="w-4 h-4" />}
              {key === 'notifications' && <Bell className="w-4 h-4" />}
              {key === 'team' && <Users className="w-4 h-4" />}
              <span>{feature.title.split(' ')[0]}</span>
            </button>
          ))}
        </div>

        <div className="feature-display">
          <div className="feature-info">
            <h2>{features[activeFeature].title}</h2>
            <p className="feature-subtitle">{features[activeFeature].description}</p>
            <ul className="feature-points">
              {features[activeFeature].points.map((point, idx) => (
                <li key={idx}>
                  <CheckCircle className="w-5 h-5" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="feature-demo">
            {renderDemo(features[activeFeature])}
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section className="demo-how-it-works">
        <h2>¿Cómo Funciona?</h2>
        <div className="steps-grid">
          <div className="step-card">
            <div className="step-number">1</div>
            <h3>Cliente escribe</h3>
            <p>Un cliente interesado envía un mensaje a tu WhatsApp Business</p>
          </div>
          <div className="step-arrow"><ArrowRight /></div>
          <div className="step-card">
            <div className="step-number">2</div>
            <h3>Bot responde</h3>
            <p>El bot con IA responde al instante, califica al lead y agenda cita</p>
          </div>
          <div className="step-arrow"><ArrowRight /></div>
          <div className="step-card">
            <div className="step-number">3</div>
            <h3>Vos cerrás</h3>
            <p>Recibís el lead calificado con toda la info lista para cerrar la venta</p>
          </div>
        </div>
      </section>

      {/* Results */}
      <section className="demo-results">
        <h2>Resultados Típicos</h2>
        <div className="results-grid">
          <div className="result-card">
            <Zap className="result-icon" />
            <div className="result-value">&lt; 1 min</div>
            <div className="result-label">Tiempo de respuesta</div>
            <div className="result-compare">vs 2-4 horas promedio</div>
          </div>
          <div className="result-card">
            <Clock className="result-icon" />
            <div className="result-value">24/7</div>
            <div className="result-label">Disponibilidad</div>
            <div className="result-compare">incluso fines de semana</div>
          </div>
          <div className="result-card">
            <BarChart3 className="result-icon" />
            <div className="result-value">+40%</div>
            <div className="result-label">Más leads captados</div>
            <div className="result-compare">por respuesta inmediata</div>
          </div>
          <div className="result-card">
            <Users className="result-icon" />
            <div className="result-value">+25%</div>
            <div className="result-label">Conversión</div>
            <div className="result-compare">leads mejor calificados</div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="demo-cta">
        <h2>¿Listo para automatizar tu inmobiliaria?</h2>
        <p>Empezá hoy y captá más leads mientras dormís</p>
        <div className="cta-buttons">
          <Button size="lg" onClick={() => navigate('/planes')} data-testid="btn-ver-planes">
            Ver Planes y Precios
          </Button>
          <Button size="lg" variant="outline" onClick={() => window.open('https://wa.me/5491159434074?text=Hola,%20quiero%20una%20demo%20de%20InmoBot', '_blank')}>
            <MessageSquare className="w-4 h-4 mr-2" />
            Solicitar Demo en Vivo
          </Button>
        </div>
      </section>
    </div>
  );
}
