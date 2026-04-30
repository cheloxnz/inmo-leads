import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, Sparkles, Shield, Bot, Mail, Megaphone, Wand2, Layers, Rocket } from 'lucide-react';

const releases = [
  {
    period: 'Abril 2026',
    items: [
      {
        icon: <Shield size={18} />,
        title: 'Observabilidad y producción',
        bullets: [
          'Logs estructurados (JSON) con request_id único por request — pasanos el ID y rastreamos exactamente qué pasó.',
          'Health check ultra-liviano /api/health/ping para monitoreo externo (UptimeRobot, Pingdom).',
          'MongoDB Atlas con backups automáticos diarios. Tu data ahora es a prueba de balas.',
          'Sentry configurado para detectar errores de backend y frontend en <1 minuto.',
          'Hardening: rate limiting por endpoint, HSTS, CSP, X-Frame-Options, payload limit 5MB.',
        ],
      },
      {
        icon: <Sparkles size={18} />,
        title: 'AI Lead Summary (premium)',
        bullets: [
          'Resumen automático de cada conversación con GPT-4: narrativa, urgencia 1-10, próximo paso, insights y señales de compra.',
          'Cache inteligente con TTL 7 días que invalida si la conversación creció.',
          'Activable desde el panel SuperAdmin por cliente (feature flag).',
        ],
      },
      {
        icon: <Megaphone size={18} />,
        title: 'Programa de Referidos con Cupones de Stripe',
        bullets: [
          'Código único por cliente (ej. INMOBOT-XXXXXX). Tu referido ingresa el cupón en Stripe Checkout y recibe 5% off el primer mes.',
          'Vos ganás $5/mes durante 12 meses por cada referido activo (cap: 100% del valor de tu plan).',
          'UTM tracking persistente con localStorage 30 días.',
        ],
      },
      {
        icon: <Mail size={18} />,
        title: 'Emails automáticos',
        bullets: [
          'Bienvenida al crear nuevo workspace.',
          'Aviso de fin de trial 1, 2 y 3 días antes (con dedupe).',
          'Resumen semanal con leads, conversiones y ahorro por referidos.',
          'Notificación de nueva comisión cuando un referido paga su primera factura.',
        ],
      },
      {
        icon: <Layers size={18} />,
        title: 'Feature Flags multi-tenant',
        bullets: [
          'Sistema de flags por cliente controlable desde panel SuperAdmin.',
          '8 flags iniciales: AI Lead Summary, voice TTS, Salesforce sync, white label y más.',
        ],
      },
    ],
  },
  {
    period: 'Marzo 2026',
    items: [
      {
        icon: <Megaphone size={18} />,
        title: 'Marketing orgánico y viralidad',
        bullets: [
          'Open Graph image generator: cuando compartís una "celebración", generamos automáticamente una imagen 1200×630 branded.',
          'Captura de leads en share pages públicos con atribución completa.',
          'Marketing Effectiveness Dashboard (/marketing) con funnel completo.',
        ],
      },
      {
        icon: <Wand2 size={18} />,
        title: 'AI Configuration Assistant',
        bullets: [
          'Editá la configuración de tu bot en lenguaje natural ("cambiá el horario a 9-19hs y los sábados de 10 a 13").',
          'Flujo de 2 pasos (preview → apply) para que veas exactamente qué va a cambiar.',
        ],
      },
      {
        icon: <Bot size={18} />,
        title: 'AI Flow Editor',
        bullets: [
          'Editor visual de flujos con asistente IA. Pedile cambios en lenguaje natural y la IA edita el árbol.',
        ],
      },
    ],
  },
  {
    period: 'Febrero 2026',
    items: [
      {
        icon: <Rocket size={18} />,
        title: 'Auto-Onboarding Wizard',
        bullets: [
          'Setup en menos de 5 minutos: ingresás nombre, descripción y email. La IA detecta el rubro, genera tagline + features + steps, crea 3 productos demo y te loguea.',
        ],
      },
      {
        icon: <Wand2 size={18} />,
        title: 'Editor visual de landing',
        bullets: [
          'Personalizá colores (con hints WCAG de contraste), logo, copy y custom features con preview en tiempo real.',
          'Subida de logos hasta 2MB.',
          'Generador de copy con IA: pegás una descripción y obtenés tagline + 3 features + 3 steps.',
        ],
      },
      {
        icon: <Layers size={18} />,
        title: 'Catálogo embebible',
        bullets: [
          'Widget público de catálogo embebible con un <script> drop-in.',
          'Recomendaciones IA contextuales para cada visitante.',
          'Tracking de conversiones widget→WhatsApp.',
        ],
      },
    ],
  },
  {
    period: 'Enero 2026',
    items: [
      {
        icon: <Rocket size={18} />,
        title: 'Multi-tenant SaaS (lanzamiento)',
        bullets: [
          'Arquitectura multi-tenant con aislamiento estricto por tenant_id.',
          '3 planes: Basic ($49/mes), Pro ($99/mes), Enterprise ($249/mes).',
          'Stripe Subscriptions con webhooks completos.',
          '5 templates de bot por rubro (inmobiliaria, clínica, restaurante, ecommerce, servicios).',
        ],
      },
    ],
  },
];

export default function Changelog() {
  return (
    <div className="changelog-page" data-testid="changelog-page">
      <div className="changelog-container">
        <Link to="/inicio" className="changelog-back" data-testid="changelog-back">
          <ChevronLeft size={16} /> Volver
        </Link>

        <header className="changelog-header">
          <div className="changelog-badge">Changelog público</div>
          <h1 className="changelog-title">Qué hay de nuevo en InmoBot</h1>
          <p className="changelog-subtitle">
            Mejoras, funciones y arreglos que liberamos cada semana. Si querés que te
            avisemos por email cuando salga algo grande,{' '}
            <a href="mailto:soporte@inmobot.com">escribinos</a>.
          </p>
        </header>

        <div className="changelog-timeline">
          {releases.map((release) => (
            <section key={release.period} className="changelog-release">
              <h2 className="changelog-period">{release.period}</h2>
              <div className="changelog-items">
                {release.items.map((item, idx) => (
                  <div
                    key={idx}
                    className="changelog-item"
                    data-testid={`changelog-item-${release.period.replace(/\s+/g, '-').toLowerCase()}-${idx}`}
                  >
                    <div className="changelog-item-icon">{item.icon}</div>
                    <div className="changelog-item-body">
                      <h3 className="changelog-item-title">{item.title}</h3>
                      <ul className="changelog-bullets">
                        {item.bullets.map((b, j) => (
                          <li key={j}>{b}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>

        <footer className="changelog-footer">
          <p>
            ¿Te gustaría una función nueva?{' '}
            <a href="mailto:soporte@inmobot.com">Mandanos un email</a> y la sumamos al
            roadmap.
          </p>
        </footer>
      </div>
    </div>
  );
}
