import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { toast } from 'sonner';
import { X, AlertCircle, Lightbulb, Zap, ArrowRight } from 'lucide-react';

const SEVERITY_STYLES = {
  high: {
    icon: AlertCircle,
    container: 'bg-red-50 border-red-300',
    iconClass: 'text-red-500',
    title: 'text-red-900',
    body: 'text-red-700',
    cta: 'bg-red-500 hover:bg-red-600',
  },
  warn: {
    icon: Zap,
    container: 'bg-amber-50 border-amber-300',
    iconClass: 'text-amber-500',
    title: 'text-amber-900',
    body: 'text-amber-700',
    cta: 'bg-amber-500 hover:bg-amber-600',
  },
  info: {
    icon: Lightbulb,
    container: 'bg-blue-50 border-blue-300',
    iconClass: 'text-blue-500',
    title: 'text-blue-900',
    body: 'text-blue-700',
    cta: 'bg-blue-500 hover:bg-blue-600',
  },
};

export default function CoachNudges() {
  const [nudges, setNudges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dismissingId, setDismissingId] = useState(null);

  useEffect(() => {
    fetchNudges();

    // Refrescar nudges al volver a la pestaña (despues de tener foco)
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        fetchNudges();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  const fetchNudges = async () => {
    try {
      const r = await axios.get(`${API}/coach/nudges`);
      setNudges(r.data?.nudges || []);
    } catch (e) {
      // 401 lo maneja el interceptor; otros errores silenciosos
    } finally {
      setLoading(false);
    }
  };

  const dismiss = async (nudge) => {
    setDismissingId(nudge.nudge_id);
    try {
      await axios.post(`${API}/coach/nudges/${nudge.nudge_id}/dismiss`);
      setNudges(prev => prev.filter(n => n.nudge_id !== nudge.nudge_id));
    } catch (e) {
      toast.error('No se pudo descartar el aviso');
    } finally {
      setDismissingId(null);
    }
  };

  if (loading || nudges.length === 0) {
    return null;
  }

  // Mostrar maximo 3 nudges (los mas relevantes ya vienen ordenados por created_at desc)
  const visible = nudges.slice(0, 3);

  return (
    <div data-testid="coach-nudges" className="space-y-3 mb-6">
      {visible.map((n) => {
        const style = SEVERITY_STYLES[n.severity] || SEVERITY_STYLES.info;
        const Icon = style.icon;
        return (
          <div
            key={n.nudge_id}
            data-testid={`coach-nudge-${n.nudge_type}`}
            className={`relative border rounded-lg p-4 flex items-start gap-3 ${style.container}`}
          >
            <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${style.iconClass}`} />
            <div className="flex-1 min-w-0">
              <h4 className={`font-semibold text-sm ${style.title}`}>{n.title}</h4>
              <p className={`text-sm mt-1 ${style.body}`}>{n.body}</p>
              <a
                href={n.cta_url}
                data-testid={`coach-nudge-cta-${n.nudge_type}`}
                className={`inline-flex items-center gap-1 mt-3 text-xs px-3 py-1.5 text-white rounded-full font-medium transition-colors ${style.cta}`}
              >
                {n.cta_text} <ArrowRight className="w-3 h-3" />
              </a>
            </div>
            <button
              data-testid={`coach-nudge-dismiss-${n.nudge_type}`}
              onClick={() => dismiss(n)}
              disabled={dismissingId === n.nudge_id}
              className={`flex-shrink-0 ${style.iconClass} hover:opacity-70 transition-opacity disabled:opacity-30`}
              aria-label="Descartar"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
      {nudges.length > 3 && (
        <p className="text-xs text-gray-500 italic">
          + {nudges.length - 3} aviso(s) más en cola
        </p>
      )}
    </div>
  );
}
