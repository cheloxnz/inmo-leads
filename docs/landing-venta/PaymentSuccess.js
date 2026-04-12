import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Check, Loader2 } from 'lucide-react';

export default function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('checking');
  const [paymentData, setPaymentData] = useState(null);
  const [attempts, setAttempts] = useState(0);

  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    if (sessionId) {
      pollPaymentStatus();
    } else {
      setStatus('error');
    }
  }, [sessionId]);

  const pollPaymentStatus = async () => {
    if (attempts >= 10) {
      setStatus('timeout');
      return;
    }

    try {
      const response = await axios.get(`${API}/checkout/status/${sessionId}`);
      
      if (response.data.payment_status === 'paid') {
        setStatus('success');
        setPaymentData(response.data);
        return;
      } else if (response.data.status === 'expired') {
        setStatus('expired');
        return;
      }

      // Seguir polling
      setAttempts(prev => prev + 1);
      setTimeout(pollPaymentStatus, 2000);
    } catch (error) {
      console.error('Error checking payment:', error);
      setAttempts(prev => prev + 1);
      setTimeout(pollPaymentStatus, 2000);
    }
  };

  const renderContent = () => {
    switch (status) {
      case 'checking':
        return (
          <div className="payment-status checking">
            <Loader2 className="spinner" />
            <h2>Verificando tu pago...</h2>
            <p>Por favor esperá unos segundos</p>
          </div>
        );
      
      case 'success':
        return (
          <div className="payment-status success">
            <div className="success-icon">
              <Check className="check-icon" />
            </div>
            <h2>¡Pago Exitoso!</h2>
            <p>Gracias por confiar en nosotros</p>
            
            {paymentData && (
              <div className="payment-details">
                <div className="detail-row">
                  <span>Plan:</span>
                  <strong>{paymentData.metadata?.plan_name}</strong>
                </div>
                <div className="detail-row">
                  <span>Monto:</span>
                  <strong>${paymentData.amount} {paymentData.currency?.toUpperCase()}</strong>
                </div>
              </div>
            )}
            
            <div className="next-steps">
              <h3>Próximos pasos:</h3>
              <ol>
                <li>Recibirás un email con los detalles de tu suscripción</li>
                <li>Nos contactaremos en las próximas 24hs para configurar tu cuenta</li>
                <li>Te ayudaremos a conectar tu WhatsApp Business</li>
              </ol>
            </div>
            
            <Button onClick={() => navigate('/')} data-testid="btn-go-home">
              Volver al Inicio
            </Button>
          </div>
        );
      
      case 'expired':
        return (
          <div className="payment-status expired">
            <h2>Sesión Expirada</h2>
            <p>La sesión de pago ha expirado. Por favor intentá nuevamente.</p>
            <Button onClick={() => navigate('/planes')} data-testid="btn-retry">
              Ver Planes
            </Button>
          </div>
        );
      
      case 'timeout':
        return (
          <div className="payment-status timeout">
            <h2>Verificación en Proceso</h2>
            <p>No pudimos confirmar tu pago automáticamente. Si realizaste el pago, recibirás un email de confirmación en breve.</p>
            <p>Si tenés dudas, contactanos a soporte@tudominio.com</p>
            <Button onClick={() => navigate('/')} data-testid="btn-go-home">
              Volver al Inicio
            </Button>
          </div>
        );
      
      case 'error':
      default:
        return (
          <div className="payment-status error">
            <h2>Error</h2>
            <p>No se encontró información del pago.</p>
            <Button onClick={() => navigate('/planes')} data-testid="btn-retry">
              Ver Planes
            </Button>
          </div>
        );
    }
  };

  return (
    <div className="payment-success-page" data-testid="payment-success">
      <Card className="payment-card">
        <CardContent>
          {renderContent()}
        </CardContent>
      </Card>
    </div>
  );
}
