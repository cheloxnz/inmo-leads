import React, { useState } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Sparkles, Loader2, RefreshCw, Zap, AlertCircle } from 'lucide-react';
import { useFeature } from '../hooks/useFeature';

function urgencyMeta(score) {
  if (score >= 9) return { label: 'CRÍTICA', color: '#dc2626', bg: '#fee2e2' };
  if (score >= 7) return { label: 'ALTA', color: '#ea580c', bg: '#ffedd5' };
  if (score >= 4) return { label: 'MEDIA', color: '#ca8a04', bg: '#fef9c3' };
  return { label: 'BAJA', color: '#0284c7', bg: '#e0f2fe' };
}

export default function AILeadSummary({ leadPhone }) {
  const { enabled: featureEnabled, loading: flagLoading } = useFeature('ai_lead_summary');
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchSummary = async (force = false) => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.post(
        `${API}/leads/${leadPhone}/ai-summary${force ? '?force=true' : ''}`,
      );
      setSummary(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  // Si el flag aún no cargó, no renderizamos nada para evitar flash
  if (flagLoading) return null;

  // Feature OFF → mostramos un upsell card en vez de la card real
  if (!featureEnabled) {
    return (
      <Card className="ai-summary-card upsell" data-testid="ai-summary-upsell">
        <CardHeader className="ai-summary-header">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="w-4 h-4" style={{ color: '#8b5cf6' }} />
            Resumen IA del lead
            <span className="ai-summary-premium-badge">Premium</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="ai-summary-upsell-text">
            Activá la <strong>IA que analiza la conversación</strong> y te dice exactamente qué busca este lead, su nivel de urgencia y el próximo paso recomendado para cerrar la venta.
          </p>
          <Button
            size="sm"
            variant="outline"
            disabled
            className="ai-summary-upsell-btn"
            data-testid="ai-summary-upsell-cta"
          >
            <Zap className="w-3 h-3 mr-1" />
            Contactar para activar
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="ai-summary-card" data-testid="ai-summary-card">
      <CardHeader className="ai-summary-header">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="w-4 h-4" style={{ color: '#8b5cf6' }} />
          Resumen IA del lead
        </CardTitle>
        <div className="ai-summary-actions">
          {summary && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => fetchSummary(true)}
              disabled={loading}
              data-testid="ai-summary-refresh"
              title="Re-generar resumen"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {!summary && !loading && !error && (
          <div className="ai-summary-empty">
            <p>Generá un análisis IA de esta conversación: qué busca, urgencia y próximo paso.</p>
            <Button
              onClick={() => fetchSummary(false)}
              data-testid="ai-summary-generate-btn"
              className="ai-summary-cta-btn"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Generar resumen IA
            </Button>
          </div>
        )}

        {loading && (
          <div className="ai-summary-loading" data-testid="ai-summary-loading">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Analizando conversación con IA…</span>
          </div>
        )}

        {error && (
          <div className="ai-summary-error" data-testid="ai-summary-error">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        {summary && !loading && (
          <div className="ai-summary-content" data-testid="ai-summary-content">
            <div className="ai-summary-narrative">
              {summary.narrative}
            </div>

            <div className="ai-summary-meta-row">
              <UrgencyPill urgency={summary.urgency} reason={summary.urgency_reason} />
              {summary.cached && <span className="ai-summary-cache-tag">cacheado</span>}
            </div>

            <div className="ai-summary-next-step" data-testid="ai-summary-next-step">
              <div className="ai-summary-next-step-label">⚡ Próximo paso</div>
              <div className="ai-summary-next-step-text">{summary.next_step}</div>
            </div>

            {summary.insights?.length > 0 && (
              <div className="ai-summary-section">
                <div className="ai-summary-section-title">Insights</div>
                <ul className="ai-summary-list">
                  {summary.insights.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}

            {summary.buying_signals?.length > 0 && (
              <div className="ai-summary-section">
                <div className="ai-summary-section-title">🎯 Señales de compra</div>
                <ul className="ai-summary-list buying-signals">
                  {summary.buying_signals.map((s, i) => <li key={i}>"{s}"</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function UrgencyPill({ urgency, reason }) {
  const meta = urgencyMeta(urgency);
  return (
    <div
      className="ai-summary-urgency"
      style={{ background: meta.bg, color: meta.color }}
      data-testid="ai-summary-urgency"
      title={reason}
    >
      <strong>{urgency}/10</strong> · {meta.label}
      {reason && <span className="ai-summary-urgency-reason">— {reason}</span>}
    </div>
  );
}
