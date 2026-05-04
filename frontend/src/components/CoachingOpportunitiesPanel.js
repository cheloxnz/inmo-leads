import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import {
  GraduationCap, TrendingUp, Users, Calendar, Sparkles,
  ChevronDown, ChevronRight, AlertCircle, RefreshCw,
} from 'lucide-react';

/**
 * Dashboard de "Oportunidades de coaching": muestra clusters semánticos de
 * preguntas frecuentes que el bot NO puede responder (no hay learned_response
 * que las cubra), ordenadas por volumen.
 *
 * El admin puede ver ejemplos y enseñar la respuesta en bulk sin abrir cada
 * lead.
 */
export default function CoachingOpportunitiesPanel({ onTaught }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [expandedIdx, setExpandedIdx] = useState(null);

  // Dialog state for "Teach answer"
  const [teachingCluster, setTeachingCluster] = useState(null);
  const [teachAnswer, setTeachAnswer] = useState('');
  const [teachingSubmit, setTeachingSubmit] = useState(false);

  useEffect(() => {
    fetchOpportunities();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  const fetchOpportunities = async () => {
    setLoading(true);
    try {
      const res = await axios.get(
        `${API}/bot-learning/coaching-opportunities?days=${days}&min_cluster_size=2`,
      );
      setData(res.data);
    } catch (err) {
      console.error('coaching-opportunities error:', err);
      toast.error('Error cargando oportunidades: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const openTeachDialog = (cluster) => {
    setTeachingCluster(cluster);
    setTeachAnswer('');
  };

  const submitTeach = async () => {
    if (!teachingCluster || !teachAnswer.trim()) return;
    setTeachingSubmit(true);
    try {
      await axios.post(`${API}/bot-learning`, {
        question: teachingCluster.canonical_question,
        answer: teachAnswer.trim(),
        notes: `Desde Oportunidades de coaching (${teachingCluster.cluster_size} leads)`,
      });
      toast.success(
        `✅ Enseñado. El bot responderá automáticamente a las ${teachingCluster.cluster_size} consultas similares.`,
      );
      setTeachingCluster(null);
      setTeachAnswer('');
      fetchOpportunities(); // refresh
      if (onTaught) onTaught();
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setTeachingSubmit(false);
    }
  };

  const isEmpty = data && (!data.clusters || data.clusters.length === 0);

  return (
    <Card data-testid="coaching-opportunities-panel" style={{ borderTop: '4px solid #8b5cf6' }}>
      <CardHeader>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <GraduationCap className="w-5 h-5" style={{ color: '#8b5cf6' }} />
            Oportunidades de coaching
            {data && (
              <span
                data-testid="opps-total-badge"
                style={{
                  padding: '2px 10px', background: '#8b5cf6', color: '#fff',
                  borderRadius: 999, fontSize: 11, fontWeight: 700,
                }}
              >
                {data.clusters?.length || 0} clusters
              </span>
            )}
          </CardTitle>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              data-testid="opps-days-select"
              style={{
                padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db',
                fontSize: 13, background: '#fff',
              }}
            >
              <option value={7}>Últimos 7 días</option>
              <option value={30}>Últimos 30 días</option>
              <option value={60}>Últimos 60 días</option>
              <option value={90}>Últimos 90 días</option>
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchOpportunities}
              disabled={loading}
              data-testid="opps-refresh-btn"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div style={{
          fontSize: 13, color: '#6b7280', marginBottom: 12, lineHeight: 1.5,
        }}>
          Temas recurrentes de tus clientes que el bot todavía no sabe responder.
          Enseñá una respuesta por cluster y el bot las cubrirá automáticamente.
        </div>

        {data && (
          <div
            data-testid="opps-stats"
            style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: 10, marginBottom: 14,
            }}
          >
            <StatBox label="Preguntas totales" value={data.total_customer_questions} color="#6b7280" />
            <StatBox label="Ya cubiertas por el bot" value={data.already_covered} color="#16a34a" />
            <StatBox label="Sin cubrir" value={data.uncovered} color="#dc2626" />
            <StatBox label="Clusters detectados" value={data.clusters?.length || 0} color="#8b5cf6" />
          </div>
        )}

        {loading && !data && (
          <div style={{ padding: 24, textAlign: 'center', color: '#6b7280', fontSize: 13 }}>
            Analizando conversaciones con IA semántica…
          </div>
        )}

        {data && !data.model_available && (
          <div
            data-testid="opps-model-unavailable"
            style={{
              padding: 14, background: '#fef2f2', border: '1px solid #fecaca',
              borderRadius: 8, color: '#991b1b', fontSize: 13,
              display: 'flex', alignItems: 'center', gap: 8,
            }}
          >
            <AlertCircle className="w-4 h-4" />
            {data.error || 'El modelo de embeddings no está disponible.'}
          </div>
        )}

        {isEmpty && data.model_available && (
          <div
            data-testid="opps-empty-state"
            style={{
              padding: 20, textAlign: 'center', background: '#f0fdf4',
              border: '1px solid #bbf7d0', borderRadius: 8, color: '#166534',
            }}
          >
            <Sparkles className="w-5 h-5 inline mr-2" />
            <strong>¡Buenas noticias!</strong> No encontramos temas recurrentes sin cubrir.
            {data.already_covered > 0 && (
              <> El bot ya está resolviendo <strong>{data.already_covered}</strong> consulta(s) automáticamente.</>
            )}
          </div>
        )}

        {data && data.clusters && data.clusters.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.clusters.map((cluster, idx) => (
              <ClusterCard
                key={idx}
                idx={idx}
                cluster={cluster}
                expanded={expandedIdx === idx}
                onToggle={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                onTeach={() => openTeachDialog(cluster)}
              />
            ))}
          </div>
        )}
      </CardContent>

      {/* Teach dialog */}
      <Dialog open={!!teachingCluster} onOpenChange={(v) => !v && setTeachingCluster(null)}>
        <DialogContent data-testid="teach-dialog">
          <DialogHeader>
            <DialogTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles className="w-5 h-5" style={{ color: '#8b5cf6' }} />
              Enseñar respuesta al bot
            </DialogTitle>
            <DialogDescription>
              Esta respuesta cubrirá las <strong>{teachingCluster?.cluster_size}</strong> consultas
              similares agrupadas en este cluster, y las futuras que aparezcan.
            </DialogDescription>
          </DialogHeader>

          {teachingCluster && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
              <div style={{
                background: '#faf5ff', border: '1px solid #e9d5ff',
                padding: 10, borderRadius: 8, fontSize: 13, color: '#4c1d95',
              }}>
                <strong>Pregunta tipo:</strong> "{teachingCluster.canonical_question}"
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 4 }}>
                  Respuesta que el bot va a dar
                </label>
                <Textarea
                  value={teachAnswer}
                  onChange={(e) => setTeachAnswer(e.target.value)}
                  placeholder="Ej: Sí, en este depto aceptamos mascotas pequeñas hasta 10kg. Contactá al propietario..."
                  rows={5}
                  data-testid="teach-answer-input"
                />
                <p style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
                  Escribila en tono conversacional, como le responderías vos.
                </p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setTeachingCluster(null)} data-testid="teach-cancel-btn">
              Cancelar
            </Button>
            <Button
              onClick={submitTeach}
              disabled={!teachAnswer.trim() || teachingSubmit}
              data-testid="teach-submit-btn"
              style={{
                background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                color: '#fff',
              }}
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {teachingSubmit ? 'Enseñando...' : 'Enseñar al bot'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ---- Sub-components ----

function StatBox({ label, value, color }) {
  return (
    <div
      style={{
        background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8,
        padding: '8px 12px',
      }}
    >
      <div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, color, marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}

function ClusterCard({ idx, cluster, expanded, onToggle, onTeach }) {
  return (
    <div
      data-testid={`cluster-${idx}`}
      style={{
        border: '1px solid #e9d5ff', borderRadius: 10, overflow: 'hidden',
        background: '#fff',
      }}
    >
      <div
        onClick={onToggle}
        style={{
          padding: '12px 14px', cursor: 'pointer', display: 'flex',
          alignItems: 'center', gap: 10,
        }}
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4" style={{ color: '#8b5cf6' }} />
        ) : (
          <ChevronRight className="w-4 h-4" style={{ color: '#8b5cf6' }} />
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 14, fontWeight: 600, color: '#1f2937',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            "{cluster.canonical_question}"
          </div>
          <div style={{
            fontSize: 11, color: '#6b7280', marginTop: 3,
            display: 'flex', gap: 10, flexWrap: 'wrap',
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <Users className="w-3 h-3" />
              {cluster.cluster_size} leads
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <Calendar className="w-3 h-3" />
              última hace {cluster.last_seen_days_ago}d
            </span>
          </div>
        </div>
        <span
          data-testid={`cluster-${idx}-badge`}
          style={{
            padding: '3px 10px', background: '#8b5cf6', color: '#fff',
            borderRadius: 999, fontSize: 11, fontWeight: 700,
            display: 'flex', alignItems: 'center', gap: 3,
          }}
        >
          <TrendingUp className="w-3 h-3" />
          {cluster.cluster_size}
        </span>
        <Button
          size="sm"
          onClick={(e) => { e.stopPropagation(); onTeach(); }}
          data-testid={`cluster-${idx}-teach-btn`}
          style={{
            background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
            color: '#fff', border: 'none',
          }}
        >
          <Sparkles className="w-3 h-3 mr-1" />
          Enseñar
        </Button>
      </div>

      {expanded && (
        <div style={{ padding: '10px 14px', background: '#faf5ff', borderTop: '1px solid #e9d5ff' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#6d28d9', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
            Preguntas agrupadas:
          </div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
            {(cluster.sample_questions || []).map((s, i) => (
              <li
                key={i}
                data-testid={`cluster-${idx}-sample-${i}`}
                style={{
                  padding: '6px 0', fontSize: 12, color: '#374151',
                  borderBottom: i < cluster.sample_questions.length - 1 ? '1px solid #f3e8ff' : 'none',
                }}
              >
                <span style={{ color: '#7c3aed', marginRight: 6 }}>→</span>
                "{s.question}"
                <span style={{ fontSize: 10, color: '#9ca3af', marginLeft: 6 }}>
                  ({s.lead_name} · hace {s.days_ago}d)
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
