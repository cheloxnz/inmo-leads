import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  TrendingUp, Eye, MousePointerClick, MessageCircle,
  Sparkles, Package, Users, Copy, Code
} from 'lucide-react';
import { toast } from 'sonner';

export default function WidgetAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [tenantId, setTenantId] = useState('');

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/widget/analytics?days=${days}`);
      setData(res.data);
    } catch (err) {
      toast.error('Error cargando analytics');
    } finally {
      setLoading(false);
    }
  }, [days]);

  const fetchTenantId = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/catalog`);
      if (res.data?.length > 0) setTenantId(res.data[0].tenant_id || '');
    } catch (err) {}
  }, []);

  useEffect(() => { fetchAnalytics(); fetchTenantId(); }, [fetchAnalytics, fetchTenantId]);

  const publicUrl = tenantId ? `${window.location.origin}/p/catalogo/${tenantId}` : '';
  const widgetJs = tenantId ? `${API}/public/catalog/${tenantId}/widget.js` : '';
  const iframeSnippet = tenantId ? `<iframe src="${publicUrl}?embed=1" style="width:100%;min-height:600px;border:0;border-radius:12px" loading="lazy"></iframe>` : '';
  const scriptSnippet = tenantId ? `<div id="inmobot-catalog"></div>\n<script src="${widgetJs}" async></script>` : '';

  const copy = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copiado`);
  };

  if (loading) return <div className="wa-loading">Cargando analytics del widget...</div>;
  if (!data) return null;

  const s = data.summary || {};

  return (
    <div className="widget-analytics" data-testid="widget-analytics">
      <div className="wa-header">
        <div>
          <h1><TrendingUp className="inline w-6 h-6 mr-2" />Analytics del Catalogo Publico</h1>
          <p>Tracking de conversion del widget embebible en tu sitio web</p>
        </div>
        <select
          value={days}
          onChange={e => setDays(parseInt(e.target.value))}
          data-testid="wa-days-select"
          className="wa-days"
        >
          <option value={7}>Ultimos 7 dias</option>
          <option value={30}>Ultimos 30 dias</option>
          <option value={90}>Ultimos 90 dias</option>
        </select>
      </div>

      {/* KPIs */}
      <div className="wa-kpis" data-testid="wa-kpis">
        <Card className="wa-kpi">
          <CardContent>
            <Eye className="wa-kpi-icon text-blue-500" />
            <div className="wa-kpi-value" data-testid="wa-kpi-views">{s.views || 0}</div>
            <div className="wa-kpi-label">Vistas</div>
            <div className="wa-kpi-sub">{s.unique_visitors || 0} unicos</div>
          </CardContent>
        </Card>
        <Card className="wa-kpi">
          <CardContent>
            <MousePointerClick className="wa-kpi-icon text-purple-500" />
            <div className="wa-kpi-value">{s.clicks_product || 0}</div>
            <div className="wa-kpi-label">Clicks en productos</div>
            <div className="wa-kpi-sub">CTR {s.click_through_rate || 0}%</div>
          </CardContent>
        </Card>
        <Card className="wa-kpi">
          <CardContent>
            <MessageCircle className="wa-kpi-icon text-green-500" />
            <div className="wa-kpi-value">{s.clicks_whatsapp || 0}</div>
            <div className="wa-kpi-label">Clicks a WhatsApp</div>
          </CardContent>
        </Card>
        <Card className="wa-kpi">
          <CardContent>
            <Sparkles className="wa-kpi-icon text-amber-500" />
            <div className="wa-kpi-value">{s.ai_searches || 0}</div>
            <div className="wa-kpi-label">Busquedas IA</div>
          </CardContent>
        </Card>
        <Card className="wa-kpi wa-kpi-highlight">
          <CardContent>
            <Users className="wa-kpi-icon text-emerald-500" />
            <div className="wa-kpi-value" data-testid="wa-kpi-leads">{s.leads_generated || 0}</div>
            <div className="wa-kpi-label">Leads generados</div>
            <div className="wa-kpi-sub">Conversion {s.conversion_rate || 0}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Embed code */}
      <Card className="wa-section">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2"><Code className="w-4 h-4" /> Codigo para incrustar en tu sitio</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="wa-embed-block">
            <div className="wa-embed-label">Opcion 1 - Script drop-in (recomendado):</div>
            <pre data-testid="wa-embed-script">{scriptSnippet}</pre>
            <button onClick={() => copy(scriptSnippet, 'Script')} data-testid="wa-copy-script"><Copy className="w-3 h-3" /> Copiar</button>
          </div>
          <div className="wa-embed-block">
            <div className="wa-embed-label">Opcion 2 - iframe directo:</div>
            <pre data-testid="wa-embed-iframe">{iframeSnippet}</pre>
            <button onClick={() => copy(iframeSnippet, 'iframe')} data-testid="wa-copy-iframe"><Copy className="w-3 h-3" /> Copiar</button>
          </div>
          <div className="wa-embed-block">
            <div className="wa-embed-label">Link directo:</div>
            <pre>{publicUrl}</pre>
            <button onClick={() => copy(publicUrl, 'Link')} data-testid="wa-copy-link"><Copy className="w-3 h-3" /> Copiar</button>
          </div>
        </CardContent>
      </Card>

      {/* Attribution */}
      {data.attribution && data.attribution.total_leads_period > 0 && (
        <Card className="wa-section wa-attribution">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2"><Users className="w-4 h-4" /> Atribucion de Leads al Widget</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="wa-attr-row" data-testid="wa-attribution">
              <div className="wa-attr-card">
                <div className="wa-attr-value">{data.attribution.widget_leads}</div>
                <div className="wa-attr-label">Leads del widget</div>
              </div>
              <div className="wa-attr-card">
                <div className="wa-attr-value">{data.attribution.total_leads_period}</div>
                <div className="wa-attr-label">Leads totales (periodo)</div>
              </div>
              <div className="wa-attr-card wa-attr-pct">
                <div className="wa-attr-value">{data.attribution.widget_share_pct}%</div>
                <div className="wa-attr-label">Share del widget</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Top products */}
      {data.top_products?.length > 0 && (
        <Card className="wa-section">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2"><Package className="w-4 h-4" /> Productos mas clickeados</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="wa-table">
              <thead>
                <tr><th>Producto</th><th>Categoria</th><th>Precio</th><th className="text-right">Clicks</th></tr>
              </thead>
              <tbody>
                {data.top_products.map((p, i) => (
                  <tr key={i}>
                    <td><strong>{p.name}</strong></td>
                    <td>{p.category || '-'}</td>
                    <td>{p.price ? `$${p.price}` : '-'}</td>
                    <td className="text-right">{p.clicks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Top AI queries */}
      {data.top_queries?.length > 0 && (
        <Card className="wa-section">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2"><Sparkles className="w-4 h-4" /> Top busquedas IA</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="wa-queries">
              {data.top_queries.map((q, i) => (
                <li key={i}>
                  <span className="wa-query-text">"{q.query}"</span>
                  <span className="wa-query-count">{q.count}x</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Daily chart */}
      {data.by_day?.length > 0 && (
        <Card className="wa-section">
          <CardHeader>
            <CardTitle className="text-sm">Actividad diaria</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="wa-table">
              <thead>
                <tr><th>Fecha</th><th className="text-right">Vistas</th><th className="text-right">Clicks</th><th className="text-right">WhatsApp</th><th className="text-right">IA</th></tr>
              </thead>
              <tbody>
                {data.by_day.slice(-14).reverse().map((d, i) => (
                  <tr key={i}>
                    <td>{d.date}</td>
                    <td className="text-right">{d.views}</td>
                    <td className="text-right">{d.clicks_product}</td>
                    <td className="text-right">{d.clicks_whatsapp}</td>
                    <td className="text-right">{d.ai_searches}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {data.summary?.views === 0 && (
        <Card className="wa-section">
          <CardContent>
            <div className="wa-empty">
              <p><strong>Aun no hay datos.</strong> Pega el codigo de arriba en tu sitio web y empezaran a aparecer las visitas.</p>
              <a href={publicUrl} target="_blank" rel="noopener noreferrer" className="wa-preview-link">
                Ver preview del catalogo publico
              </a>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
