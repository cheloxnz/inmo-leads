import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { 
  User, MapPin, DollarSign, Calendar, Tag, 
  GripVertical, ArrowRight, Phone, Download
} from 'lucide-react';

const statusColors = {
  new: { bg: '#e0f2fe', border: '#0ea5e9', text: '#0369a1' },
  contacted: { bg: '#fef3c7', border: '#f59e0b', text: '#b45309' },
  qualified: { bg: '#dbeafe', border: '#3b82f6', text: '#1d4ed8' },
  appointment: { bg: '#f3e8ff', border: '#a855f7', text: '#7c3aed' },
  hot: { bg: '#fee2e2', border: '#ef4444', text: '#dc2626' },
  warm: { bg: '#fef3c7', border: '#f59e0b', text: '#b45309' },
  cold: { bg: '#e0f7fa', border: '#06b6d4', text: '#0891b2' },
  completed: { bg: '#dcfce7', border: '#22c55e', text: '#16a34a' }
};

export default function KanbanView() {
  const [columns, setColumns] = useState({});
  const [loading, setLoading] = useState(true);
  const [draggedLead, setDraggedLead] = useState(null);
  const [dragOverColumn, setDragOverColumn] = useState(null);

  useEffect(() => {
    fetchKanbanData();
  }, []);

  const fetchKanbanData = async () => {
    try {
      const response = await axios.get(`${API}/leads/kanban`);
      setColumns(response.data);
    } catch (error) {
      console.error('Error fetching kanban data:', error);
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const [exporting, setExporting] = useState(false);
  const exportToCSV = async () => {
    setExporting(true);
    try {
      const response = await axios.get(`${API}/leads/export`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
      a.download = `leads_${ts}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      const totalRows = response.headers?.['x-total-rows'] || '?';
      toast.success(`CSV exportado: ${totalRows} leads`);
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Error exportando CSV');
    } finally {
      setExporting(false);
    }
  };

  const handleDragStart = (e, lead, sourceColumn) => {
    setDraggedLead({ lead, sourceColumn });
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, columnId) => {
    e.preventDefault();
    setDragOverColumn(columnId);
  };

  const handleDragLeave = () => {
    setDragOverColumn(null);
  };

  const handleDrop = async (e, targetColumn) => {
    e.preventDefault();
    setDragOverColumn(null);

    if (!draggedLead || draggedLead.sourceColumn === targetColumn) {
      setDraggedLead(null);
      return;
    }

    try {
      await axios.put(`${API}/leads/${draggedLead.lead.phone}/status`, null, {
        params: { new_status: targetColumn }
      });

      // Actualizar estado local
      const newColumns = { ...columns };
      
      // Remover del origen
      newColumns[draggedLead.sourceColumn].leads = newColumns[draggedLead.sourceColumn].leads.filter(
        l => l.phone !== draggedLead.lead.phone
      );
      newColumns[draggedLead.sourceColumn].count--;

      // Agregar al destino
      newColumns[targetColumn].leads.unshift(draggedLead.lead);
      newColumns[targetColumn].count++;

      setColumns(newColumns);
      toast.success('Lead actualizado');
    } catch (error) {
      console.error('Error updating lead status:', error);
      toast.error('Error al mover lead');
    }

    setDraggedLead(null);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' });
  };

  if (loading) {
    return <div className="loading-container">Cargando Kanban...</div>;
  }

  return (
    <div className="kanban-container" data-testid="kanban-view">
      <div className="kanban-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1>Pipeline de Leads</h1>
          <p>Arrastrá y soltá los leads para cambiar su estado</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={exportToCSV}
          disabled={exporting}
          data-testid="kanban-export-csv-btn"
          style={{ marginTop: 4 }}
        >
          <Download className="w-4 h-4 mr-2" />
          {exporting ? 'Exportando...' : 'Exportar CSV'}
        </Button>
      </div>

      <div className="kanban-board">
        {Object.entries(columns).map(([columnId, column]) => (
          <div
            key={columnId}
            className={`kanban-column ${dragOverColumn === columnId ? 'drag-over' : ''}`}
            onDragOver={(e) => handleDragOver(e, columnId)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, columnId)}
            style={{ 
              borderTopColor: statusColors[columnId]?.border || '#e2e8f0'
            }}
          >
            <div className="kanban-column-header">
              <h3 style={{ color: statusColors[columnId]?.text }}>
                {column.title}
              </h3>
              <Badge 
                variant="secondary"
                style={{ 
                  backgroundColor: statusColors[columnId]?.bg,
                  color: statusColors[columnId]?.text
                }}
              >
                {column.count}
              </Badge>
            </div>

            <div className="kanban-column-content">
              {column.leads.map((lead) => (
                <div
                  key={lead.phone}
                  className="kanban-card"
                  draggable
                  onDragStart={(e) => handleDragStart(e, lead, columnId)}
                  style={{
                    borderLeftColor: statusColors[columnId]?.border
                  }}
                >
                  <div className="kanban-card-header">
                    <GripVertical className="drag-handle" />
                    <span className="lead-name">{lead.name || 'Sin nombre'}</span>
                    {lead.score >= 8 && <span className="hot-badge">🔥</span>}
                  </div>
                  
                  <div className="kanban-card-body">
                    {lead.zone && (
                      <div className="kanban-card-row">
                        <MapPin className="w-3 h-3" />
                        <span>{lead.zone}</span>
                      </div>
                    )}
                    {lead.budget_text && (
                      <div className="kanban-card-row">
                        <DollarSign className="w-3 h-3" />
                        <span>{lead.budget_text}</span>
                      </div>
                    )}
                    {lead.appointment_datetime && (
                      <div className="kanban-card-row">
                        <Calendar className="w-3 h-3" />
                        <span>{formatDate(lead.appointment_datetime)}</span>
                      </div>
                    )}
                  </div>

                  {lead.tags && lead.tags.length > 0 && (
                    <div className="kanban-card-tags">
                      {lead.tags.slice(0, 2).map((tag, idx) => (
                        <Badge key={idx} variant="outline" className="tag-badge">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <div className="kanban-card-footer">
                    <a href={`/leads/${lead.phone}`} className="view-link">
                      Ver detalle <ArrowRight className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}

              {column.leads.length === 0 && (
                <div className="kanban-empty">
                  <span>Sin leads</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
