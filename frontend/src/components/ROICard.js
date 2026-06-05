import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent } from '@/components/ui/card';
import { TrendingUp, Clock, DollarSign, Flame, Target, PackageX, Sparkles } from 'lucide-react';

export default function ROICard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchROI = () => {
    setLoading(true);
    setError(false);
    axios.get(`${API}/dashboard/roi?days=30`)
      .then(r => setData(r.data))
      .catch(err => { console.error('ROI fetch err', err); setError(true); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchROI(); }, []);

  if (loading) {
    return (
      <Card className="roi-card roi-card-loading" data-testid="roi-card">
        <CardContent>
          <div className="roi-loading">
            <span className="roi-loading-spinner" />
            Calculando ROI...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="roi-card roi-card-error" data-testid="roi-card">
        <CardContent>
          <div className="roi-error">
            <span className="roi-error-icon">📊</span>
            <div>
              <div className="roi-error-title">ROI no disponible</div>
              <div className="roi-error-sub">No se pudieron cargar las métricas de ROI.</div>
            </div>
            <button className="roi-retry-btn" onClick={fetchROI}>↺ Reintentar</button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const pipelineFormatted = Math.round(data.estimated_pipeline_usd).toLocaleString();
  const unmetFormatted = Math.round(data.unmet_demand_usd).toLocaleString();

  return (
    <Card className="roi-card" data-testid="roi-card">
      <CardContent>
        <div className="roi-hero">
          <div className="roi-hero-icon">
            <Sparkles className="w-6 h-6" />
          </div>
          <div className="roi-hero-text">
            <div className="roi-hero-label">InmoBot generó para vos (últimos 30 días)</div>
            <div className="roi-hero-value" data-testid="roi-pipeline">
              ${pipelineFormatted}
              <span className="roi-hero-sub"> en pipeline estimado</span>
            </div>
            <div className="roi-hero-sentence">{data.summary_sentence}</div>
          </div>
        </div>

        <div className="roi-metrics-grid">
          <div className="roi-metric">
            <Flame className="w-4 h-4" />
            <div>
              <div className="roi-metric-num" data-testid="roi-hot-leads">{data.hot_leads}</div>
              <div className="roi-metric-label">Hot leads</div>
            </div>
          </div>
          <div className="roi-metric">
            <Target className="w-4 h-4" />
            <div>
              <div className="roi-metric-num">{data.conversion_rate}%</div>
              <div className="roi-metric-label">Conversión</div>
            </div>
          </div>
          <div className="roi-metric">
            <Clock className="w-4 h-4" />
            <div>
              <div className="roi-metric-num" data-testid="roi-hours-saved">{data.hours_saved}h</div>
              <div className="roi-metric-label">Ahorradas por IA</div>
            </div>
          </div>
          <div className="roi-metric">
            <TrendingUp className="w-4 h-4" />
            <div>
              <div className="roi-metric-num">{data.ai_messages_answered}</div>
              <div className="roi-metric-label">Msgs IA</div>
            </div>
          </div>
          {data.unmet_demand_usd > 0 && (
            <div className="roi-metric roi-metric-warn">
              <PackageX className="w-4 h-4" />
              <div>
                <div className="roi-metric-num" data-testid="roi-unmet">${unmetFormatted}</div>
                <div className="roi-metric-label">Demanda agotada</div>
              </div>
            </div>
          )}
        </div>

        <div className="roi-footer">
          <DollarSign className="w-3 h-3" />
          <span>Valor promedio por deal: ${data.avg_deal_usd}</span>
          <a href="/config" className="roi-footer-link">Ajustar ↗</a>
        </div>
      </CardContent>
    </Card>
  );
}
