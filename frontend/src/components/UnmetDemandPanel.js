import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TrendingUp, RefreshCw, Flame, Package, Users, Loader2 } from 'lucide-react';

export default function UnmetDemandPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

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
        ) : !data || data.top_products.length === 0 ? (
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
                  </tr>
                </thead>
                <tbody>
                  {data.top_products.map((p, idx) => (
                    <tr key={`${p.tenant_id}-${p.product_id}`} data-testid={`unmet-row-${idx}`}>
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
