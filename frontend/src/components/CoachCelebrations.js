import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { API } from '../App';
import { toast } from 'sonner';
import { X, ArrowRight, Sparkles, Share2 } from 'lucide-react';
import ShareCelebrationModal from './ShareCelebrationModal';

export default function CoachCelebrations() {
  const [celebrations, setCelebrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [seeing, setSeeing] = useState(null);
  const [shareTarget, setShareTarget] = useState(null);

  const fetchCelebrations = async () => {
    try {
      const r = await axios.get(`${API}/coach/celebrations`);
      setCelebrations(r.data?.celebrations || []);
    } catch (e) {
      // silencioso (401 lo maneja el interceptor)
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCelebrations();
    const onVisible = () => {
      if (document.visibilityState === 'visible') fetchCelebrations();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  const markSeen = async (cel) => {
    setSeeing(cel.celebration_id);
    try {
      await axios.post(`${API}/coach/celebrations/${cel.celebration_id}/seen`);
      setCelebrations(prev => prev.filter(c => c.celebration_id !== cel.celebration_id));
    } catch (e) {
      toast.error('No se pudo marcar como vista');
    } finally {
      setSeeing(null);
    }
  };

  if (loading || celebrations.length === 0) {
    return null;
  }

  const visible = celebrations.slice(0, 2);

  const renderCTA = (c) => {
    if (!c.cta_url || !c.cta_text) return null;
    const className = 'inline-flex items-center gap-1 mt-3 text-xs px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-full font-medium transition-colors';
    if (c.cta_url.startsWith('/')) {
      return (
        <Link
          to={c.cta_url}
          data-testid={`coach-celebration-cta-${c.celebration_type}`}
          className={className}
        >
          {c.cta_text} <ArrowRight className="w-3 h-3" />
        </Link>
      );
    }
    return (
      <a
        href={c.cta_url}
        target="_blank"
        rel="noopener noreferrer"
        data-testid={`coach-celebration-cta-${c.celebration_type}`}
        className={className}
      >
        {c.cta_text} <ArrowRight className="w-3 h-3" />
      </a>
    );
  };

  return (
    <>
      <div data-testid="coach-celebrations" className="space-y-3 mb-6">
        {visible.map((c) => (
          <div
            key={c.celebration_id}
            data-testid={`coach-celebration-${c.celebration_type}`}
            className="relative border border-emerald-300 rounded-lg p-4 bg-gradient-to-r from-emerald-50 via-green-50 to-teal-50 flex items-start gap-3 shadow-sm"
          >
            <div className="flex-shrink-0 text-3xl mt-0.5" aria-hidden="true">
              {c.emoji || '🎉'}
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="font-bold text-emerald-900 text-sm flex items-center gap-2">
                {c.title}
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              </h4>
              <p className="text-sm text-emerald-800 mt-1">{c.body}</p>
              <div className="flex flex-wrap gap-2 items-center">
                {renderCTA(c)}
                <button
                  data-testid={`coach-celebration-share-${c.celebration_type}`}
                  onClick={() => setShareTarget(c)}
                  className="inline-flex items-center gap-1 mt-3 text-xs px-3 py-1.5 bg-white border border-emerald-400 text-emerald-700 hover:bg-emerald-50 rounded-full font-medium transition-colors"
                >
                  <Share2 className="w-3 h-3" /> Compartir
                </button>
              </div>
            </div>
            <button
              data-testid={`coach-celebration-dismiss-${c.celebration_type}`}
              onClick={() => markSeen(c)}
              disabled={seeing === c.celebration_id}
              className="flex-shrink-0 text-emerald-500 hover:text-emerald-700 transition-opacity disabled:opacity-30"
              aria-label="Cerrar"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {shareTarget && (
        <ShareCelebrationModal
          celebration={shareTarget}
          onClose={() => setShareTarget(null)}
        />
      )}
    </>
  );
}
