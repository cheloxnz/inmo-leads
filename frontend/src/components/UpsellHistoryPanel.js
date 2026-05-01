import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Mail, RefreshCw, TrendingUp, CheckCircle2, XCircle,
  Loader2, Zap, Target, DollarSign
} from 'lucide-react';

export default function UpsellHistoryPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/superadmin/upsell/history?limit=50&days=90`);
      setData(res.data);
    } catch (err) {
      console.error('upsell history fetch err', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleRunNow = async () => {
    if (!window.confirm(
      'Ejecutar corrida de upsell ahora? Se evaluarán tenants Pro y se les mandarán emails '
      + '(respeta cooldown 30 días salvo UPSELL_FORCE=1).'
    )) return;
    setRunning(true);
    try {
      const res = await axios.post(`${API}/superadmin/upsell/run`);
      const { evaluated, sent, skipped_cooldown, conversions_marked } = res.data;
      toast.success(
        `Evaluados: ${evaluated} · Enviados: ${sent} · En cooldown: ${skipped_cooldown} · Conversiones marcadas: ${conversions_marked}`
      );
      fetch();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error ejecutando upsell');
    } finally {
      setRunning(false);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  const stats = data?.stats || {};
  const items = data?.items || [];

  return (
    <Card className="upsell-panel" data-testid="upsell-history-panel">
      <CardHeader className="upsell-head">
        <div>
          <CardTitle className="upsell-title">
            <Zap className="w-5 h-5" /> Upsell History · Pro → Enterprise
          </CardTitle>
          <p className="upsell-sub">
            Emails automáticos enviados a tenants Pro con alta demanda insatisfecha.
            Conversión = tenant upgradea a Enterprise dentro de los 90 días post-envío.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Button size="sm" variant="outline" onClick={fetch} disabled={loading} data-testid="btn-refresh-upsell">
            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          </Button>
          <Button size="sm" onClick={handleRunNow} disabled={running} data-testid="btn-run-upsell-now">
            {running ? <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Corriendo...</> : <><Zap className="w-3 h-3 mr-1" /> Ejecutar ahora</>}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading && !data ? (
          <div className="unmet-empty"><Loader2 className="w-5 h-5 animate-spin" /> Cargando...</div>
        ) : (
          <>
            {/* Stats */}
            <div className="upsell-stats-grid">
              <div className="upsell-stat">
                <Mail className="w-4 h-4" />
                <div>
                  <div className="upsell-stat-num" data-testid="upsell-stat-sent">{stats.total_sent || 0}</div>
                  <div className="upsell-stat-label">Enviados (90d)</div>
                </div>
              </div>
              <div className="upsell-stat">
                <CheckCircle2 className="w-4 h-4" />
                <div>
                  <div className="upsell-stat-num">{stats.delivered || 0}</div>
                  <div className="upsell-stat-label">Entregados</div>
                </div>
              </div>
              <div className="upsell-stat upsell-stat-conv">
                <Target className="w-4 h-4" />
                <div>
                  <div className="upsell-stat-num" data-testid="upsell-stat-converted">
                    {stats.converted || 0}
                  </div>
                  <div className="upsell-stat-label">Convertidos</div>
                </div>
              </div>
              <div className="upsell-stat upsell-stat-rate">
                <TrendingUp className="w-4 h-4" />
                <div>
                  <div className="upsell-stat-num" data-testid="upsell-stat-rate">
                    {stats.conversion_rate || 0}%
                  </div>
                  <div className="upsell-stat-label">Tasa conv.</div>
                </div>
              </div>
              <div className="upsell-stat upsell-stat-value">
                <DollarSign className="w-4 h-4" />
                <div>
                  <div className="upsell-stat-num" data-testid="upsell-stat-value">
                    ${Math.round(stats.converted_value_usd || 0).toLocaleString()}
                  </div>
                  <div className="upsell-stat-label">Demanda convertida</div>
                </div>
              </div>
            </div>

            {/* Table */}
            {items.length === 0 ? (
              <div className="unmet-empty" data-testid="upsell-empty">
                <Mail className="w-10 h-10" />
                <p><strong>No se enviaron upsells todavía.</strong></p>
                <p className="unmet-empty-sub">
                  Cuando un tenant Pro acumule 50+ leads esperando o $1500+ en demanda,
                  se le enviará un email automático. Podés forzar una corrida con el botón "Ejecutar ahora".
                </p>
              </div>
            ) : (
              <div className="unmet-table-wrap">
                <table className="unmet-table" data-testid="upsell-table">
                  <thead>
                    <tr>
                      <th>Enviado</th>
                      <th>Tenant</th>
                      <th>Email</th>
                      <th className="num">Leads</th>
                      <th className="num">Demanda USD</th>
                      <th>Estado</th>
                      <th>Conversión</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((e, idx) => (
                      <tr key={idx} data-testid={`upsell-row-${idx}`}>
                        <td>{formatDate(e.sent_at)}</td>
                        <td>
                          <div className="unmet-tenant">
                            <strong>{e.tenant_name || e.tenant_id}</strong>
                          </div>
                        </td>
                        <td style={{ fontSize: '0.78rem' }}>{e.to_email}</td>
                        <td className="num">{e.leads_count || 0}</td>
                        <td className="num">${Math.round(e.value_usd || 0).toLocaleString()}</td>
                        <td>
                          {e.delivered ? (
                            <span className="catalog-badge catalog-badge-ok" style={{ fontSize: '0.62rem' }}>
                              <CheckCircle2 className="w-3 h-3" /> Entregado
                            </span>
                          ) : (
                            <span className="catalog-badge catalog-badge-out" style={{ fontSize: '0.62rem' }}>
                              <XCircle className="w-3 h-3" /> Falló
                            </span>
                          )}
                        </td>
                        <td>
                          {e.converted ? (
                            <span className="upsell-converted-badge" title={`Upgrade a ${e.conversion_plan}`}>
                              <Target className="w-3 h-3" /> ✓ {e.current_plan || e.conversion_plan}
                            </span>
                          ) : e.current_plan === 'enterprise' ? (
                            <span className="catalog-badge catalog-badge-ok" style={{ fontSize: '0.62rem' }}>
                              ya Enterprise
                            </span>
                          ) : (
                            <span className="upsell-pending" data-testid={`upsell-pending-${idx}`}>
                              Pendiente
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
