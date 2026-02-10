import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { 
  MessageSquare, Bot, Calendar, BarChart3, 
  Zap, Clock, CheckCircle, ArrowRight, Play
} from 'lucide-react';
import PublicROICalculator from '../components/PublicROICalculator';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-content">
          <img 
            src="https://customer-assets.emergentagent.com/job_lead-manager-es/artifacts/l1ys0o2g_ChatGPT%20Image%203%20feb%202026%2C%2009_57_44%20p.m..png" 
            alt="InmoBot Logo" 
            className="landing-logo"
          />
          <h1>InmoBot</h1>
          <p className="landing-tagline">
            El Bot de WhatsApp con IA que convierte consultas en ventas mientras dormís
          </p>
          <div className="landing-hero-buttons">
            <Button size="lg" onClick={() => navigate('/demo')} data-testid="btn-ver-demo">
              <Play className="w-4 h-4 mr-2" />
              Ver Demo
            </Button>
            <Button size="lg" variant="outline" onClick={() => navigate('/planes')} data-testid="btn-ver-precios">
              Ver Precios
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing-features">
        <h2>¿Por qué InmoBot?</h2>
        <div className="features-grid">
          <div className="feature-card">
            <Bot className="feature-icon" />
            <h3>Respuestas 24/7</h3>
            <p>Tu asistente nunca duerme. Responde consultas a cualquier hora, todos los días.</p>
          </div>
          <div className="feature-card">
            <MessageSquare className="feature-icon" />
            <h3>Calificación Automática</h3>
            <p>Identifica leads calientes automáticamente basándose en sus respuestas.</p>
          </div>
          <div className="feature-card">
            <Calendar className="feature-icon" />
            <h3>Agenda Visitas</h3>
            <p>El bot agenda citas directamente en tu calendario sin intervención manual.</p>
          </div>
          <div className="feature-card">
            <BarChart3 className="feature-icon" />
            <h3>Dashboard Completo</h3>
            <p>Métricas en tiempo real, historial de conversaciones y gestión de leads.</p>
          </div>
          <div className="feature-card">
            <Zap className="feature-icon" />
            <h3>Respuestas Inteligentes</h3>
            <p>Usa IA para responder preguntas complejas sobre propiedades y servicios.</p>
          </div>
          <div className="feature-card">
            <Clock className="feature-icon" />
            <h3>Setup en 24hs</h3>
            <p>Configuramos todo por vos. En menos de un día estás operativo.</p>
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

      {/* CTA Section */}
      <section className="landing-cta">
        <h2>¿Listo para automatizar tu inmobiliaria?</h2>
        <p>Unite a las inmobiliarias que ya están cerrando más ventas con InmoBot</p>
        <div className="cta-buttons">
          <Button size="lg" onClick={() => navigate('/planes')} data-testid="btn-empezar">
            Empezar Ahora
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          <Button size="lg" variant="outline" onClick={() => window.open('https://wa.me/5491159434074?text=Hola,%20quiero%20información%20sobre%20InmoBot', '_blank')}>
            <MessageSquare className="w-4 h-4 mr-2" />
            Contactar por WhatsApp
          </Button>
        </div>
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
            <a href="/planes">Precios</a>
            <a href="/privacy">Privacidad</a>
            <a href="/terms">Términos</a>
          </div>
          <p className="footer-copy">© 2025 InmoBot. Todos los derechos reservados.</p>
        </div>
      </footer>
    </div>
  );
}
