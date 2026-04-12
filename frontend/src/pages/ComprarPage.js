import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { 
  CheckCircle, ArrowLeft, CreditCard, Shield, 
  Code, MessageSquare, Wrench, Plus, X,
  Monitor, Rocket
} from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const BASE_PLANS = [
  {
    id: 'codigo',
    name: 'Codigo Solo',
    price: 147,
    description: 'Código fuente + documentación. Lo instalás vos.',
    features: [
      'Código fuente completo (React + Python)',
      'Bot de WhatsApp con IA (GPT-4)',
      'Dashboard de gestión completo',
      'Landing page personalizable',
      'Docker + Railway listos para deploy',
      'Documentación paso a paso (800+ líneas)',
      'Licencia comercial incluida',
    ]
  },
  {
    id: 'instalacion',
    name: 'Codigo + Instalacion',
    price: 497,
    popular: true,
    description: 'Todo lo anterior + nosotros te lo dejamos funcionando.',
    features: [
      'Todo del plan Código Solo',
      'Instalación completa por nosotros',
      'Deploy en Railway o tu servidor',
      'Configuración de WhatsApp Business API',
      'Dominio personalizado + SSL',
      'Bot funcionando y testeado',
      'Videollamada de entrega (30 min)',
    ]
  }
];

const SOPORTE_OPTIONS = [
  { label: 'Mensual', months: 1, pricePerMonth: 100, discount: 0 },
  { label: '6 meses', months: 6, pricePerMonth: 85, discount: 15 },
  { label: '12 meses', months: 12, pricePerMonth: 80, discount: 20 },
  { label: '24 meses', months: 24, pricePerMonth: 70, discount: 30 },
];

