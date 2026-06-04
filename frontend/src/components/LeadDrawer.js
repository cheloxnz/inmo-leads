import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import { X, ExternalLink, MessageCircle, Phone, MapPin, DollarSign, Target, Calendar, Clock } from 'lucide-react';

const STATUS_LABELS = { hot: '🔥 Caliente', warm: '🟡 Tibio', cold: '❄️ Frío' };
const STATUS_COLORS = { hot: 'badge-hot', warm: 'badge-warm', cold: 'badge-cold' };

const INTENT_LABELS = {
  comprar: '🏠 Comprar', alquilar: '🔑 Alquilar',
  vender: '💰 Vender', inversion: '📈 Inversión',
};

export default function LeadDrawer({ phone, onClose }) {
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const drawerRef = useRef(null);

  useEffect(() => {
    if (!phone) return;
    setLoading(true);
    setLead(null);
    axios.get(`${API}/leads/${phone}`)
      .then(r => setLead(r.data))
      .catch(() => toast.error('Error cargando lead'))
      .finally(() => setLoading(false));
  }, [phone]);

  // Cerrar con Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const formatPhone = (p) => {
    const n = String(p).replace(/\D/g, '');
    if (n.startsWith('549') && n.length === 13)
      return `+54 9 ${n.slice(3, 5)} ${n.slice(5, 9)}-${n.slice(9)}`;
    return `+${n}`;
  };

  const formatDate = (d) => d
    ? new Date(d).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
    : null;

  const formatTime = (d) => d
    ? new Date(d).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
    : null;

  const timeAgo = (d) => {
    if (!d) return null;
    const diff = Math.floor((Date.now() - new Date(d)) / 1000);
    if (diff < 60) return 'hace un momento';
    if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
    if (diff < 172800) return 'ayer';
    return `hace ${Math.floor(diff / 86400)} días`;
  };

  if (!phone) return null;

  return (
    <>
      {/* Overlay */}
      <div className="drawer-overlay" onClick={onClose} />

      {/* Panel */}
      <aside className="lead-drawer" ref={drawerRef}>
        {/* Header */}
        <div className="drawer-header">
          <div className="drawer-header-left">
            <button className="drawer-close-btn" onClick={onClose} title="Cerrar (Esc)">
              <X className="w-4 h-4" />
            </button>
            {lead && (
              <Badge className={STATUS_COLORS[lead.status]}>
                {STATUS_LABELS[lead.status] || lead.status}
              </Badge>
            )}
          </div>
          {lead && (
            <div className="drawer-header-actions">
              <Button
                size="sm"
                variant="outline"
                className="drawer-wa-btn"
                onClick={() => window.open(`https://wa.me/${lead.phone}`, '_blank')}
              >
                <MessageCircle className="w-3.5 h-3.5 mr-1" />
                WhatsApp
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => navigate(`/leads/${lead.phone}`)}
                title="Ver detalle completo"
              >
                <ExternalLink className="w-3.5 h-3.5 mr-1" />
                Detalle
              </Button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="drawer-loading">Cargando...</div>
        ) : !lead ? (
          <div className="drawer-loading">No se encontró el lead.</div>
        ) : (
          <ScrollArea className="drawer-scroll">
            {/* Identidad */}
            <div className="drawer-section drawer-identity">
              <h2 className="drawer-name">{lead.name || 'Sin nombre'}</h2>
              <p className="drawer-phone">
                <Phone className="w-3.5 h-3.5" />
                {formatPhone(lead.phone)}
              </p>
            </div>

            {/* Score */}
            <div className="drawer-section drawer-score-row">
              <span className="drawer-score-label">Score</span>
              <div className="drawer-score-bar-wrap">
                <div
                  className="score-bar-fill"
                  style={{ width: `${Math.round((lead.score / 12) * 100)}%` }}
                  data-score={lead.score}
                />
              </div>
              <span className="drawer-score-num">{lead.score}/12</span>
            </div>

            {/* Datos clave */}
            <div className="drawer-section drawer-fields">
              {lead.intent && (
                <div className="drawer-field">
                  <Target className="w-3.5 h-3.5" />
                  <span className="drawer-field-label">Intención</span>
                  <span className="drawer-field-val">{INTENT_LABELS[lead.intent] || lead.intent}</span>
                </div>
              )}
              {lead.zone && (
                <div className="drawer-field">
                  <MapPin className="w-3.5 h-3.5" />
                  <span className="drawer-field-label">Zona</span>
                  <span className="drawer-field-val">{lead.zone}</span>
                </div>
              )}
              {lead.budget_text && (
                <div className="drawer-field">
                  <DollarSign className="w-3.5 h-3.5" />
                  <span className="drawer-field-label">Presupuesto</span>
                  <span className="drawer-field-val">{lead.budget_text}</span>
                </div>
              )}
              {lead.appointment_datetime && (
                <div className="drawer-field">
                  <Calendar className="w-3.5 h-3.5" />
                  <span className="drawer-field-label">Cita</span>
                  <span className="drawer-field-val">
                    {formatDate(lead.appointment_datetime)} {formatTime(lead.appointment_datetime)}
                  </span>
                </div>
              )}
              {lead.last_message_at && (
                <div className="drawer-field">
                  <Clock className="w-3.5 h-3.5" />
                  <span className="drawer-field-label">Última actividad</span>
                  <span className="drawer-field-val">{timeAgo(lead.last_message_at)}</span>
                </div>
              )}
            </div>

            {/* Notas */}
            {lead.notes && (
              <div className="drawer-section">
                <p className="drawer-section-title">Notas</p>
                <p className="drawer-notes">{lead.notes}</p>
              </div>
            )}

            {/* Conversación */}
            <div className="drawer-section">
              <p className="drawer-section-title">
                Conversación
                {lead.conversation_history?.length > 0 && (
                  <span className="drawer-conv-count"> · {lead.conversation_history.length} mensajes</span>
                )}
              </p>
              {!lead.conversation_history?.length ? (
                <p className="drawer-no-conv">Sin mensajes registrados.</p>
              ) : (
                <div className="drawer-chat">
                  {lead.conversation_history.map((msg, i) => (
                    <div
                      key={i}
                      className={`drawer-bubble ${msg.from === 'customer' ? 'bubble-customer' : 'bubble-bot'}`}
                    >
                      <p className="bubble-text">{msg.text}</p>
                      {msg.timestamp && (
                        <p className="bubble-time">
                          {new Date(msg.timestamp).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>
        )}
      </aside>
    </>
  );
}
