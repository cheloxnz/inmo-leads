import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { TrendingUp, RefreshCw, Flame, Package, Users, Loader2, BellOff } from 'lucide-react';

export default function UnmetDemandPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [snoozingKey, setSnoozingKey] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/superadmin/unmet-demand?limit=20`);
      setData(res.data);
    } catch (err) {
      console.error('unmet-demand fetch err', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleSnooze = async (tenant_id, product_id, product_name) => {
    const days = window.prompt(
      `Silenciar "${product_name}" del top de demanda. ¿Cuántos días? (1-365)`,
      '7'
    );
    if (!days) return;
    const n = parseInt(days, 10);
    if (Number.isNaN(n) || n < 1 || n > 365) {
      toast.error('Días debe ser entre 1 y 365');
      return;
    }
    const key = `${tenant_id}-${product_id}`;
    setSnoozingKey(key);
    try {
      await axios.post(`${API}/superadmin/unmet-demand/snooze`, {
        tenant_id, product_id, days: n,
      });
      toast.success(`Silenciado por ${n} día(s)`);
      fetch();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error silenciando');
    } finally {
      setSnoozingKey(null);
    }
  };

  return (
    <Card className="unmet-demand-panel" data-testid="unmet-demand-panel">
      <CardHeader className="unmet-demand-head">
        <div>
          <CardTitle className="unmet-demand-title">
            <TrendingUp className="w-5 h-5" /> Demanda Insatisfecha
          </CardTitle>
          <p className="unmet-demand-sub">
            Productos más pedidos por leads pero que siguen agotados, cross-tenant.
            Score = leads × log(precio). Útil para detectar qué reponer primero.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={fetch}
          disabled={loading}
          data-testid="btn-refresh-unmet-demand"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
        </Button>
      </CardHeader>
      <CardContent>
        {loading && !data ? (
          <div className="unmet-empty"><Loader2 className="w-5 h-5 animate-spin" /> Cargando...</div>
        ) : !data || !data.top_products || data.top_products.length === 0 ? (
          <div className="unmet-empty" data-testid="unmet-empty">
            <Package className="w-10 h-10" />
            <p><strong>Todavía no hay demanda insatisfecha registrada.</strong></p>
            <p className="unmet-empty-sub">
              Cuando un lead pregunte por un producto agotado en cualquier tenant, aparecerá aquí.
            </p>
          </div>
        ) : (
          <>
            <div className="unmet-stats">
              <div className="unmet-stat">
                <Users className="w-4 h-4" />
                <span className="unmet-stat-num" data-testid="unmet-total-leads">
                  {data.total_pending_leads}
                </span>
                <span>leads esperando</span>
              </div>
              <div className="unmet-stat">
                <Package className="w-4 h-4" />
                <span className="unmet-stat-num">{data.total_unique_products}</span>
                <span>productos únicos</span>
              </div>
              {data.snoozed_count > 0 && (
                <div className="unmet-stat" title="Productos silenciados, no aparecen en el top">
                  <BellOff className="w-4 h-4" />
                  <span className="unmet-stat-num">{data.snoozed_count}</span>
                  <span>silenciados</span>
                </div>
              )}
            </div>

            <div className="unmet-table-wrap">
              <table className="unmet-table" data-testid="unmet-table">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Tenant</th>
                    <th>Categoría</th>
                    <th className="num">Precio</th>
                    <th className="num">Leads</th>
                    <th className="num">Score</th>
                    <th className="num">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_products.map((p, idx) => {
                    const key = `${p.tenant_id}-${p.product_id}`;
                    return (
                    <tr key={key} data-testid={`unmet-row-${idx}`}>
                      <td className="unmet-product-cell">
                        {idx < 3 && <Flame className="w-3 h-3 unmet-fire" />}
                        <span>
                          <strong>{p.product_name || '(sin nombre)'}</strong>
                          {!p.product_exists && <em className="unmet-deleted"> (eliminado)</em>}
                        </span>
                      </td>
                      <td>
                        <div className="unmet-tenant">
                          <strong>{p.tenant_name || p.tenant_id}</strong>
                          {p.tenant_email && (
                            <span className="unmet-tenant-email">{p.tenant_email}</span>
                          )}
                        </div>
                      </td>
                      <td>{p.category || '—'}</td>
                      <td className="num">{p.price > 0 ? `$${p.price} ${p.currency}` : '—'}</td>
                      <td className="num"><strong>{p.leads_count}</strong></td>
                      <td className="num unmet-score">{p.urgency_score}</td>
                      <td className="num">
                        <button
                          className="unmet-snooze-btn"
                          title="Silenciar del top por X días"
                          disabled={snoozingKey === key}
                          onClick={() => handleSnooze(p.tenant_id, p.product_id, p.product_name)}
                          data-testid={`btn-snooze-${idx}`}
                        >
                          {snoozingKey === key
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <BellOff className="w-3 h-3" />}
                        </button>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
