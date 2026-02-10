import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { RefreshCw, History, User, Calendar, FileText, Tag, Trash2, Send, Download } from 'lucide-react';

const actionIcons = {
  status_changed: <RefreshCw className="w-4 h-4" />,
  bulk_tag: <Tag className="w-4 h-4" />,
  bulk_status: <RefreshCw className="w-4 h-4" />,
  bulk_assign: <User className="w-4 h-4" />,
  bulk_delete: <Trash2 className="w-4 h-4" />,
  broadcast_sent: <Send className="w-4 h-4" />,
  report_generated: <Download className="w-4 h-4" />,
  default: <FileText className="w-4 h-4" />
};

const actionLabels = {
  status_changed: 'Cambio de Estado',
  bulk_tag: 'Tag Masivo',
  bulk_status: 'Estado Masivo',
  bulk_assign: 'Asignación Masiva',
  bulk_delete: 'Eliminación Masiva',
  broadcast_sent: 'Broadcast Enviado',
  report_generated: 'Reporte Generado'
};

const actionColors = {
  status_changed: 'bg-blue-100 text-blue-800',
  bulk_tag: 'bg-purple-100 text-purple-800',
  bulk_status: 'bg-yellow-100 text-yellow-800',
  bulk_assign: 'bg-green-100 text-green-800',
  bulk_delete: 'bg-red-100 text-red-800',
  broadcast_sent: 'bg-indigo-100 text-indigo-800',
  report_generated: 'bg-gray-100 text-gray-800'
};

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('all');

  useEffect(() => {
    fetchLogs();
  }, [filterAction]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = filterAction !== 'all' ? `?action=${filterAction}` : '';
      const response = await axios.get(`${API}/audit-log${params}`);
      setLogs(response.data);
    } catch (error) {
      console.error('Error fetching audit logs:', error);
    } finally {
      setLoading(false);
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

  const getActionIcon = (action) => {
    return actionIcons[action] || actionIcons.default;
  };

  const getActionLabel = (action) => {
    return actionLabels[action] || action;
  };

  const getActionColor = (action) => {
    return actionColors[action] || 'bg-gray-100 text-gray-800';
  };

  const formatDetails = (details) => {
    if (!details) return null;
    
    const entries = Object.entries(details).filter(([k, v]) => v !== null && v !== undefined);
    if (entries.length === 0) return null;

    return (
      <div className="audit-details">
        {entries.map(([key, value]) => (
          <span key={key} className="detail-item">
            <strong>{key}:</strong> {typeof value === 'object' ? JSON.stringify(value) : String(value)}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="page-container" data-testid="audit-log-page">
      <header className="page-header">
        <div>
          <h1><History className="inline w-8 h-8 mr-2" />Historial de Auditoría</h1>
          <p className="subtitle">Registro de todas las acciones realizadas en el sistema</p>
        </div>
        <div className="header-actions">
          <Select value={filterAction} onValueChange={setFilterAction}>
            <SelectTrigger className="w-48" data-testid="filter-action">
              <SelectValue placeholder="Filtrar por acción..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las acciones</SelectItem>
              <SelectItem value="status_changed">Cambio de Estado</SelectItem>
              <SelectItem value="bulk_tag">Tag Masivo</SelectItem>
              <SelectItem value="bulk_status">Estado Masivo</SelectItem>
              <SelectItem value="bulk_assign">Asignación Masiva</SelectItem>
              <SelectItem value="bulk_delete">Eliminación Masiva</SelectItem>
              <SelectItem value="broadcast_sent">Broadcast</SelectItem>
              <SelectItem value="report_generated">Reportes</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={fetchLogs} variant="outline" size="sm" data-testid="btn-refresh">
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Últimas {logs.length} acciones registradas</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="loading-container">Cargando historial...</div>
          ) : logs.length === 0 ? (
            <div className="empty-state">
              <History className="w-12 h-12 text-gray-400 mx-auto mb-2" />
              <p>No hay registros de auditoría</p>
            </div>
          ) : (
            <div className="audit-timeline">
              {logs.map((log, index) => (
                <div key={index} className="audit-item" data-testid={`audit-item-${index}`}>
                  <div className="audit-icon">
                    {getActionIcon(log.action)}
                  </div>
                  <div className="audit-content">
                    <div className="audit-header">
                      <Badge className={getActionColor(log.action)}>
                        {getActionLabel(log.action)}
                      </Badge>
                      <span className="audit-time">
                        <Calendar className="w-3 h-3 inline mr-1" />
                        {formatDate(log.timestamp)}
                      </span>
                    </div>
                    <div className="audit-body">
                      <span className="audit-user">
                        <User className="w-3 h-3 inline mr-1" />
                        {log.user_email}
                      </span>
                      {log.lead_phone && (
                        <span className="audit-lead">Lead: {log.lead_phone}</span>
                      )}
                    </div>
                    {formatDetails(log.details)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
