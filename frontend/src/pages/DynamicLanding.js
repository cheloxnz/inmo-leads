import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import {
  MessageSquare, Bot, Clock, CheckCircle, ArrowRight,
  Home, Phone, MapPin, Shield, Star, Users, Sparkles,
  Calendar
} from 'lucide-react';
import { getLandingTemplate } from '../data/landingTemplates';

const BACKEND = process.env.REACT_APP_BACKEND_URL;

// Iconos disponibles para los features (mapeados desde landingTemplates)
const FEATURE_ICONS = {
  home: Home,
  calendar: Calendar,
  message: MessageSquare,
  shield: Shield,
  bot: Bot,
};

export default function DynamicLanding() {
  const { tenantId } = useParams();
  const navigate = useNavigate();
  const [tenantData, setTenantData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTenant = useCallback(async () => {
    if (!tenantId) {
      // Generic SaaS landing
      setTenantData({
        tenant: {
          business_name: process.env.REACT_APP_BUSINESS_NAME || 'InmoBot',
          business_tagline: process.env.REACT_APP_BUSINESS_TAGLINE || 'El bot inteligente para tu negocio',
          whatsapp_phone: process.env.REACT_APP_WHATSAPP_NUMBER || '',
          template_id: 'servicios',
        },
        products: [],
      });
      setLoading(false);
      return;
    }
    try {
      const res = await axios.get(`${BACKEND}/api/public/catalog/${tenantId}`);
      setTenantData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'No pudimos cargar este negocio');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchTenant(); }, [fetchTenant]);

  useEffect(() => {
    if (tenantData?.tenant?.business_name) {
      document.title = `${tenantData.tenant.business_name} — InmoBot`;
    }
  }, [tenantData]);

  if (loading) return <div className="immo-landing-loading">Cargando...</div>;
  if (error) return <div className="immo-landing-error">{error}</div>;
  if (!tenantData) return null;

  const t = tenantData.tenant;
  const businessName = t.business_name || t.name || 'Tu negocio';
  const tpl = getLandingTemplate(t.template_id, businessName);
  const phone = (t.whatsapp_phone || '').replace(/[^0-9]/g, '');
  const whatsappLink = phone
    ? `https://wa.me/${phone}?text=${encodeURIComponent(tpl.cta_text)}`
    : '#';

  // Custom branding overrides
  const features = (t.custom_features && t.custom_features.length > 0) ? t.custom_features : tpl.features;
  const steps = (t.custom_steps && t.custom_steps.length > 0) ? t.custom_steps : tpl.steps;
  const customStyle = {
    '--immo-primary': t.primary_color || '#3b82f6',
    '--immo-accent': t.accent_color || '#8b5cf6',
  };

  return (
    <div className="immo-landing" style={customStyle} data-testid="dynamic-landing" data-template={t.template_id}>
      {/* Navbar */}
      <nav className="immo-nav">
        <div className="immo-nav-inner">
          <div className="immo-nav-brand">
            {t.logo_url ? <img src={t.logo_url} alt={businessName} className="immo-nav-logo" /> : <Bot className="w-6 h-6" />}
            <span>{businessName}</span>
          </div>
          <div className="immo-nav-links">
            <a href="#servicios">Servicios</a>
            <a href="#como-funciona">Cómo funciona</a>
            <a href="#contacto">Contacto</a>
            {!tenantId && (
              <Button size="sm" variant="outline" onClick={() => navigate('/login')} data-testid="btn-login-nav">
                Acceder
              </Button>
            )}
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
          <h1 data-testid="hero-title">{tpl.hero_title_text}</h1>
          {t.business_tagline && <p className="immo-hero-tagline">{t.business_tagline}</p>}
          <p className="immo-hero-sub">{tpl.hero_subtitle}</p>
          <div className="immo-hero-buttons">
            {phone && (
              <Button size="lg" asChild data-testid="btn-whatsapp-hero">
                <a href={whatsappLink} target="_blank" rel="noopener noreferrer">
                  <MessageSquare className="w-5 h-5 mr-2" />
                  Escribinos por WhatsApp
                </a>
              </Button>
            )}
            {tenantId && tenantData.products?.length > 0 && (
              <Button size="lg" variant="outline" onClick={() => navigate(`/p/catalogo/${tenantId}`)} data-testid="btn-ver-catalogo">
                Ver {tpl.catalog_title}
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            )}
            {!tenantId && (
              <Button size="lg" variant="outline" onClick={() => {
                document.getElementById('servicios')?.scrollIntoView({ behavior: 'smooth' });
              }} data-testid="btn-ver-servicios">
                Ver Servicios <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="immo-stats">
        <div className="immo-stats-grid">
          <div className="immo-stat"><Clock className="w-8 h-8" /><span className="immo-stat-number">24/7</span><span className="immo-stat-label">Atención inmediata</span></div>
          <div className="immo-stat"><MessageSquare className="w-8 h-8" /><span className="immo-stat-number">&lt; 1 min</span><span className="immo-stat-label">Tiempo de respuesta</span></div>
          <div className="immo-stat"><Users className="w-8 h-8" /><span className="immo-stat-number">100%</span><span className="immo-stat-label">Consultas atendidas</span></div>
          <div className="immo-stat"><Star className="w-8 h-8" /><span className="immo-stat-number">IA</span><span className="immo-stat-label">Asistente inteligente</span></div>
        </div>
      </section>

      {/* Servicios / Features */}
      <section className="immo-services" id="servicios">
        <h2>{tpl.section_features_title}</h2>
        <p className="immo-section-sub">{tpl.section_features_sub}</p>
        <div className="immo-services-grid">
          {features.map((f, i) => {
            const Icon = FEATURE_ICONS[f.icon] || Bot;
            return (
              <div key={i} className="immo-service-card" data-testid={`feature-${i}`}>
                <div className="immo-service-icon"><Icon className="w-8 h-8" /></div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            );
          })}
          <div className="immo-service-card">
            <div className="immo-service-icon"><MapPin className="w-8 h-8" /></div>
            <h3>Atención Personalizada</h3>
            <p>Si necesitás hablar con un asesor humano, te conectamos con el especialista correspondiente.</p>
          </div>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="immo-how" id="como-funciona">
        <h2>Cómo Funciona</h2>
        <p className="immo-section-sub">En 3 simples pasos</p>
        <div className="immo-steps">
          {steps.map((s, i) => (
            <React.Fragment key={i}>
              <div className="immo-step">
                <div className="immo-step-number">{i + 1}</div>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </div>
              {i < steps.length - 1 && (
                <div className="immo-step-arrow"><ArrowRight className="w-6 h-6" /></div>
              )}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="immo-cta" id="contacto">
        <div className="immo-cta-content">
          <h2>{tenantId ? 'Empezá ahora' : 'Empezá hoy con InmoBot'}</h2>
          <p>{phone ? 'Escribinos por WhatsApp y te respondemos al instante.' : 'Configurá tu bot y empezá a vender por WhatsApp con IA.'}</p>
          <div className="immo-cta-buttons">
            {phone ? (
              <Button size="lg" asChild data-testid="btn-whatsapp-cta">
                <a href={whatsappLink} target="_blank" rel="noopener noreferrer">
                  <MessageSquare className="w-5 h-5 mr-2" />
                  Contactar por WhatsApp
                </a>
              </Button>
            ) : (
              <Button size="lg" onClick={() => navigate('/login')} data-testid="btn-cta-login">
                Acceder al panel
              </Button>
            )}
          </div>
          <div className="immo-trust">
            <div className="immo-trust-item"><Shield className="w-4 h-4" /><span>Atención segura</span></div>
            <div className="immo-trust-item"><CheckCircle className="w-4 h-4" /><span>Respuesta inmediata</span></div>
            <div className="immo-trust-item"><Star className="w-4 h-4" /><span>IA de última generación</span></div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="immo-footer">
        <div className="immo-footer-inner">
          <div className="immo-footer-brand">
            <Bot className="w-5 h-5" />
            <span>{businessName}</span>
          </div>
          <div className="immo-footer-links">
            <a href="#servicios">Servicios</a>
            <a href="#como-funciona">Cómo funciona</a>
            <a href="#contacto">Contacto</a>
          </div>
          <p className="immo-footer-copy">
            &copy; {new Date().getFullYear()} {businessName}. Powered by <strong>InmoBot</strong>.
          </p>
        </div>
      </footer>
    </div>
  );
}
