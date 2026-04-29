import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Gift, Copy, CheckCircle, AlertTriangle, Clock, XCircle, Sparkles, Share2,
} from 'lucide-react';

const STATUS_META = {
  active:    { label: 'Activa',     icon: <CheckCircle className="w-3 h-3" />, cls: 'rp-status-active' },
  pending:   { label: 'Pendiente',  icon: <Clock className="w-3 h-3" />,       cls: 'rp-status-pending' },
  expired:   { label: 'Expirada',   icon: <XCircle className="w-3 h-3" />,     cls: 'rp-status-expired' },
  cancelled: { label: 'Cancelada',  icon: <XCircle className="w-3 h-3" />,     cls: 'rp-status-cancelled' },
};

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return iso; }
}

function daysUntil(iso) {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms)) return null;
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

export default function ReferralProgramSection() {
  const { user, isSuperAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isSuperAdmin) return;
    fetchSummary();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchSummary = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.get(`${API}/commissions/summary`);
      setData(res.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Error cargando programa de referidos');
    } finally {
      setLoading(false);
    }
  };

  if (isSuperAdmin) return null;
  if (loading) {
    return (
      <div className="rp-section" data-testid="referral-program-loading">
        <div className="rp-skeleton">Cargando programa de referidos…</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="rp-section" data-testid="referral-program-error">
        <div className="rp-error">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      </div>
    );
  }
  if (!data) return null;

  const tenantId = user?.tenant_id;
  const refLink = tenantId
    ? `${window.location.origin}/signup?ref=${encodeURIComponent(tenantId)}&utm_source=referral&utm_medium=link&utm_campaign=tenant_share`
    : '';
  const credit = data.active_credit || {};
  const config = data.config || {};
  const lifetime = data.total_lifetime_credit_usd || 0;

  const handleCopy = async () => {
    if (!refLink) return;
    try {
      await navigator.clipboard.writeText(refLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('clipboard failed', err);
    }
  };

  const handleShareNative = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Probá InmoBot',
          text: 'Te invito a probar InmoBot — bot de WhatsApp con IA para tu negocio. Setup en 5 minutos.',
          url: refLink,
        });
      } catch (e) { /* user cancelled */ }
    } else {
      handleCopy();
    }
  };

  const commissions = data.commissions || [];

  return (
    <div className="rp-section" data-testid="referral-program-section">
      <h2 className="rp-title">
        <Gift className="w-5 h-5" />
        Programa de referidos
        <span className="rp-badge-new">${config.amount_per_referral_usd || 5}/mes por referido · 12 meses</span>
      </h2>

      {/* KPI cards */}
      <div className="rp-kpis">
        <div className="rp-kpi rp-kpi-primary" data-testid="rp-kpi-active-credit">
          <div className="rp-kpi-label">Crédito activo este mes</div>
          <div className="rp-kpi-value">
            -${(credit.capped_amount_usd || 0).toFixed(0)}
          </div>
          <div className="rp-kpi-hint">
            {credit.is_capped
              ? <>Topeado al 100% de tu plan (${(credit.plan_price_usd || 0).toFixed(0)}/mes). ¡Estás referindo gratis tu suscripción!</>
              : <>Se descontará en tu próxima factura ({credit.active_count || 0} {credit.active_count === 1 ? 'referido activo' : 'referidos activos'})</>
            }
          </div>
        </div>

        <div className="rp-kpi" data-testid="rp-kpi-active-count">
          <div className="rp-kpi-label">Referidos activos</div>
          <div className="rp-kpi-value">{credit.active_count || 0}</div>
          <div className="rp-kpi-hint">Pagando suscripción ahora</div>
        </div>

        <div className="rp-kpi" data-testid="rp-kpi-lifetime">
          <div className="rp-kpi-label">Total ahorrado histórico</div>
          <div className="rp-kpi-value">${lifetime.toFixed(0)}</div>
          <div className="rp-kpi-hint">Acumulado desde el día 1</div>
        </div>
      </div>

      {/* Cap banner */}
      {credit.is_capped && (
        <div className="rp-cap-banner" data-testid="rp-cap-banner">
          <Sparkles className="w-4 h-4" />
          <div>
            <strong>¡Tu suscripción es gratis!</strong> Tenés ${(credit.amount_usd || 0).toFixed(0)}/mes en
            comisiones — más que el costo de tu plan (${(credit.plan_price_usd || 0).toFixed(0)}/mes). El descuento
            queda topeado al 100% del plan, pero los meses extra siguen contando si en algún momento subís de plan.
          </div>
        </div>
      )}

      {/* Referral link */}
      <Card className="rp-link-card">
        <CardHeader className="rp-link-card-header">
          <CardTitle className="text-sm flex items-center gap-2">
            <Share2 className="w-4 h-4" />
            Tu link de referido
          </CardTitle>
        </CardHeader>
        <CardContent className="rp-link-card-content">
          <div className="rp-link-row">
            <input
              type="text"
              value={refLink}
              readOnly
              className="rp-link-input"
              data-testid="rp-link-input"
              onClick={(e) => e.target.select()}
            />
            <Button size="sm" onClick={handleCopy} data-testid="rp-copy-btn" className="rp-btn-primary">
              {copied ? <CheckCircle className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
              {copied ? '¡Copiado!' : 'Copiar'}
            </Button>
            <Button size="sm" variant="outline" onClick={handleShareNative} data-testid="rp-share-btn">
              <Share2 className="w-4 h-4 mr-1" />
              Compartir
            </Button>
          </div>
          <p className="rp-link-hint">
            Cada inmobiliaria que se registre con tu link y pague la suscripción te suma <strong>${config.amount_per_referral_usd || 5}/mes</strong> de
            descuento durante <strong>12 meses</strong>.
          </p>
        </CardContent>
      </Card>

      {/* Commissions table */}
      {commissions.length > 0 ? (
        <Card className="rp-table-card">
          <CardHeader>
            <CardTitle className="text-sm">Tus referidos</CardTitle>
          </CardHeader>
          <CardContent className="rp-table-card-content">
            <div className="rp-table-wrapper">
              <table className="rp-table" data-testid="rp-commissions-table">
                <thead>
                  <tr>
                    <th>Negocio referido</th>
                    <th>Status</th>
                    <th>$/mes</th>
                    <th>Total acreditado</th>
                    <th>Expira</th>
                  </tr>
                </thead>
                <tbody>
                  {commissions.map((c) => {
                    const meta = STATUS_META[c.status] || STATUS_META.active;
                    const days = c.status === 'active' ? daysUntil(c.expires_at) : null;
                    return (
                      <tr key={c.commission_id} data-testid={`rp-row-${c.commission_id}`}>
                        <td className="rp-td-name">{c.referred_business_name || '—'}</td>
                        <td>
                          <span className={`rp-status ${meta.cls}`}>{meta.icon} {meta.label}</span>
                        </td>
                        <td>${(c.amount_per_month_usd || 0).toFixed(0)}</td>
                        <td>${(c.total_credited_usd || 0).toFixed(0)}</td>
                        <td className="rp-td-expires">
                          {fmtDate(c.expires_at)}
                          {days !== null && (
                            <span className="rp-days-left">{days} días restantes</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="rp-empty-card">
          <CardContent className="rp-empty-content" data-testid="rp-empty">
            <Gift className="w-10 h-10 rp-empty-icon" />
            <div>
              <strong>Aún no tenés referidos.</strong>
              <p>Compartí tu link arriba y empezá a ganar ${config.amount_per_referral_usd || 5}/mes por cada inmobiliaria que active su plan.</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
