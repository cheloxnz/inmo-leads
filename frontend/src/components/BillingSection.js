import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  CreditCard, CheckCircle, AlertCircle, Clock,
  ArrowUpCircle, Zap, Shield, X
} from 'lucide-react';

const PLAN_COLORS = {
  basic: '#2563eb',
  pro: '#8b5cf6',
  enterprise: '#059669'
};

export default function BillingSection() {
  const { isSuperAdmin } = useAuth();
  const [billing, setBilling] = useState(null);
  const [plans, setPlans] = useState({});
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [showPlans, setShowPlans] = useState(false);

  useEffect(() => {
    fetchBilling();
    fetchPlans();
  }, []);

  const fetchBilling = async () => {
    try {
      const res = await axios.get(`${API}/billing`);
      setBilling(res.data);
    } catch (err) {
      console.error('Error fetching billing:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPlans = async () => {
    try {
      const res = await axios.get(`${API}/plans`);
      setPlans(res.data);
    } catch (err) {
      console.error('Error fetching plans:', err);
    }
  };

  const handleSubscribe = async (planId) => {
    setUpgrading(true);
    try {
      const res = await axios.post(`${API}/billing/subscribe`, {
        plan_id: planId,
        origin_url: window.location.origin
      });
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      }
    } catch (err) {
      alert('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUpgrading(false);
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Estas seguro? La suscripcion se cancelara al final del periodo actual.')) return;
    setCancelling(true);
    try {
      await axios.post(`${API}/billing/cancel`);
      fetchBilling();
    } catch (err) {
      alert('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setCancelling(false);
    }
  };

  if (isSuperAdmin) return null;
  if (loading) return <div className="billing-loading">Cargando billing...</div>;

  const statusIcons = {
    active: <CheckCircle className="w-4 h-4 text-green-500" />,
    trial: <Clock className="w-4 h-4 text-blue-500" />,
    past_due: <AlertCircle className="w-4 h-4 text-yellow-500" />,
    suspended: <AlertCircle className="w-4 h-4 text-red-500" />,
    cancelled: <X className="w-4 h-4 text-red-500" />,
    cancelling: <Clock className="w-4 h-4 text-yellow-500" />,
  };

  const statusLabels = {
    active: 'Activa',
    trial: 'Prueba',
    past_due: 'Pago pendiente',
    suspended: 'Suspendida',
    cancelled: 'Cancelada',
    cancelling: 'Se cancela al final del periodo',
  };

  return (
    <div className="billing-section" data-testid="billing-section">
      <h2 className="billing-title">
        <CreditCard className="w-5 h-5" />
        Facturacion y Plan
      </h2>

      {/* Current Plan */}
      <Card className="billing-current">
        <CardContent className="billing-current-content">
          <div className="billing-plan-info">
            <div className="billing-plan-badge" style={{ background: PLAN_COLORS[billing?.plan] || '#2563eb' }}>
              {billing?.plan_name || 'Basic'}
            </div>
            <div className="billing-plan-price">
              <span className="billing-price-amount">${billing?.price_monthly || 0}</span>
              <span className="billing-price-period">/mes</span>
            </div>
          </div>

          <div className="billing-status-row">
            <div className="billing-status">
              {statusIcons[billing?.subscription_status] || statusIcons.active}
              <span>{statusLabels[billing?.subscription_status] || 'Activa'}</span>
            </div>
            {billing?.next_billing_date && (
              <div className="billing-next">
                Proximo cobro: {new Date(billing.next_billing_date).toLocaleDateString('es')}
              </div>
            )}
          </div>

          <div className="billing-limits">
            <div className="billing-limit">
              <span>Leads max:</span>
              <strong>{billing?.max_leads || 500}</strong>
            </div>
            <div className="billing-limit">
              <span>Agentes max:</span>
              <strong>{billing?.max_agents || 3}</strong>
            </div>
          </div>

          <div className="billing-actions">
            <Button size="sm" onClick={() => setShowPlans(!showPlans)} data-testid="btn-change-plan">
              <ArrowUpCircle className="w-4 h-4 mr-1" />
              {showPlans ? 'Ocultar planes' : 'Cambiar plan'}
            </Button>
            {billing?.subscription_status === 'active' && (
              <Button size="sm" variant="outline" onClick={handleCancel} disabled={cancelling} data-testid="btn-cancel-sub">
                {cancelling ? 'Cancelando...' : 'Cancelar suscripcion'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Plans comparison */}
      {showPlans && (
        <div className="billing-plans" data-testid="billing-plans">
          {Object.entries(plans).map(([id, plan]) => (
            <Card key={id} className={`billing-plan-card ${id === billing?.plan ? 'current' : ''}`}>
              <CardContent className="billing-plan-card-content">
                <h3 style={{ color: PLAN_COLORS[id] }}>{plan.name}</h3>
                <div className="billing-plan-card-price">
                  <span>${plan.price_monthly}</span>/mes
                </div>
                <p className="billing-plan-card-desc">{plan.description}</p>
                <ul className="billing-plan-card-features">
                  {plan.features.map((f, i) => (
                    <li key={i}><CheckCircle className="w-3 h-3" /> {f}</li>
                  ))}
                </ul>
                {id === billing?.plan ? (
                  <Button size="sm" disabled className="w-full">Plan actual</Button>
                ) : (
                  <Button 
                    size="sm" 
                    className="w-full"
                    onClick={() => handleSubscribe(id)} 
                    disabled={upgrading}
                    data-testid={`btn-subscribe-${id}`}
                  >
                    {upgrading ? 'Procesando...' : `Suscribirse - $${plan.price_monthly}/mes`}
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Recent Transactions */}
      {billing?.transactions?.length > 0 && (
        <Card className="billing-transactions">
          <CardHeader>
            <CardTitle className="text-sm">Ultimos pagos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="billing-txn-list">
              {billing.transactions.map((txn, i) => (
                <div key={i} className="billing-txn-row">
                  <div className="billing-txn-info">
                    <span className="billing-txn-type">
                      {txn.type === 'recurring' ? 'Pago mensual' : `Suscripcion ${txn.plan_name || ''}`}
                    </span>
                    <span className="billing-txn-date">
                      {new Date(txn.created_at).toLocaleDateString('es')}
                    </span>
                  </div>
                  <div className={`billing-txn-amount ${txn.payment_status === 'paid' ? 'paid' : 'pending'}`}>
                    ${txn.amount} {txn.currency?.toUpperCase() || 'USD'}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
