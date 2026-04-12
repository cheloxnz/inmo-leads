import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { 
  CheckCircle, ArrowLeft, CreditCard, Shield, 
  Download, FileText, Video, Code, MessageSquare,
  Wrench, RefreshCw, Headphones, ArrowRight
} from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const PLANS = {
  codigo: {
    id: 'codigo',
    name: 'Código Solo',
    price: 147,
    description: 'Código fuente completo + documentación. Lo instalás vos.',
    features: [
      'Código fuente completo (React + Python)',
      'Bot de WhatsApp con IA (GPT-4)',
      'Dashboard de gestión completo',
      'Landing page personalizable',
      'Docker + Railway listos para deploy',
      'Documentación paso a paso (800+ líneas)',
      'Licencia comercial incluida',
      '7 días de garantía'
    ]
  },
  instalacion: {
    id: 'instalacion',
    name: 'Código + Instalación',
    price: 497,
    popular: true,
    description: 'Todo del plan anterior + nosotros te lo dejamos funcionando.',
    features: [
      'Todo del plan Código Solo',
      'Instalación completa por nosotros',
      'Deploy en Railway o tu servidor',
      'Configuración de WhatsApp Business API',
      'Dominio personalizado + SSL',
      'Bot funcionando y testeado',
      'Videollamada de entrega (30 min)',
      '7 días de garantía'
    ]
  },
  soporte: {
    id: 'soporte',
    name: 'Soporte + Actualizaciones',
    price: 100,
    monthly: true,
    description: 'Mantenimiento continuo, nuevas funciones y soporte técnico.',
    features: [
      'Actualizaciones automáticas del código',
      'Nuevas funcionalidades incluidas',
      'Soporte técnico por WhatsApp',
      'Corrección de bugs prioritaria',
      'Mejoras de IA incluidas',
      'Backups asistidos'
    ]
  }
};

const SOPORTE_OPTIONS = [
  { period: 'Mensual', months: 1, price: 100, discount: 0, total: 100 },
  { period: '6 meses', months: 6, price: 85, discount: 15, total: 510 },
  { period: '12 meses', months: 12, price: 80, discount: 20, total: 960 },
  { period: '24 meses', months: 24, price: 70, discount: 30, total: 1680 },
];

