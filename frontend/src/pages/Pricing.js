import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Check } from 'lucide-react';
import { toast } from 'sonner';

export default function Pricing() {
  const [plans, setPlans] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [customerData, setCustomerData] = useState({ name: '', email: '' });
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/plans`);
      setPlans(response.data);
    } catch (error) {
      console.error('Error fetching plans:', error);
      toast.error('Error cargando planes');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPlan = (planId) => {
    setSelectedPlan(planId);
    setShowModal(true);
  };

  const handleCheckout = async () => {
    if (!customerData.name || !customerData.email) {
      toast.error('Por favor completá todos los campos');
      return;
    }

    setProcessing(true);

    try {
      const response = await axios.post(`${API}/checkout`, {
        plan_id: selectedPlan,
        customer_email: customerData.email,
        customer_name: customerData.name,
        origin_url: window.location.origin
      });

      // Redirigir a Stripe Checkout
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Error creating checkout:', error);
      toast.error('Error al procesar el pago');
      setProcessing(false);
    }
  };

  if (loading) {
    return <div className="loading-container">Cargando planes...</div>;
  }

  return (
    <div className="pricing-page" data-testid="pricing-page">
      {/* Hero Section */}
      <section className="pricing-hero">
        <img 
          src="https://customer-assets.emergentagent.com/job_lead-manager-es/artifacts/l1ys0o2g_ChatGPT%20Image%203%20feb%202026%2C%2009_57_44%20p.m..png" 
          alt="InmoBot Logo" 
          className="hero-logo"
        />
        <h1>Automatizá tu Inmobiliaria con IA</h1>
        <p>Bot de WhatsApp + CRM completo para captar y gestionar leads 24/7</p>
      </section>

      {/* Plans Section */}
      <section className="pricing-plans">
        <div className="plans-grid">
          {Object.entries(plans).map(([planId, plan]) => (
            <Card 
              key={planId} 
              className={`plan-card ${planId === 'pro' ? 'featured' : ''}`}
              data-testid={`plan-${planId}`}
            >
              {planId === 'pro' && (
                <Badge className="plan-badge">Más Popular</Badge>
              )}
              <CardHeader>
                <CardTitle className="plan-name">{plan.name}</CardTitle>
                <p className="plan-description">{plan.description}</p>
                <div className="plan-price">
                  <span className="price-amount">${plan.price}</span>
                  <span className="price-period">/mes</span>
                </div>
                {plan.setup_price && (
                  <div className="plan-setup">
                    <span className="setup-label">Setup único:</span>
                    <span className="setup-price">${plan.setup_price}</span>
                  </div>
                )}
              </CardHeader>
              <CardContent>
                <ul className="plan-features">
                  {plan.features.map((feature, idx) => (
                    <li key={idx}>
                      <Check className="feature-check" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <Button 
                  className={`plan-button ${planId === 'pro' ? 'primary' : 'outline'}`}
                  onClick={() => handleSelectPlan(planId)}
                  data-testid={`btn-select-${planId}`}
                >
                  {planId === 'agency' ? 'Contactar Ventas' : 'Comenzar Ahora'}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section className="pricing-features">
        <h2>Todo lo que necesitás para vender más</h2>
        <div className="features-grid">
          <div className="feature-item">
            <span className="feature-icon">🤖</span>
            <h3>Bot de WhatsApp con IA</h3>
            <p>Responde automáticamente, califica leads y agenda citas 24/7</p>
          </div>
          <div className="feature-item">
            <span className="feature-icon">📊</span>
            <h3>Dashboard Completo</h3>
            <p>Métricas en tiempo real, gestión de leads y calendario integrado</p>
          </div>
          <div className="feature-item">
            <span className="feature-icon">🔔</span>
            <h3>Notificaciones Inteligentes</h3>
            <p>Alertas de leads urgentes y recordatorios de citas</p>
          </div>
          <div className="feature-item">
            <span className="feature-icon">👥</span>
            <h3>Gestión de Equipo</h3>
            <p>Asignación automática de leads entre tus asesores</p>
          </div>
          <div className="feature-item">
            <span className="feature-icon">🎤</span>
            <h3>Transcripción de Audios</h3>
            <p>El bot entiende mensajes de voz y los procesa automáticamente</p>
          </div>
          <div className="feature-item">
            <span className="feature-icon">📅</span>
            <h3>Agenda Inteligente</h3>
            <p>Clientes agendan citas por WhatsApp sin intervención humana</p>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="pricing-testimonials">
        <h2>Lo que dicen nuestros clientes</h2>
        <div className="testimonials-grid">
          <div className="testimonial-card">
            <div className="testimonial-content">
              <p>"Desde que implementamos InmoBot, captamos un 40% más de leads. El bot responde al instante y mis asesores ya reciben los contactos calificados."</p>
            </div>
            <div className="testimonial-author">
              <div className="author-avatar">MR</div>
              <div className="author-info">
                <strong>Martín Rodríguez</strong>
                <span>Director - Inmobiliaria Rodríguez</span>
              </div>
            </div>
            <div className="testimonial-stars">⭐⭐⭐⭐⭐</div>
          </div>
          <div className="testimonial-card">
            <div className="testimonial-content">
              <p>"Antes perdíamos muchas consultas fuera de horario. Ahora el bot agenda citas automáticamente y nos avisa cuando hay un cliente urgente. Excelente inversión."</p>
            </div>
            <div className="testimonial-author">
              <div className="author-avatar">CG</div>
              <div className="author-info">
                <strong>Carolina González</strong>
                <span>Broker - CG Propiedades</span>
              </div>
            </div>
            <div className="testimonial-stars">⭐⭐⭐⭐⭐</div>
          </div>
          <div className="testimonial-card">
            <div className="testimonial-content">
              <p>"El dashboard me permite ver todo en un solo lugar. Las métricas me ayudaron a identificar que estaba perdiendo clientes en la etapa de agendamiento. Ahora mi conversión subió un 25%."</p>
            </div>
            <div className="testimonial-author">
              <div className="author-avatar">LP</div>
              <div className="author-info">
                <strong>Luis Peralta</strong>
                <span>Gerente - Grupo Inmobiliario LP</span>
              </div>
            </div>
            <div className="testimonial-stars">⭐⭐⭐⭐⭐</div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="pricing-faq">
        <h2>Preguntas Frecuentes</h2>
        <div className="faq-grid">
          <div className="faq-item">
            <h4>¿Cómo funciona el bot de WhatsApp?</h4>
            <p>Conectamos tu número de WhatsApp Business con nuestro sistema. El bot responde automáticamente a tus clientes, los califica según sus necesidades y agenda citas directamente en tu calendario.</p>
          </div>
          <div className="faq-item">
            <h4>¿Necesito conocimientos técnicos?</h4>
            <p>No, nosotros nos encargamos de toda la configuración. En menos de 24 horas tenés tu bot funcionando.</p>
          </div>
          <div className="faq-item">
            <h4>¿Puedo cancelar cuando quiera?</h4>
            <p>Sí, podés cancelar tu suscripción en cualquier momento. No hay contratos de permanencia.</p>
          </div>
          <div className="faq-item">
            <h4>¿Qué pasa con mis datos si cancelo?</h4>
            <p>Tus datos te pertenecen. Podés exportarlos en cualquier momento y te damos 30 días para descargarlos después de cancelar.</p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="pricing-cta">
        <h2>¿Listo para automatizar tu inmobiliaria?</h2>
        <p>Empezá hoy y captá más leads mientras dormís</p>
        <Button 
          size="lg" 
          onClick={() => handleSelectPlan('pro')}
          data-testid="btn-cta"
        >
          Comenzar Prueba Gratis
        </Button>
      </section>

      {/* Checkout Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Completá tus datos</DialogTitle>
            <DialogDescription>
              {selectedPlan && plans[selectedPlan] && (
                <div className="checkout-plan-info">
                  <div>Plan: <strong>{plans[selectedPlan].name}</strong></div>
                  <div className="checkout-prices">
                    <span>Setup único: <strong>${plans[selectedPlan].setup_price}</strong></span>
                    <span>Luego: <strong>${plans[selectedPlan].price}/mes</strong></span>
                  </div>
                </div>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="checkout-form">
            <div className="form-group">
              <label>Nombre completo</label>
              <Input
                type="text"
                placeholder="Tu nombre"
                value={customerData.name}
                onChange={(e) => setCustomerData({...customerData, name: e.target.value})}
                data-testid="input-name"
              />
            </div>
            <div className="form-group">
              <label>Email</label>
              <Input
                type="email"
                placeholder="tu@email.com"
                value={customerData.email}
                onChange={(e) => setCustomerData({...customerData, email: e.target.value})}
                data-testid="input-email"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowModal(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={handleCheckout} 
              disabled={processing}
              data-testid="btn-checkout"
            >
              {processing ? 'Procesando...' : 'Ir a Pagar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
