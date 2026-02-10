import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from 'sonner';
import { Send, History, Users, Filter, Clock, CheckCircle, XCircle, Info, AlertTriangle } from 'lucide-react';

export default function Broadcast() {
  const [message, setMessage] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [zoneFilter, setZoneFilter] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [sending, setSending] = useState(false);
  const [history, setHistory] = useState([]);
  const [previewCount, setPreviewCount] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  useEffect(() => {
    previewRecipients();
  }, [statusFilter, zoneFilter]);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API}/broadcast/history`);
      setHistory(response.data);
    } catch (error) {
      console.error('Error fetching broadcast history:', error);
    }
  };

  const previewRecipients = async () => {
    try {
      const filters = {};
      if (statusFilter !== 'all') filters.status = statusFilter;
      if (zoneFilter) filters.zone = { "$regex": zoneFilter, "$options": "i" };

      // Contar leads que coinciden
      const response = await axios.get(`${API}/leads`);
      let filtered = response.data;
      
      if (statusFilter !== 'all') {
        filtered = filtered.filter(l => l.status === statusFilter);
      }
      if (zoneFilter) {
        filtered = filtered.filter(l => 
          (l.zone || '').toLowerCase().includes(zoneFilter.toLowerCase())
        );
      }
      
      setPreviewCount(filtered.length);
    } catch (error) {
      console.error('Error previewing recipients:', error);
      setPreviewCount(null);
    }
  };

  const sendBroadcast = async () => {
    if (!message.trim()) {
      toast.error('Escribí un mensaje para enviar');
      return;
    }

    if (previewCount === 0) {
      toast.error('No hay destinatarios que coincidan con los filtros');
      return;
    }

    const confirmed = window.confirm(
      `¿Estás seguro de enviar este mensaje a ${previewCount} leads?`
    );
    if (!confirmed) return;

    setSending(true);
    try {
      const filters = {};
      if (statusFilter !== 'all') filters.status = statusFilter;
      if (zoneFilter) filters.zone = { "$regex": zoneFilter, "$options": "i" };

      const response = await axios.post(`${API}/broadcast`, {
        message: message,
        filters: Object.keys(filters).length > 0 ? filters : null,
        scheduled_at: scheduledAt || null
      });

      toast.success(`Broadcast enviado a ${response.data.total_recipients} leads`);
      setMessage('');
      setStatusFilter('all');
      setZoneFilter('');
      setScheduledAt('');
      fetchHistory();
    } catch (error) {
      console.error('Error sending broadcast:', error);
      toast.error('Error enviando broadcast');
    } finally {
      setSending(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="page-container" data-testid="broadcast-page">
      <header className="page-header">
        <div>
          <h1><Send className="inline w-8 h-8 mr-2" />Mensajes Broadcast</h1>
          <p className="subtitle">Envía mensajes masivos a tus leads por WhatsApp</p>
        </div>
      </header>

      {/* Nota informativa */}
      <Alert className="broadcast-info-alert" data-testid="broadcast-info">
        <Info className="h-4 w-4" />
        <AlertDescription>
          <strong>¿Cómo funciona el Broadcast?</strong>
          <ul className="broadcast-info-list">
            <li>Los mensajes se envían a través de la <strong>API de WhatsApp Business</strong> conectada a tu cuenta.</li>
            <li>Podés filtrar por estado del lead (calientes, tibios, etc.) o por zona geográfica.</li>
            <li>Los mensajes se envían de forma escalonada para cumplir con los límites de WhatsApp.</li>
            <li>Asegurate de tener configurado tu token de WhatsApp en <strong>Configuración</strong>.</li>
          </ul>
        </AlertDescription>
      </Alert>

      <div className="broadcast-grid">
        {/* Formulario de envío */}
        <Card className="broadcast-form-card">
          <CardHeader>
            <CardTitle className="text-lg">Nuevo Broadcast</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="broadcast-form">
              <div className="form-group">
                <label>Mensaje</label>
                <Textarea
                  placeholder="Escribí tu mensaje aquí... Podés usar *negrita* y _cursiva_"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={5}
                  data-testid="broadcast-message"
                />
                <small className="text-muted">{message.length}/1000 caracteres</small>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label><Filter className="w-4 h-4 inline mr-1" />Filtrar por Estado</label>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger data-testid="filter-status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos los estados</SelectItem>
                      <SelectItem value="hot">Calientes</SelectItem>
                      <SelectItem value="warm">Tibios</SelectItem>
                      <SelectItem value="cold">Fríos</SelectItem>
                      <SelectItem value="new">Nuevos</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="form-group">
                  <label>Filtrar por Zona</label>
                  <Input
                    placeholder="Ej: Palermo"
                    value={zoneFilter}
                    onChange={(e) => setZoneFilter(e.target.value)}
                    data-testid="filter-zone"
                  />
                </div>
              </div>

              <div className="form-group">
                <label><Clock className="w-4 h-4 inline mr-1" />Programar envío (opcional)</label>
                <Input
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  data-testid="scheduled-at"
                />
              </div>

              <div className="broadcast-preview">
                <Users className="w-5 h-5" />
                <span>
                  {previewCount !== null 
                    ? `${previewCount} leads recibirán este mensaje`
                    : 'Calculando destinatarios...'
                  }
                </span>
              </div>

              <Button 
                onClick={sendBroadcast} 
                disabled={sending || !message.trim() || previewCount === 0}
                className="w-full"
                data-testid="btn-send-broadcast"
              >
                {sending ? 'Enviando...' : (
                  <>
                    <Send className="w-4 h-4 mr-2" />
                    {scheduledAt ? 'Programar Envío' : 'Enviar Ahora'}
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Historial */}
        <Card className="broadcast-history-card">
          <CardHeader>
            <CardTitle className="text-lg">
              <History className="w-5 h-5 inline mr-2" />
              Historial de Broadcasts
            </CardTitle>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <div className="empty-state">
                <Send className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                <p>No hay broadcasts enviados</p>
              </div>
            ) : (
              <div className="broadcast-history-list">
                {history.map((item, index) => (
                  <div key={index} className="broadcast-history-item" data-testid={`broadcast-item-${index}`}>
                    <div className="broadcast-item-header">
                      <Badge variant={item.status === 'sent' ? 'default' : 'secondary'}>
                        {item.status === 'sent' ? (
                          <><CheckCircle className="w-3 h-3 mr-1" />Enviado</>
                        ) : (
                          <><XCircle className="w-3 h-3 mr-1" />{item.status}</>
                        )}
                      </Badge>
                      <span className="broadcast-date">{formatDate(item.sent_at)}</span>
                    </div>
                    <p className="broadcast-message-preview">
                      {item.message?.substring(0, 100)}
                      {item.message?.length > 100 && '...'}
                    </p>
                    <div className="broadcast-stats">
                      <span><Users className="w-3 h-3 inline" /> {item.recipients_count || 0} destinatarios</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