export default function ComprarPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [selectedPlan, setSelectedPlan] = useState('instalacion');
  const [selectedSoporte, setSelectedSoporte] = useState(1);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({ name: '', email: '' });

  useEffect(() => {
    const plan = searchParams.get('plan');
    if (plan && PLANS[plan]) {
      setSelectedPlan(plan);
    }
  }, [searchParams]);

  const currentPlan = PLANS[selectedPlan];

  const getTotal = () => {
    if (selectedPlan === 'soporte') {
      return SOPORTE_OPTIONS[selectedSoporte].total;
    }
    return currentPlan.price;
  };

  const getPriceLabel = () => {
    if (selectedPlan === 'soporte') {
      const opt = SOPORTE_OPTIONS[selectedSoporte];
      return opt.months === 1 ? `$${opt.total} USD/mes` : `$${opt.total} USD (${opt.period})`;
    }
    return `$${currentPlan.price} USD`;
  };

  const handlePurchase = async () => {
    if (!formData.name || !formData.email) {
      alert('Por favor completá tu nombre y email');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/api/create-checkout-session`, {
        plan_id: selectedPlan,
        customer_email: formData.email,
        customer_name: formData.name,
        soporte_period: selectedPlan === 'soporte' ? SOPORTE_OPTIONS[selectedSoporte].months : null
      });

      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Error al procesar. Por favor intentá de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="comprar-page">
      <div className="comprar-container">
        <button className="back-button" onClick={() => navigate('/inicio')} data-testid="back-button">
          <ArrowLeft className="w-4 h-4" />
          Volver
        </button>

        {/* Plan Selector Tabs */}
        <div className="plan-tabs" data-testid="plan-tabs">
          {Object.values(PLANS).map((plan) => (
            <button
              key={plan.id}
              className={`plan-tab ${selectedPlan === plan.id ? 'active' : ''}`}
              onClick={() => setSelectedPlan(plan.id)}
              data-testid={`tab-${plan.id}`}
            >
              {plan.popular && <span className="tab-badge">Popular</span>}
              <span className="tab-name">{plan.name}</span>
              <span className="tab-price">
                {plan.monthly ? `$${plan.price}/mes` : `$${plan.price}`}
              </span>
            </button>
          ))}
        </div>

        <div className="comprar-grid">
          {/* Left - Product Info */}
          <div className="comprar-product">
            <h1>{currentPlan.name}</h1>
            <p className="product-subtitle">{currentPlan.description}</p>

            <div className="product-price-box">
              {selectedPlan === 'soporte' ? (
                <>
                  <span className="price-main">${SOPORTE_OPTIONS[selectedSoporte].price}</span>
                  <span className="price-currency">USD/mes</span>
                  {SOPORTE_OPTIONS[selectedSoporte].discount > 0 && (
                    <div className="price-discount-tag">
                      {SOPORTE_OPTIONS[selectedSoporte].discount}% OFF
                    </div>
                  )}
                  <p className="price-note">
                    {SOPORTE_OPTIONS[selectedSoporte].months === 1 
                      ? 'Pago mensual - Cancelá cuando quieras'
                      : `Pago único de $${SOPORTE_OPTIONS[selectedSoporte].total} USD por ${SOPORTE_OPTIONS[selectedSoporte].period}`
                    }
                  </p>
                </>
              ) : (
                <>
                  {selectedPlan === 'instalacion' && <span className="price-old">$697</span>}
                  <span className="price-main">${currentPlan.price}</span>
                  <span className="price-currency">USD</span>
                  <p className="price-note">Pago único - Tuyo para siempre</p>
                </>
              )}
            </div>

            {/* Soporte period selector */}
            {selectedPlan === 'soporte' && (
              <div className="soporte-options" data-testid="soporte-options">
                <h3>Elegí tu período:</h3>
                {SOPORTE_OPTIONS.map((opt, idx) => (
                  <button
                    key={idx}
                    className={`soporte-option ${selectedSoporte === idx ? 'active' : ''}`}
                    onClick={() => setSelectedSoporte(idx)}
                    data-testid={`soporte-${opt.months}m`}
                  >
                    <div className="soporte-option-left">
                      <span className="soporte-period">{opt.period}</span>
                      <span className="soporte-detail">
                        {opt.months === 1 ? 'Pago mes a mes' : `Pago único $${opt.total}`}
                      </span>
                    </div>
                    <div className="soporte-option-right">
                      <span className="soporte-price">${opt.price}/mes</span>
                      {opt.discount > 0 && (
                        <span className="soporte-discount">-{opt.discount}%</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}

            <div className="product-includes">
              <h3>Qué incluye:</h3>
              <ul>
                {currentPlan.features.map((feature, idx) => (
                  <li key={idx}>
                    <CheckCircle className="w-4 h-4" />
                    {feature}
                  </li>
                ))}
              </ul>
            </div>

            <div className="product-guarantee">
              <Shield className="w-5 h-5" />
              <div>
                <strong>Garantía de 7 días</strong>
                <p>Si no funciona como se describe, te devolvemos el 100%</p>
              </div>
            </div>
          </div>

          {/* Right - Checkout Form */}
          <div className="comprar-checkout">
            <h2>Completá tu compra</h2>
            
            <div className="checkout-form">
              <div className="form-group">
                <label>Nombre completo</label>
                <input 
                  type="text" 
                  placeholder="Tu nombre"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  data-testid="input-name"
                />
              </div>
              
              <div className="form-group">
                <label>Email</label>
                <input 
                  type="email" 
                  placeholder="tu@email.com"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  data-testid="input-email"
                />
                <span className="form-hint">Recibirás el acceso en este email</span>
              </div>

              <div className="checkout-summary">
                <div className="summary-row">
                  <span>{currentPlan.name}</span>
                  <span>{getPriceLabel()}</span>
                </div>
                {selectedPlan === 'soporte' && SOPORTE_OPTIONS[selectedSoporte].discount > 0 && (
                  <div className="summary-row discount">
                    <span>Descuento ({SOPORTE_OPTIONS[selectedSoporte].discount}%)</span>
                    <span>-${(SOPORTE_OPTIONS[selectedSoporte].months * 100) - SOPORTE_OPTIONS[selectedSoporte].total} USD</span>
                  </div>
                )}
                <div className="summary-row total">
                  <span>Total</span>
                  <span>${getTotal()} USD</span>
                </div>
              </div>

              <Button 
                size="lg" 
                className="w-full checkout-button"
                onClick={handlePurchase}
                disabled={loading}
                data-testid="checkout-button"
              >
                {loading ? (
                  'Procesando...'
                ) : (
                  <>
                    <CreditCard className="w-4 h-4 mr-2" />
                    Pagar ${getTotal()} USD
                  </>
                )}
              </Button>

              <div className="checkout-secure">
                <Shield className="w-4 h-4" />
                <span>Pago seguro con Stripe</span>
              </div>

              <div className="checkout-methods">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/Stripe_Logo%2C_revised_2016.svg/512px-Stripe_Logo%2C_revised_2016.svg.png" alt="Stripe" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
