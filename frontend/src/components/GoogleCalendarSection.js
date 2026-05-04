import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Calendar, CheckCircle2, XCircle, ExternalLink, Unlink, RefreshCw } from 'lucide-react';

/**
 * Sección de integración con Google Calendar (OAuth per-tenant).
 * - Muestra estado (conectado/desconectado) + email de la cuenta conectada.
 * - Botón "Conectar Google Calendar" → inicia OAuth.
 * - Cuando está conectado, muestra lista de próximos 5 eventos.
 * - Botón "Desconectar" libera los tokens.
 */
export default function GoogleCalendarSection() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const fetchStatus = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/calendar/status`);
      setStatus(r.data);
      if (r.data?.connected) fetchEvents();
    } catch (err) {
      console.error('calendar/status', err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchEvents = async () => {
    setLoadingEvents(true);
    try {
      const r = await axios.get(`${API}/calendar/events?max_results=5`);
      setEvents(r.data?.events || []);
    } catch (err) {
      console.error('calendar/events', err);
    } finally {
      setLoadingEvents(false);
    }
  };

  // Manejo del retorno del OAuth callback (?calendar=connected|error)
  useEffect(() => {
    const calFlag = searchParams.get('calendar');
    if (calFlag === 'connected') {
      toast.success('✅ Google Calendar conectado correctamente');
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('calendar');
      setSearchParams(newParams, { replace: true });
    } else if (calFlag === 'error') {
      const reason = searchParams.get('reason') || '';
      toast.error('No se pudo conectar Google Calendar' + (reason ? ` (${reason})` : ''));
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('calendar');
      newParams.delete('reason');
      setSearchParams(newParams, { replace: true });
    }
    fetchStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnect = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/oauth/calendar/start`);
      const url = r.data?.authorization_url;
      if (url) window.location.href = url;
    } catch (err) {
      toast.error('Error iniciando OAuth: ' + (err.response?.data?.detail || err.message));
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('¿Desconectar Google Calendar? Los próximos eventos no se sincronizarán más.')) return;
    try {
      await axios.post(`${API}/calendar/disconnect`);
      toast.success('Google Calendar desconectado');
      setEvents([]);
      fetchStatus();
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleString('es-AR', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
      });
    } catch { return iso; }
  };

  if (!status) {
    return (
      <Card data-testid="google-calendar-section">
        <CardHeader><CardTitle>📅 Google Calendar</CardTitle></CardHeader>
        <CardContent><div style={{ color: '#6b7280', fontSize: 13 }}>Cargando…</div></CardContent>
      </Card>
    );
  }

  if (!status.configured) {
    return (
      <Card data-testid="google-calendar-section" style={{ borderLeft: '4px solid #9ca3af' }}>
        <CardHeader><CardTitle>📅 Google Calendar</CardTitle></CardHeader>
        <CardContent>
          <div style={{ color: '#6b7280', fontSize: 13 }}>
            La integración no está configurada en el servidor (faltan <code>GOOGLE_CLIENT_ID/SECRET</code>).
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="google-calendar-section" style={{ borderLeft: '4px solid #4285F4' }}>
      <CardHeader>
        <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Calendar className="w-5 h-5" style={{ color: '#4285F4' }} />
          Google Calendar
          {status.connected ? (
            <span
              data-testid="gcal-status-connected"
              style={{
                padding: '2px 10px', background: '#16a34a', color: '#fff',
                borderRadius: 999, fontSize: 11, fontWeight: 700,
                display: 'inline-flex', alignItems: 'center', gap: 4,
              }}
            >
              <CheckCircle2 className="w-3 h-3" /> Conectado
            </span>
          ) : (
            <span
              data-testid="gcal-status-disconnected"
              style={{
                padding: '2px 10px', background: '#e5e7eb', color: '#374151',
                borderRadius: 999, fontSize: 11, fontWeight: 600,
                display: 'inline-flex', alignItems: 'center', gap: 4,
              }}
            >
              <XCircle className="w-3 h-3" /> No conectado
            </span>
          )}
        </CardTitle>
      </CardHeader>

      <CardContent>
        {!status.connected && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.5 }}>
              Conectá tu calendario de Google para que cada cita agendada por WhatsApp
              aparezca automáticamente en tu agenda, con recordatorios y un invite al
              cliente.
            </div>
            <Button
              onClick={handleConnect}
              disabled={loading}
              data-testid="gcal-connect-btn"
              style={{
                background: '#4285F4', color: '#fff', border: 'none',
                alignSelf: 'flex-start',
              }}
            >
              <Calendar className="w-4 h-4 mr-2" />
              {loading ? 'Redirigiendo…' : 'Conectar Google Calendar'}
            </Button>
          </div>
        )}

        {status.connected && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              flexWrap: 'wrap', gap: 8,
            }}>
              <div style={{ fontSize: 13, color: '#374151' }}>
                Cuenta: <strong data-testid="gcal-connected-email">{status.connected_email || '—'}</strong>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <Button size="sm" variant="outline" onClick={fetchEvents} data-testid="gcal-refresh-btn">
                  <RefreshCw className={`w-3 h-3 mr-1 ${loadingEvents ? 'animate-spin' : ''}`} />
                  Refrescar
                </Button>
                <Button size="sm" variant="outline" onClick={handleDisconnect} data-testid="gcal-disconnect-btn">
                  <Unlink className="w-3 h-3 mr-1" />
                  Desconectar
                </Button>
              </div>
            </div>

            <div>
              <div style={{
                fontSize: 11, fontWeight: 700, color: '#1a73e8',
                textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6,
              }}>
                Próximos eventos
              </div>
              {loadingEvents ? (
                <div style={{ fontSize: 12, color: '#6b7280' }}>Cargando…</div>
              ) : events.length === 0 ? (
                <div
                  data-testid="gcal-no-events"
                  style={{ fontSize: 12, color: '#6b7280', fontStyle: 'italic' }}
                >
                  Sin eventos próximos.
                </div>
              ) : (
                <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {events.map((ev) => (
                    <li
                      key={ev.id}
                      data-testid={`gcal-event-${ev.id}`}
                      style={{
                        padding: '8px 10px', background: '#f8fafc',
                        border: '1px solid #e2e8f0', borderRadius: 6,
                        display: 'flex', justifyContent: 'space-between', gap: 8,
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937' }}>
                          {ev.summary || '(sin título)'}
                        </div>
                        <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
                          {formatDate(ev.start)} → {formatDate(ev.end)}
                        </div>
                      </div>
                      {ev.html_link && (
                        <a
                          href={ev.html_link} target="_blank" rel="noopener noreferrer"
                          style={{ color: '#4285F4', fontSize: 11, whiteSpace: 'nowrap' }}
                        >
                          <ExternalLink className="w-3 h-3 inline" /> Abrir
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
