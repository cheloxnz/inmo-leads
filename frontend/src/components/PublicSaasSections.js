import React, { useEffect, useRef, useState } from 'react';
import {
  Bot, MessageSquare, Calendar, ShieldCheck, Zap, Brain, Database,
  CreditCard, Clock, TrendingUp, Users, Sparkles, CheckCircle2, XCircle,
  ChevronDown, Quote, Pizza, Wrench, Home as HomeIcon, Stethoscope,
  Briefcase, ShoppingBag, ArrowRight,
} from 'lucide-react';

/* ──────────────────────────────────────────────────────────────────────────
   Hook: fade-in on scroll usando IntersectionObserver.
   Aplica clase `is-visible` cuando el elemento entra al viewport.
   ────────────────────────────────────────────────────────────────────────── */
function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('is-visible');
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
}

const Reveal = ({ children, delay = 0, className = '' }) => {
  const ref = useReveal();
  return (
    <div
      ref={ref}
      className={`reveal ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
};

/* ──────────────────────────────────────────────────────────────────────────
   1. Métricas / Hooks
   ────────────────────────────────────────────────────────────────────────── */
const METRICS = [
  { icon: Clock, value: '24/7', label: 'Atención continua' },
  { icon: Zap, value: '< 1 min', label: 'Tiempo de respuesta' },
  { icon: TrendingUp, value: '+90%', label: 'Consultas resueltas sin humano' },
  { icon: Users, value: 'Multi-rubro', label: 'Para cualquier negocio' },
];

const MetricsSection = () => (
  <section className="saas-metrics">
    <div className="saas-container">
      <Reveal>
        <h2 className="saas-h2">Resultados desde el primer día</h2>
        <p className="saas-sub">Diseñado para que vendas más sin contratar más gente.</p>
      </Reveal>
      <div className="saas-metrics-grid">
        {METRICS.map((m, i) => (
          <Reveal key={i} delay={i * 80}>
            <div className="saas-metric-card">
              <m.icon className="w-7 h-7" />
              <div className="saas-metric-value">{m.value}</div>
              <div className="saas-metric-label">{m.label}</div>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
);

/* ──────────────────────────────────────────────────────────────────────────
   2. Tecnologías / Stack
   ────────────────────────────────────────────────────────────────────────── */
const TECH = [
  { icon: Brain, name: 'OpenAI GPT', desc: 'Comprensión natural y respuestas inteligentes.' },
  { icon: MessageSquare, name: 'WhatsApp Business API', desc: 'Mensajería oficial de Meta con cifrado E2E.' },
  { icon: Calendar, name: 'Google Calendar', desc: 'Agenda automática con detección de conflictos.' },
  { icon: CreditCard, name: 'Stripe', desc: 'Pagos seguros con tarjeta o cuenta bancaria.' },
  { icon: Database, name: 'MongoDB Atlas', desc: 'Base de datos en la nube con alta disponibilidad.' },
  { icon: ShieldCheck, name: 'Cloudflare', desc: 'CDN global y protección anti-DDoS.' },
];

const TechSection = () => (
  <section className="saas-tech" id="tecnologias">
    <div className="saas-container">
      <Reveal>
        <div className="saas-eyebrow">Powered by</div>
        <h2 className="saas-h2">Tecnología de nivel empresarial</h2>
        <p className="saas-sub">
          InmoBot AI se apoya en los servicios líderes del mundo para garantizar velocidad,
          seguridad y resultados.
        </p>
      </Reveal>
      <div className="saas-tech-grid">
        {TECH.map((t, i) => (
          <Reveal key={i} delay={i * 60}>
            <div className="saas-tech-card">
              <div className="saas-tech-icon">
                <t.icon className="w-6 h-6" />
              </div>
              <h3>{t.name}</h3>
              <p>{t.desc}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
);

/* ──────────────────────────────────────────────────────────────────────────
   3. Casos de uso / Industrias
   ────────────────────────────────────────────────────────────────────────── */
const USE_CASES = [
  {
    icon: Pizza,
    title: 'Gastronomía',
    desc: 'Tomá pedidos por WhatsApp, mandá el menú en PDF y agendá reservas automáticamente.',
    bullets: ['Menú en PDF', 'Pedidos guiados', 'Reserva de mesa'],
  },
  {
    icon: HomeIcon,
    title: 'Inmobiliarias',
    desc: 'Califica leads, recopila zona/presupuesto/intención y agenda visitas en tu calendario.',
    bullets: ['Calificación de leads', 'Visitas agendadas', 'Tasaciones'],
  },
  {
    icon: Wrench,
    title: 'Ferreterías y Servicios',
    desc: 'Cotizá trabajos, mandá lista de precios y derivá al asesor cuando corresponde.',
    bullets: ['Lista de precios', 'Cotizaciones', 'Stock disponible'],
  },
  {
    icon: Stethoscope,
    title: 'Salud y Estética',
    desc: 'Turnos online, recordatorios automáticos y derivación a especialistas.',
    bullets: ['Turnos automáticos', 'Recordatorios', 'Triage inicial'],
  },
  {
    icon: Briefcase,
    title: 'Consultoras y B2B',
    desc: 'Califica leads B2B, agenda demos y entrega material comercial en segundos.',
    bullets: ['Lead scoring', 'Demos agendadas', 'Brochures por chat'],
  },
  {
    icon: ShoppingBag,
    title: 'E-commerce y Retail',
    desc: 'Catálogo interactivo, tracking de pedidos y atención post-venta 24/7.',
    bullets: ['Catálogo en chat', 'Estado del pedido', 'Postventa'],
  },
];

const UseCasesSection = () => (
  <section className="saas-cases" id="casos">
    <div className="saas-container">
      <Reveal>
        <div className="saas-eyebrow">Casos de uso</div>
        <h2 className="saas-h2">Para cualquier rubro</h2>
        <p className="saas-sub">
          Configurás el flujo una vez y InmoBot AI se adapta a tu negocio. Estos son solo
          algunos ejemplos.
        </p>
      </Reveal>
      <div className="saas-cases-grid">
        {USE_CASES.map((c, i) => (
          <Reveal key={i} delay={i * 70}>
            <div className="saas-case-card">
              <div className="saas-case-icon">
                <c.icon className="w-6 h-6" />
              </div>
              <h3>{c.title}</h3>
              <p>{c.desc}</p>
              <ul>
                {c.bullets.map((b, j) => (
                  <li key={j}>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
);

/* ──────────────────────────────────────────────────────────────────────────
   4. Demo mockup WhatsApp chat
   ────────────────────────────────────────────────────────────────────────── */
const DEMO_MESSAGES = [
  { from: 'user', text: '¡Hola! Quiero pedir una pizza' },
  { from: 'bot', text: '👋 ¡Hola! Soy el asistente virtual de Chevamaso. ¿Qué te gustaría hacer hoy?', buttons: ['🍕 Ver menú', '📦 Hacer pedido', '📅 Reservar mesa'] },
  { from: 'user', text: 'Ver menú' },
  { from: 'bot', text: '📄 Te paso nuestro menú actualizado:', attachment: 'menu.pdf' },
  { from: 'bot', text: '¿Querés que te ayude a armar un pedido? 🤖' },
];

const DemoSection = () => (
  <section className="saas-demo" id="demo">
    <div className="saas-container saas-demo-inner">
      <div className="saas-demo-text">
        <Reveal>
          <div className="saas-eyebrow">Demo en vivo</div>
          <h2 className="saas-h2">Así conversa tu negocio con tus clientes</h2>
          <p className="saas-sub">
            Cada mensaje, cada botón, cada PDF: todo configurable desde un panel
            sin escribir código. El bot se siente humano, pero trabaja 24/7.
          </p>
          <ul className="saas-demo-bullets">
            <li><Sparkles className="w-4 h-4" /> Botones con archivos adjuntos (menú, catálogo, presupuestos)</li>
            <li><Sparkles className="w-4 h-4" /> Detección automática de intención con IA</li>
            <li><Sparkles className="w-4 h-4" /> Handoff al asesor humano cuando hace falta</li>
            <li><Sparkles className="w-4 h-4" /> Aprende de cada conversación nueva</li>
          </ul>
        </Reveal>
      </div>

      <Reveal delay={150} className="saas-demo-phone-wrapper">
        <div className="saas-demo-phone">
          <div className="saas-demo-header">
            <div className="saas-demo-avatar">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="saas-demo-name">Chevamaso</div>
              <div className="saas-demo-status">en línea</div>
            </div>
          </div>
          <div className="saas-demo-body">
            {DEMO_MESSAGES.map((m, i) => (
              <div key={i} className={`saas-demo-msg saas-demo-msg--${m.from}`}>
                <div className="saas-demo-bubble">
                  <span>{m.text}</span>
                  {m.attachment && (
                    <div className="saas-demo-attach">
                      📄 {m.attachment}
                    </div>
                  )}
                  {m.buttons && (
                    <div className="saas-demo-buttons">
                      {m.buttons.map((b, j) => <span key={j}>{b}</span>)}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div className="saas-demo-typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </Reveal>
    </div>
  </section>
);

/* ──────────────────────────────────────────────────────────────────────────
   5. Comparativa Con vs Sin InmoBot
   ────────────────────────────────────────────────────────────────────────── */
const COMPARISON = {
  without: [
    'Clientes esperan horas o días una respuesta',
    'Perdés leads fuera del horario comercial',
    'Te interrumpen 50 veces al día con la misma consulta',
    'Manualmente cargás cada lead en una planilla',
    'Olvidos y citas duplicadas en la agenda',
    'Sin métricas para saber qué funciona',
  ],
  with: [
    'Respuesta automática en menos de 1 minuto, 24/7',
    'Capturás leads incluso a las 3am',
    'El bot responde lo repetitivo, vos cerrás ventas',
    'Cada conversación queda en el CRM automáticamente',
    'Agenda sincronizada con Google Calendar sin conflictos',
    'Dashboard con scoring, conversión y trends',
  ],
};

const ComparisonSection = () => (
  <section className="saas-compare">
    <div className="saas-container">
      <Reveal>
        <div className="saas-eyebrow">Comparativa</div>
        <h2 className="saas-h2">Con InmoBot AI vs. sin InmoBot AI</h2>
        <p className="saas-sub">La diferencia entre perder oportunidades y multiplicarlas.</p>
      </Reveal>
      <div className="saas-compare-grid">
        <Reveal className="saas-compare-col saas-compare-col--bad">
          <div className="saas-compare-head">
            <XCircle className="w-5 h-5" />
            <span>Sin InmoBot AI</span>
          </div>
          <ul>
            {COMPARISON.without.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </Reveal>
        <Reveal delay={150} className="saas-compare-col saas-compare-col--good">
          <div className="saas-compare-head">
            <CheckCircle2 className="w-5 h-5" />
            <span>Con InmoBot AI</span>
          </div>
          <ul>
            {COMPARISON.with.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </Reveal>
      </div>
    </div>
  </section>
);

/* ──────────────────────────────────────────────────────────────────────────
   6. Testimonios genéricos (placeholders editables)
   ────────────────────────────────────────────────────────────────────────── */
const TESTIMONIALS = [
  {
    name: 'Martín G.',
    role: 'Dueño · Inmobiliaria',
    text: 'Antes perdía consultas todos los fines de semana. Ahora cada lead queda calificado y con visita agendada antes de que llegue el lunes.',
  },
  {
    name: 'Laura P.',
    role: 'Gerenta · Pizzería de barrio',
    text: 'El bot toma pedidos mientras atendemos en el local. Vendimos un 30% más sin contratar a nadie nuevo.',
  },
  {
    name: 'Diego R.',
    role: 'Director · Consultora B2B',
    text: 'Califica leads mejor que un SDR junior. Ahorramos 20 horas semanales solo en filtrar contactos no calificados.',
  },
];

const TestimonialsSection = () => (
  <section className="saas-testimonials">
    <div className="saas-container">
      <Reveal>
        <div className="saas-eyebrow">Testimonios</div>
        <h2 className="saas-h2">Lo que dicen quienes ya lo usan</h2>
        <p className="saas-sub">Negocios reales, resultados reales.</p>
      </Reveal>
      <div className="saas-testimonials-grid">
        {TESTIMONIALS.map((t, i) => (
          <Reveal key={i} delay={i * 100}>
            <div className="saas-testimonial-card">
              <Quote className="saas-testimonial-quote" />
              <p>{t.text}</p>
              <div className="saas-testimonial-author">
                <div className="saas-testimonial-avatar">
                  {t.name.charAt(0)}
                </div>
                <div>
                  <div className="saas-testimonial-name">{t.name}</div>
                  <div className="saas-testimonial-role">{t.role}</div>
                </div>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
);

/* ──────────────────────────────────────────────────────────────────────────
   7. FAQ
   ────────────────────────────────────────────────────────────────────────── */
const FAQ_ITEMS = [
  {
    q: '¿Necesito saber programar para usarlo?',
    a: 'No. Todo se configura desde un panel visual: mensaje de bienvenida, botones, archivos adjuntos, flujos. Lo armás en minutos sin escribir código.',
  },
  {
    q: '¿Sirve para mi rubro?',
    a: 'Sí. InmoBot AI es genérico y se adapta a cualquier negocio: gastronomía, inmobiliarias, ferreterías, salud, consultoras, retail y más. Vos definís el flujo y los mensajes.',
  },
  {
    q: '¿Cómo se conecta a mi WhatsApp?',
    a: 'Usamos la API oficial de WhatsApp Business (Meta Cloud API). Conectás tu número en pocos pasos y empezás a atender. El número sigue siendo tuyo, no se comparte.',
  },
  {
    q: '¿Qué pasa cuando el bot no sabe responder?',
    a: 'Hace handoff automático: te avisa que hay un cliente que necesita ayuda humana y vos seguís la conversación desde el mismo panel. Además, el bot aprende para responder solo la próxima vez.',
  },
  {
    q: '¿Mis datos están seguros?',
    a: 'Sí. Usamos infraestructura cifrada, MongoDB Atlas, Cloudflare y los estándares de seguridad de Meta. Cada cliente tiene su entorno aislado (multi-tenant).',
  },
  {
    q: '¿Puedo agendar reuniones con Google Calendar?',
    a: 'Sí. InmoBot AI se integra con tu Google Calendar, detecta conflictos automáticamente y propone horarios alternativos cuando un slot no está disponible.',
  },
];

const FaqItem = ({ item, isOpen, onToggle }) => (
  <div className={`saas-faq-item ${isOpen ? 'is-open' : ''}`}>
    <button className="saas-faq-question" onClick={onToggle} data-testid="faq-question">
      <span>{item.q}</span>
      <ChevronDown className="saas-faq-chevron w-5 h-5" />
    </button>
    <div className="saas-faq-answer">
      <p>{item.a}</p>
    </div>
  </div>
);

const FaqSection = () => {
  const [openIdx, setOpenIdx] = useState(0);
  return (
    <section className="saas-faq" id="faq">
      <div className="saas-container saas-faq-container">
        <Reveal>
          <div className="saas-eyebrow">Preguntas frecuentes</div>
          <h2 className="saas-h2">Resolvemos tus dudas</h2>
        </Reveal>
        <div className="saas-faq-list">
          {FAQ_ITEMS.map((item, i) => (
            <Reveal key={i} delay={i * 60}>
              <FaqItem
                item={item}
                isOpen={openIdx === i}
                onToggle={() => setOpenIdx(openIdx === i ? -1 : i)}
              />
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
};

/* ──────────────────────────────────────────────────────────────────────────
   8. Floating WhatsApp CTA
   ────────────────────────────────────────────────────────────────────────── */
const FloatingWhatsappCTA = ({ phone }) => {
  if (!phone) return null;
  return (
    <a
      href={`https://wa.me/${phone.replace(/[^0-9]/g, '')}?text=Hola%2C%20quiero%20probar%20InmoBot%20AI`}
      target="_blank"
      rel="noopener noreferrer"
      className="saas-floating-cta"
      data-testid="floating-cta"
      aria-label="Hablar por WhatsApp"
    >
      <MessageSquare className="w-6 h-6" />
      <span>Probalo en WhatsApp</span>
      <ArrowRight className="w-4 h-4" />
    </a>
  );
};

/* ──────────────────────────────────────────────────────────────────────────
   Componente principal
   ────────────────────────────────────────────────────────────────────────── */
export default function PublicSaasSections({ phone }) {
  return (
    <>
      <MetricsSection />
      <TechSection />
      <UseCasesSection />
      <DemoSection />
      <ComparisonSection />
      <TestimonialsSection />
      <FaqSection />
      <FloatingWhatsappCTA phone={phone} />
    </>
  );
}
