import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { 
  CheckCircle, ArrowLeft, CreditCard, Shield, 
  Download, FileText, Video, Code, MessageSquare
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ComprarPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: ''
  });

  const handlePurchase = async () => {
    if (!formData.name || !formData.email) {
      alert('Por favor completá tu nombre y email');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/api/create-checkout-session`, {
        plan_id: 'starter',
        customer_email: formData.email,
        customer_name: formData.name
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
        <button className="back-button" onClick={() => navigate('/')}>
          <ArrowLeft className="w-4 h-4" />
          Volver
        </button>

        <div className="comprar-grid">
          {/* Left - Product Info */}
          <div className="comprar-product">
            <h1>InmoBot Completo</h1>
            <p className="product-subtitle">Sistema de ventas con IA para inmobiliarias</p>

            <div className="product-price-box">
              <span className="price-old">$297</span>
              <span className="price-main">$147</span>
              <span className="price-currency">USD</span>
              <p className="price-note">Pago único - Tuyo para siempre</p>
            </div>

            <div className="product-includes">
              <h3>Qué incluye:</h3>
              <ul>
                <li><Code className="w-4 h-4" /> Código fuente completo (React + Python)</li>
                <li><MessageSquare className="w-4 h-4" /> Bot de WhatsApp con IA (GPT)</li>
                <li><CheckCircle className="w-4 h-4" /> Dashboard de gestión completo</li>
                <li><FileText className="w-4 h-4" /> Documentación paso a paso</li>
                <li><Video className="w-4 h-4" /> Videos de instalación</li>
                <li><Download className="w-4 h-4" /> Actualizaciones gratuitas</li>
                <li><Shield className="w-4 h-4" /> Licencia comercial incluida</li>
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
                />
              </div>
              
              <div className="form-group">
                <label>Email</label>
                <input 
                  type="email" 
                  placeholder="tu@email.com"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                />
                <span className="form-hint">Recibirás el acceso en este email</span>
              </div>

              <div className="checkout-summary">
                <div className="summary-row">
                  <span>InmoBot Completo</span>
                  <span>$147 USD</span>
                </div>
                <div className="summary-row total">
                  <span>Total</span>
                  <span>$147 USD</span>
                </div>
              </div>

              <Button 
                size="lg" 
                className="w-full checkout-button"
                onClick={handlePurchase}
                disabled={loading}
              >
                {loading ? (
                  'Procesando...'
                ) : (
                  <>
                    <CreditCard className="w-4 h-4 mr-2" />
                    Pagar $147 USD
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
