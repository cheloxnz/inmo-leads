import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { 
  MessageSquare, Bot, Calendar, BarChart3, 
  Zap, Clock, CheckCircle, ArrowRight, Play,
  Package, FileText, Video, Code, Download
} from 'lucide-react';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-content">
          <div className="hero-badge">🔥 Sistema completo - Tuyo para siempre</div>
          <img 
            src="https://customer-assets.emergentagent.com/job_lead-manager-es/artifacts/l1ys0o2g_ChatGPT%20Image%203%20feb%202026%2C%2009_57_44%20p.m..png" 
            alt="InmoBot Logo" 
            className="landing-logo"
          />
          <h1>InmoBot</h1>
          <p className="landing-tagline">
            Sistema de ventas con IA para inmobiliarias
          </p>
          <p className="landing-subtitle">
            Bot de WhatsApp + Dashboard completo + Código fuente incluido
          </p>
          <div className="landing-hero-buttons">
            <Button size="lg" onClick={() => navigate('/comprar')} data-testid="btn-comprar">
              <Download className="w-4 h-4 mr-2" />
              Comprar Ahora - $147 USD
            </Button>
            <Button size="lg" variant="outline" onClick={() => navigate('/demo')} data-testid="btn-ver-demo">
              <Play className="w-4 h-4 mr-2" />
              Ver Demo
            </Button>
          </div>
          <p className="hero-note">Un solo pago. Sin mensualidades. 100% tuyo.</p>
        </div>
      </section>

      {/* What's Included Section */}
      <section className="landing-included">
        <h2>¿Qué incluye?</h2>
        <div className="included-grid">
          <div className="included-item">
            <Code className="included-icon" />
            <h3>Código Fuente Completo</h3>
            <p>React + Python + MongoDB. Modificalo como quieras.</p>
          </div>
          <div className="included-item">
            <Bot className="included-icon" />
            <h3>Bot de WhatsApp con IA</h3>
            <p>Responde 24/7, califica leads, agenda visitas.</p>
          </div>
          <div className="included-item">
            <BarChart3 className="included-icon" />
            <h3>Dashboard de Gestión</h3>
            <p>Kanban, métricas, calendario, reportes.</p>
          </div>
          <div className="included-item">
            <FileText className="included-icon" />
            <h3>Documentación Completa</h3>
            <p>Guía paso a paso de instalación y uso.</p>
          </div>
          <div className="included-item">
            <Video className="included-icon" />
            <h3>Videos de Setup</h3>
            <p>Tutoriales para configurar todo.</p>
          </div>
          <div className="included-item">
            <Package className="included-icon" />
            <h3>Plantillas y Scripts</h3>
            <p>Mensajes, flujos, configuraciones listas.</p>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing-features">
        <h2>¿Qué hace el bot?</h2>
        <div className="features-grid">
          <div className="feature-card">
            <Bot className="feature-icon" />
            <h3>Respuestas 24/7</h3>
            <p>Tu asistente nunca duerme. Responde consultas a cualquier hora.</p>
          </div>
          <div className="feature-card">
            <MessageSquare className="feature-icon" />
            <h3>Calificación Automática</h3>
            <p>Identifica leads calientes automáticamente.</p>
          </div>
          <div className="feature-card">
            <Calendar className="feature-icon" />
            <h3>Agenda Visitas</h3>
            <p>El bot agenda citas directamente sin intervención.</p>
          </div>
          <div className="feature-card">
            <Zap className="feature-icon" />
            <h3>IA Integrada (GPT)</h3>
            <p>Respuestas inteligentes a preguntas complejas.</p>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="landing-stats">
        <div className="stats-container">
          <div className="stat-item">
            <span className="stat-number">&lt; 1 min</span>
            <span className="stat-text">Tiempo de respuesta</span>
          </div>
          <div className="stat-item">
            <span className="stat-number">24/7</span>
            <span className="stat-text">Disponibilidad</span>
          </div>
          <div className="stat-item">
            <span className="stat-number">+40%</span>
            <span className="stat-text">Más leads captados</span>
          </div>
          <div className="stat-item">
            <span className="stat-number">+25%</span>
            <span className="stat-text">Mejor conversión</span>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="landing-pricing">
        <h2>Precio único</h2>
        <div className="pricing-card-single">
          <div className="pricing-badge">Más vendido</div>
          <h3>InmoBot Completo</h3>
          <div className="pricing-price">
            <span className="price-old">$297</span>
            <span className="price-current">$147</span>
            <span className="price-currency">USD</span>
          </div>
          <p className="pricing-note">Un solo pago - Tuyo para siempre</p>
          <ul className="pricing-features">
            <li><CheckCircle className="w-4 h-4" /> Código fuente completo</li>
            <li><CheckCircle className="w-4 h-4" /> Bot de WhatsApp con IA</li>
            <li><CheckCircle className="w-4 h-4" /> Dashboard de gestión</li>
            <li><CheckCircle className="w-4 h-4" /> Documentación paso a paso</li>
            <li><CheckCircle className="w-4 h-4" /> Videos de instalación</li>
            <li><CheckCircle className="w-4 h-4" /> Actualizaciones gratuitas</li>
            <li><CheckCircle className="w-4 h-4" /> Licencia comercial</li>
          </ul>
          <Button size="lg" className="w-full" onClick={() => navigate('/comprar')}>
            Comprar Ahora
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="landing-faq">
        <h2>Preguntas Frecuentes</h2>
        <div className="faq-grid">
          <div className="faq-item">
            <h4>¿Necesito saber programar?</h4>
            <p>No. Viene con guía paso a paso y videos. Si sabés seguir instrucciones, podés instalarlo.</p>
          </div>
          <div className="faq-item">
            <h4>¿Incluye soporte?</h4>
            <p>Es un producto self-service con documentación completa. No incluye soporte personalizado.</p>
          </div>
          <div className="faq-item">
            <h4>¿Puedo modificarlo?</h4>
            <p>Sí, recibís el código fuente completo. Podés personalizarlo como quieras.</p>
          </div>
          <div className="faq-item">
            <h4>¿Qué costos tiene después?</h4>
            <p>Solo hosting (~$20/mes) y APIs (WhatsApp, OpenAI). Estimado: $50-100/mes.</p>
          </div>
          <div className="faq-item">
            <h4>¿Puedo revenderlo?</h4>
            <p>Sí, incluye licencia comercial. Podés usarlo para tus clientes.</p>
          </div>
          <div className="faq-item">
            <h4>¿Hay garantía?</h4>
            <p>Sí, 7 días. Si no funciona como se describe, te devolvemos el dinero.</p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="landing-cta">
        <h2>Automatizá tus ventas hoy</h2>
        <p>Dejá de perder leads. Empezá a cerrar más ventas con IA.</p>
        <div className="cta-buttons">
          <Button size="lg" onClick={() => navigate('/comprar')} data-testid="btn-empezar">
            Comprar Ahora - $147 USD
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
        <p className="cta-guarantee">✓ 7 días de garantía &nbsp; ✓ Pago seguro con Stripe</p>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <img 
              src="https://customer-assets.emergentagent.com/job_lead-manager-es/artifacts/l1ys0o2g_ChatGPT%20Image%203%20feb%202026%2C%2009_57_44%20p.m..png" 
              alt="InmoBot" 
              className="footer-logo"
            />
            <span>InmoBot</span>
          </div>
          <div className="footer-links">
            <a href="/demo">Demo</a>
            <a href="/comprar">Comprar</a>
            <a href="/privacy">Privacidad</a>
            <a href="/terms">Términos</a>
          </div>
          <p className="footer-copy">© 2025 InmoBot. Todos los derechos reservados.</p>
        </div>
      </footer>
    </div>
  );
}