export default function ComprarPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [selectedBase, setSelectedBase] = useState(null);
  const [addSoporte, setAddSoporte] = useState(false);
  const [soporteIdx, setSoporteIdx] = useState(1);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({ name: '', email: '' });

  useEffect(() => {
    const plan = searchParams.get('plan');
    if (plan === 'codigo' || plan === 'instalacion') {
      setSelectedBase(plan);
    }
  }, [searchParams]);

  const basePlan = BASE_PLANS.find(p => p.id === selectedBase);
  const soporteOption = SOPORTE_OPTIONS[soporteIdx];

  const getTotal = () => {
    let total = basePlan ? basePlan.price : 0;
    if (addSoporte) {
      total += soporteOption.pricePerMonth * soporteOption.months;
    }
    return total;
  };

  const handlePurchase = async () => {
    if (!selectedBase) {
      alert('Seleccioná un plan base primero');
      return;
    }
    if (!formData.name || !formData.email) {
      alert('Por favor completá tu nombre y email');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/api/create-checkout-session`, {
        plan_id: selectedBase,
        customer_email: formData.email,
        customer_name: formData.name,
        add_soporte: addSoporte,
        soporte_months: addSoporte ? soporteOption.months : null
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

        <div className="comprar-flow">
          {/* Step 1: Base Plan */}
          <div className="comprar-step">
            <div className="step-header">
              <div className="step-number">1</div>
              <h2>Elegi tu plan</h2>
            </div>

            <div className="base-plans-row">
              {BASE_PLANS.map((plan) => (
                <button
                  key={plan.id}
                  className={`base-plan-card ${selectedBase === plan.id ? 'selected' : ''}`}
                  onClick={() => setSelectedBase(plan.id)}
                  data-testid={`plan-${plan.id}`}
                >
                  {plan.popular && <span className="plan-popular-tag">Mas vendido</span>}
                  <div className="base-plan-icon">
                    {plan.id === 'codigo' ? <Code className="w-6 h-6" /> : <Rocket className="w-6 h-6" />}
                  </div>
                  <h3>{plan.name}</h3>
                  <p className="base-plan-desc">{plan.description}</p>
                  <div className="base-plan-price">
                    <span className="base-price-amount">${plan.price}</span>
                    <span className="base-price-currency">USD</span>
                  </div>
                  <span className="base-price-type">Pago unico</span>
                  <ul className="base-plan-features">
                    {plan.features.map((f, i) => (
                      <li key={i}><CheckCircle className="w-3.5 h-3.5" /> {f}</li>
                    ))}
                  </ul>
                  <div className={`plan-select-indicator ${selectedBase === plan.id ? 'active' : ''}`}>
                    {selectedBase === plan.id ? <CheckCircle className="w-5 h-5" /> : <div className="plan-radio" />}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Step 2: Add Soporte (only shows after base plan selected) */}
          {selectedBase && (
            <div className="comprar-step">
              <div className="step-header">
                <div className="step-number">2</div>
                <h2>Agregar soporte? <span className="step-optional">(opcional)</span></h2>
              </div>

              {!addSoporte ? (
                <button 
                  className="add-soporte-btn" 
                  onClick={() => setAddSoporte(true)}
                  data-testid="add-soporte-btn"
                >
                  <div className="add-soporte-left">
                    <div className="add-soporte-icon">
                      <Wrench className="w-5 h-5" />
                    </div>
                    <div>
                      <h4>Soporte + Actualizaciones</h4>
                      <p>Mantenimiento, nuevas funciones y soporte tecnico por WhatsApp</p>
                    </div>
                  </div>
                  <div className="add-soporte-right">
                    <span className="add-soporte-price">Desde $70/mes</span>
                    <div className="add-soporte-plus">
                      <Plus className="w-5 h-5" />
                    </div>
                  </div>
                </button>
              ) : (
                <div className="soporte-panel" data-testid="soporte-panel">
                  <div className="soporte-panel-header">
                    <div className="soporte-panel-title">
                      <Wrench className="w-5 h-5" />
                      <h4>Soporte + Actualizaciones</h4>
                    </div>
                    <button 
                      className="soporte-remove" 
                      onClick={() => setAddSoporte(false)}
                      data-testid="remove-soporte-btn"
                    >
                      <X className="w-4 h-4" />
                      Quitar
                    </button>
                  </div>

                  <div className="soporte-period-grid">
                    {SOPORTE_OPTIONS.map((opt, idx) => (
                      <button
                        key={idx}
                        className={`soporte-period-card ${soporteIdx === idx ? 'active' : ''}`}
                        onClick={() => setSoporteIdx(idx)}
                        data-testid={`soporte-${opt.months}m`}
                      >
                        {opt.discount > 0 && (
                          <span className={`soporte-discount-tag ${opt.discount >= 30 ? 'best' : ''}`}>
                            -{opt.discount}%
                          </span>
                        )}
                        <span className="soporte-period-label">{opt.label}</span>
                        <span className="soporte-period-price">${opt.pricePerMonth}/mes</span>
                        {opt.months > 1 && (
                          <span className="soporte-period-total">${opt.pricePerMonth * opt.months} total</span>
                        )}
                      </button>
                    ))}
                  </div>

                  <ul className="soporte-features-list">
                    <li><CheckCircle className="w-3.5 h-3.5" /> Actualizaciones automaticas del codigo</li>
                    <li><CheckCircle className="w-3.5 h-3.5" /> Nuevas funcionalidades incluidas</li>
                    <li><CheckCircle className="w-3.5 h-3.5" /> Soporte tecnico por WhatsApp</li>
                    <li><CheckCircle className="w-3.5 h-3.5" /> Correccion de bugs prioritaria</li>
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Checkout (only after base plan selected) */}
          {selectedBase && (
            <div className="comprar-step">
              <div className="step-header">
                <div className="step-number">{addSoporte ? '3' : '2'}</div>
                <h2>Completa tu compra</h2>
              </div>

              <div className="checkout-card">
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
                    <span className="form-hint">Recibiras el acceso en este email</span>
                  </div>

                  <div className="checkout-summary">
                    <div className="summary-row">
                      <span>{basePlan.name}</span>
                      <span>${basePlan.price} USD</span>
                    </div>
                    {addSoporte && (
                      <>
                        <div className="summary-row">
                          <span>Soporte ({soporteOption.label})</span>
                          <span>${soporteOption.pricePerMonth * soporteOption.months} USD</span>
                        </div>
                        {soporteOption.discount > 0 && (
                          <div className="summary-row discount">
                            <span>Descuento soporte ({soporteOption.discount}%)</span>
                            <span>-${(100 * soporteOption.months) - (soporteOption.pricePerMonth * soporteOption.months)} USD</span>
                          </div>
                        )}
                      </>
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

                  <div className="checkout-guarantee">
                    <Shield className="w-4 h-4" />
                    <span>7 dias de garantia - 100% devolucion</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
