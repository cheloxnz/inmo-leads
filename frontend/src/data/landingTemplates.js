/**
 * Plantillas de copy por rubro (template_id) para la Landing Dinamica.
 * El bot se llama InmoBot pero atiende cualquier rubro: el copy se adapta.
 */

const TEMPLATES = {
  inmobiliaria: {
    label: 'Inmobiliaria',
    hero_title: (biz) => `${biz}, encontrá tu propiedad ideal`,
    hero_subtitle: 'Atención inmediata por WhatsApp con IA. Buscá propiedades, agendá visitas y resolvé tus dudas 24/7.',
    cta_text: 'Hola, me interesa consultar por propiedades',
    section_features_title: 'Cómo te ayudamos',
    section_features_sub: 'Tecnología de punta para la mejor experiencia inmobiliaria',
    features: [
      { icon: 'home', title: 'Búsqueda de Propiedades', desc: 'Decinos qué buscás y te mostramos las mejores opciones según presupuesto, zona y tipo.' },
      { icon: 'calendar', title: 'Agendá Visitas', desc: 'Coordiná visitas a propiedades directamente desde WhatsApp, sin llamadas.' },
      { icon: 'message', title: 'Atención 24/7', desc: 'Respuestas inmediatas en cualquier momento. Atención humana cuando lo necesites.' },
    ],
    steps: [
      { title: 'Contanos qué buscás', desc: 'Mandanos un mensaje con lo que necesitás: tipo de propiedad, zona, presupuesto.' },
      { title: 'Recibí opciones personalizadas', desc: 'Nuestro asistente analiza tu consulta y te muestra propiedades que se ajustan.' },
      { title: 'Visitá y decidí', desc: 'Elegí la propiedad y coordiná una visita directamente por chat.' },
    ],
    catalog_title: 'Propiedades disponibles',
  },
  clinica: {
    label: 'Clínica / Salud',
    hero_title: (biz) => `${biz}, agendá tu turno fácil y rápido`,
    hero_subtitle: 'Atención inmediata por WhatsApp. Agendá consultas, consultá tratamientos y resolvé dudas 24/7 con IA.',
    cta_text: 'Hola, me gustaría agendar un turno',
    section_features_title: 'Cómo te atendemos',
    section_features_sub: 'Tecnología que cuida tu salud y tu tiempo',
    features: [
      { icon: 'calendar', title: 'Turnos por WhatsApp', desc: 'Reservá tu turno en segundos. Recibí recordatorios automáticos.' },
      { icon: 'shield', title: 'Información de Tratamientos', desc: 'Consultá precios, prestaciones, especialidades y obra social.' },
      { icon: 'message', title: 'Atención 24/7', desc: 'Tu profesional disponible cuando lo necesités, sin esperas en línea.' },
    ],
    steps: [
      { title: 'Contanos tu consulta', desc: 'Decinos qué especialidad necesitás y tu obra social.' },
      { title: 'Elegí horario', desc: 'Te mostramos los turnos disponibles y elegís el que mejor te queda.' },
      { title: 'Recibí tu confirmación', desc: 'Te enviamos confirmación y recordatorios por WhatsApp.' },
    ],
    catalog_title: 'Servicios disponibles',
  },
  restaurante: {
    label: 'Restaurante / Gastronomía',
    hero_title: (biz) => `${biz}, reservá tu mesa o pedí tu menú`,
    hero_subtitle: 'Reservas, pedidos y consultas por WhatsApp con IA. Te atendemos al instante 24/7.',
    cta_text: 'Hola, me gustaría reservar una mesa',
    section_features_title: 'Cómo te atendemos',
    section_features_sub: 'Una experiencia gastronómica sin esperas',
    features: [
      { icon: 'calendar', title: 'Reservas Inmediatas', desc: 'Reservá tu mesa en segundos sin llamar.' },
      { icon: 'home', title: 'Menú Digital', desc: 'Consultá nuestro menú, precios y opciones del día.' },
      { icon: 'message', title: 'Pedidos por WhatsApp', desc: 'Hacé tu pedido para llevar o delivery directamente por chat.' },
    ],
    steps: [
      { title: 'Decinos qué necesitás', desc: 'Reserva, pedido para llevar o consulta del menú.' },
      { title: 'Elegí y confirmá', desc: 'Te mostramos opciones y horarios disponibles.' },
      { title: 'Disfrutá', desc: 'Recibí confirmación al instante y te esperamos.' },
    ],
    catalog_title: 'Nuestro menú',
  },
  ecommerce: {
    label: 'E-commerce / Retail',
    hero_title: (biz) => `${biz}, comprá fácil por WhatsApp`,
    hero_subtitle: 'Atención de ventas instantánea con IA. Productos, precios, stock y compras directo por chat 24/7.',
    cta_text: 'Hola, me interesa consultar por productos',
    section_features_title: 'Cómo te atendemos',
    section_features_sub: 'La forma más rápida de comprar lo que necesitás',
    features: [
      { icon: 'home', title: 'Productos en Tiempo Real', desc: 'Consultá disponibilidad, precios y promociones.' },
      { icon: 'shield', title: 'Asesoría Personalizada', desc: 'Te ayudamos a elegir el producto ideal para vos.' },
      { icon: 'message', title: 'Compra por WhatsApp', desc: 'Cerrá tu compra y coordiná entrega directo por chat.' },
    ],
    steps: [
      { title: 'Buscá el producto', desc: 'Decinos qué necesitás o explorá nuestro catálogo.' },
      { title: 'Recibí recomendaciones', desc: 'Nuestra IA te muestra opciones que se ajustan a vos.' },
      { title: 'Comprá y recibí', desc: 'Coordiná pago y entrega sin moverte.' },
    ],
    catalog_title: 'Productos destacados',
  },
  servicios: {
    label: 'Servicios profesionales',
    hero_title: (biz) => `${biz}, atención inmediata por WhatsApp`,
    hero_subtitle: 'Consultas, presupuestos y agenda online con IA. Te respondemos al instante 24/7.',
    cta_text: 'Hola, me gustaría hacer una consulta',
    section_features_title: 'Cómo te atendemos',
    section_features_sub: 'Una experiencia simple, rápida y personalizada',
    features: [
      { icon: 'message', title: 'Consultas en Tiempo Real', desc: 'Resolvé tus dudas al instante sin esperar llamadas.' },
      { icon: 'calendar', title: 'Agenda Online', desc: 'Coordiná reuniones o visitas directamente por WhatsApp.' },
      { icon: 'shield', title: 'Presupuestos Personalizados', desc: 'Recibí cotizaciones a medida según lo que necesités.' },
    ],
    steps: [
      { title: 'Contanos qué necesitás', desc: 'Mandanos tu consulta y te respondemos al instante.' },
      { title: 'Recibí información clara', desc: 'Te asesoramos y te damos toda la info que necesités.' },
      { title: 'Coordiná lo que sigue', desc: 'Agenda una reunión o avancemos directamente por chat.' },
    ],
    catalog_title: 'Nuestros servicios',
  },
};

export function getLandingTemplate(templateId, businessName) {
  const t = TEMPLATES[templateId] || TEMPLATES.servicios;
  return {
    ...t,
    hero_title_text: typeof t.hero_title === 'function' ? t.hero_title(businessName || 'Tu negocio') : t.hero_title,
  };
}

export const ALL_TEMPLATES = TEMPLATES;
