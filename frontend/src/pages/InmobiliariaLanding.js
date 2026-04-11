import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { 
  MessageSquare, Bot, Clock, CheckCircle, ArrowRight, 
  Home, Phone, MapPin, Shield, Star, Users, Sparkles
} from 'lucide-react';

const BUSINESS_NAME = process.env.REACT_APP_BUSINESS_NAME || 'Tu Inmobiliaria';
const WHATSAPP_NUMBER = process.env.REACT_APP_WHATSAPP_NUMBER || '';
const BUSINESS_TAGLINE = process.env.REACT_APP_BUSINESS_TAGLINE || 'Encontra tu propiedad ideal con atención inmediata';

export default function InmobiliariaLanding() {
  const navigate = useNavigate();

  const whatsappLink = WHATSAPP_NUMBER 
    ? `https://wa.me/${WHATSAPP_NUMBER.replace(/[^0-9]/g, '')}?text=Hola,%20me%20interesa%20consultar%20por%20propiedades`
    : '#';

  return (
    <div className="immo-landing">
      {/* Navbar */}
      <nav className="immo-nav">
        <div className="immo-nav-inner">
          <div className="immo-nav-brand">
            <Home className="w-6 h-6" />
            <span>{BUSINESS_NAME}</span>
          </div>
          <div className="immo-nav-links">
            <a href="#servicios">Servicios</a>
            <a href="#como-funciona">Como funciona</a>
            <a href="#contacto">Contacto</a>
            <Button size="sm" variant="outline" onClick={() => navigate('/login')} data-testid="btn-login-nav">
              Acceder
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="immo-hero">
        <div className="immo-hero-content">
          <div className="immo-hero-badge">
            <Sparkles className="w-4 h-4" />
            Atención con Inteligencia Artificial 24/7
          </div>
          <h1>{BUSINESS_NAME}</h1>
          <p className="immo-hero-tagline">{BUSINESS_TAGLINE}</p>
          <p className="immo-hero-sub">
            Escribinos por WhatsApp y nuestro asistente virtual te ayuda al instante: 
            buscar propiedades, agendar visitas y resolver tus dudas.
          </p>
          <div className="immo-hero-buttons">
            {WHATSAPP_NUMBER && (
              <Button size="lg" asChild data-testid="btn-whatsapp-hero">
                <a href={whatsappLink} target="_blank" rel="noopener noreferrer">
                  <MessageSquare className="w-5 h-5 mr-2" />
                  Escribinos por WhatsApp
                </a>
              </Button>
            )}
            <Button size="lg" variant="outline" onClick={() => {
              document.getElementById('servicios')?.scrollIntoView({ behavior: 'smooth' });
            }} data-testid="btn-ver-servicios">
              Ver Servicios
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="immo-stats">
        <div className="immo-stats-grid">
          <div className="immo-stat">
            <Clock className="w-8 h-8" />
            <span className="immo-stat-number">24/7</span>
            <span className="immo-stat-label">Atención inmediata</span>
          </div>
          <div className="immo-stat">
            <MessageSquare className="w-8 h-8" />
            <span className="immo-stat-number">&lt; 1 min</span>
            <span className="immo-stat-label">Tiempo de respuesta</span>
          </div>
          <div className="immo-stat">
            <Users className="w-8 h-8" />
            <span className="immo-stat-number">100%</span>
            <span className="immo-stat-label">Consultas atendidas</span>
          </div>
          <div className="immo-stat">
            <Star className="w-8 h-8" />
            <span className="immo-stat-number">IA</span>
            <span className="immo-stat-label">Asistente inteligente</span>
          </div>
        </div>
      </section>

      {/* Servicios */}
      <section className="immo-services" id="servicios">
        <h2>Nuestros Servicios</h2>
        <p className="immo-section-sub">Tecnología de punta para la mejor experiencia inmobiliaria</p>
        <div className="immo-services-grid">
          <div className="immo-service-card">
            <div className="immo-service-icon">
              <Bot className="w-8 h-8" />
            </div>
            <h3>Asistente Virtual por WhatsApp</h3>
            <p>Nuestro bot con inteligencia artificial responde tus consultas al instante, las 24 horas del dia, los 7 dias de la semana.</p>
          </div>
          <div className="immo-service-card">
            <div className="immo-service-icon">
              <Home className="w-8 h-8" />
            </div>
            <h3>Busqueda de Propiedades</h3>
            <p>Decinos que buscas y te mostramos las mejores opciones segun tu presupuesto, zona y tipo de propiedad.</p>
          </div>
          <div className="immo-service-card">
            <div className="immo-service-icon">
              <Phone className="w-8 h-8" />
            </div>
            <h3>Agenda de Visitas</h3>
            <p>Agenda visitas a propiedades directamente desde WhatsApp, sin llamadas ni esperas.</p>
          </div>
          <div className="immo-service-card">
            <div className="immo-service-icon">
              <MapPin className="w-8 h-8" />
            </div>
            <h3>Atencion Personalizada</h3>
            <p>Si necesitas hablar con un asesor humano, te conectamos con el especialista de tu zona.</p>
          </div>
        </div>
      </section>

      {/* Como funciona */}
      <section className="immo-how" id="como-funciona">
        <h2>Como Funciona</h2>
        <p className="immo-section-sub">En 3 simples pasos</p>
        <div className="immo-steps">
          <div className="immo-step">
            <div className="immo-step-number">1</div>
            <h3>Escribi por WhatsApp</h3>
            <p>Mandanos un mensaje con lo que buscas: tipo de propiedad, zona, presupuesto.</p>
          </div>
          <div className="immo-step-arrow">
            <ArrowRight className="w-6 h-6" />
          </div>
          <div className="immo-step">
            <div className="immo-step-number">2</div>
            <h3>Recibí opciones</h3>
            <p>Nuestro asistente analiza tu consulta y te muestra propiedades que se ajustan.</p>
          </div>
          <div className="immo-step-arrow">
            <ArrowRight className="w-6 h-6" />
          </div>
          <div className="immo-step">
            <div className="immo-step-number">3</div>
            <h3>Agenda tu visita</h3>
            <p>Elegí la propiedad que te interesa y coordiná una visita directamente por chat.</p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="immo-cta" id="contacto">
        <div className="immo-cta-content">
          <h2>Empeza tu busqueda hoy</h2>
          <p>Escribinos por WhatsApp y encontra tu propiedad ideal en minutos.</p>
          <div className="immo-cta-buttons">
            {WHATSAPP_NUMBER && (
              <Button size="lg" asChild data-testid="btn-whatsapp-cta">
                <a href={whatsappLink} target="_blank" rel="noopener noreferrer">
                  <MessageSquare className="w-5 h-5 mr-2" />
                  Contactar por WhatsApp
                </a>
              </Button>
            )}
          </div>
          <div className="immo-trust">
            <div className="immo-trust-item">
              <Shield className="w-4 h-4" />
              <span>Atencion segura</span>
            </div>
            <div className="immo-trust-item">
              <CheckCircle className="w-4 h-4" />
              <span>Respuesta inmediata</span>
            </div>
            <div className="immo-trust-item">
              <Star className="w-4 h-4" />
              <span>IA de ultima generacion</span>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="immo-footer">
        <div className="immo-footer-inner">
          <div className="immo-footer-brand">
            <Home className="w-5 h-5" />
            <span>{BUSINESS_NAME}</span>
          </div>
          <div className="immo-footer-links">
            <a href="#servicios">Servicios</a>
            <a href="#como-funciona">Como funciona</a>
            <a href="#contacto">Contacto</a>
            <button onClick={() => navigate('/login')} className="immo-footer-login">
              Panel de control
            </button>
          </div>
          <p className="immo-footer-copy">&copy; {new Date().getFullYear()} {BUSINESS_NAME}. Todos los derechos reservados.</p>
        </div>
      </footer>
    </div>
  );
}
