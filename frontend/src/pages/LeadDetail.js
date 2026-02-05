import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';

export default function LeadDetail() {
  const { phone } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDate, setEditDate] = useState('');
  const [editTime, setEditTime] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [saving, setSaving] = useState(false);
  
  useEffect(() => {
    fetchLead();
  }, [phone]);
  
  const fetchLead = async () => {
    try {
      const response = await axios.get(`${API}/leads/${phone}`);
      setLead(response.data);
      setEditName(response.data.name || '');
      setEditNotes(response.data.notes || '');
      
      if (response.data.appointment_datetime) {
        const date = new Date(response.data.appointment_datetime);
        const dateStr = date.toISOString().split('T')[0];
        const timeStr = date.toTimeString().slice(0, 5);
        setEditDate(dateStr);
        setEditTime(timeStr);
      }
    } catch (error) {
      console.error('Error fetching lead:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleEdit = () => {
    setShowEditModal(true);
  };
  
  const handleSaveEdit = async () => {
    setSaving(true);
    try {
      const updateData = {
        name: editName,
        notes: editNotes
      };
      
      if (editDate && editTime) {
        const appointmentDatetime = new Date(`${editDate}T${editTime}`);
        updateData.appointment_datetime = appointmentDatetime.toISOString();
      }
      
      await axios.put(`${API}/leads/${phone}`, updateData);
      toast.success('Lead actualizado exitosamente');
      setShowEditModal(false);
      fetchLead();
    } catch (error) {
      console.error('Error updating lead:', error);
      toast.error('Error actualizando lead');
    } finally {
      setSaving(false);
    }
  };
  
  const handleDelete = () => {
    setShowDeleteModal(true);
  };
  
  const confirmDelete = async () => {
    setSaving(true);
    try {
      await axios.delete(`${API}/leads/${phone}`);
      toast.success('Lead eliminado exitosamente');
      navigate('/leads');
    } catch (error) {
      console.error('Error deleting lead:', error);
      toast.error('Error eliminando lead');
      setSaving(false);
    }
  };
  
  const getStatusBadge = (status) => {
    const styles = {
      hot: 'badge-hot',
      warm: 'badge-warm',
      cold: 'badge-cold'
    };
    
    const labels = {
      hot: '🔥 Caliente',
      warm: '🟡 Tibio',
      cold: '❄️ Frío'
    };
    
    return <Badge className={styles[status]}>{labels[status] || status}</Badge>;
  };
  
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('es-AR');
  };
  
  if (loading) {
    return <div className="loading-container">Cargando...</div>;
  }
  
  if (!lead) {
    return <div className="error-container">Lead no encontrado</div>;
  }
  
  return (
    <div className="page-container" data-testid="lead-detail-page">
      <header className="page-header">
        <Button onClick={() => navigate('/leads')} variant="ghost" className="back-button">
          ← Volver
        </Button>
        <div className="header-title-group">
          <h1>{lead.name || 'Sin nombre'}</h1>
          {getStatusBadge(lead.status)}
        </div>
        <div className="header-actions">
          <Button onClick={handleEdit} variant="outline" data-testid="btn-edit-lead">
            ✏️ Editar
          </Button>
          <Button onClick={handleDelete} variant="destructive" data-testid="btn-delete-lead">
            🗑️ Eliminar
          </Button>
        </div>
      </header>
      
      <div className="lead-detail-grid">
        <Card>
          <CardHeader>
            <CardTitle>Información de Contacto</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">Teléfono:</span>
                <span className="value">{lead.phone}</span>
              </div>
              <div className="info-row">
                <span className="label">Fuente:</span>
                <span className="value">{lead.source}</span>
              </div>
              <div className="info-row">
                <span className="label">Creado:</span>
                <span className="value">{formatDate(lead.created_at)}</span>
              </div>
              <div className="info-row">
                <span className="label">Último mensaje:</span>
                <span className="value">{formatDate(lead.last_message_at)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Preferencias de Propiedad</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">Intención:</span>
                <span className="value">{lead.intent || 'No definida'}</span>
              </div>
              <div className="info-row">
                <span className="label">Zona:</span>
                <span className="value">{lead.zone || 'No especificada'}</span>
              </div>
              <div className="info-row">
                <span className="label">Presupuesto:</span>
                <span className="value">{lead.budget_text || 'No especificado'}</span>
              </div>
              <div className="info-row">
                <span className="label">Tipo de propiedad:</span>
                <span className="value">{lead.property_type || 'No especificado'}</span>
              </div>
              <div className="info-row">
                <span className="label">Dormitorios:</span>
                <span className="value">{lead.bedrooms || 'No especificado'}</span>
              </div>
              {lead.must_have && lead.must_have.length > 0 && (
                <div className="info-row">
                  <span className="label">Requisitos:</span>
                  <span className="value">{lead.must_have.join(', ')}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Urgencia y Financiamiento</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">Urgencia:</span>
                <span className="value">{lead.urgency || 'No especificada'}</span>
              </div>
              {lead.financing && (
                <div className="info-row">
                  <span className="label">Financiamiento:</span>
                  <span className="value">{lead.financing}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Scoring y Estado</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">Score:</span>
                <span className="value score-large">{lead.score}/12</span>
              </div>
              <div className="info-row">
                <span className="label">Clasificación:</span>
                <span className="value">{getStatusBadge(lead.status)}</span>
              </div>
              <div className="info-row">
                <span className="label">Estado del flujo:</span>
                <span className="value">{lead.flow_stage}</span>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {lead.appointment_datetime && (
          <Card className="appointment-card">
            <CardHeader>
              <CardTitle>📅 Cita Agendada</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="info-rows">
                <div className="info-row">
                  <span className="label">Tipo:</span>
                  <span className="value">{lead.appointment_type}</span>
                </div>
                <div className="info-row">
                  <span className="label">Fecha y hora:</span>
                  <span className="value">{formatDate(lead.appointment_datetime)}</span>
                </div>
                {lead.assigned_agent && (
                  <div className="info-row">
                    <span className="label">Asesor asignado:</span>
                    <span className="value">{lead.assigned_agent}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}
        
        <Card className="notes-card">
          <CardHeader>
            <CardTitle>📝 Notas Internas</CardTitle>
          </CardHeader>
          <CardContent>
            {lead.notes ? (
              <div className="notes-content">
                {lead.notes}
              </div>
            ) : (
              <div className="notes-empty">
                Sin notas. Click en "Editar" para agregar observaciones.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      
      <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
        <DialogContent data-testid="edit-modal">
          <DialogHeader>
            <DialogTitle>Editar Lead</DialogTitle>
            <DialogDescription>
              Modifica el nombre o fecha de cita del lead
            </DialogDescription>
          </DialogHeader>
          
          <div className="edit-form">
            <div className="form-group">
              <label>Nombre completo</label>
              <Input 
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="Nombre y apellido"
                data-testid="input-edit-name"
              />
            </div>
            
            {lead?.appointment_datetime && (
              <>
                <div className="form-group">
                  <label>Fecha de cita</label>
                  <Input 
                    type="date"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    data-testid="input-edit-date"
                  />
                </div>
                
                <div className="form-group">
                  <label>Hora de cita</label>
                  <Input 
                    type="time"
                    value={editTime}
                    onChange={(e) => setEditTime(e.target.value)}
                    data-testid="input-edit-time"
                  />
                </div>
              </>
            )}
            
            <div className="form-group">
              <label>Notas internas</label>
              <textarea 
                className="textarea-input"
                rows="4"
                placeholder="Observaciones, comentarios internos..."
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                data-testid="input-edit-notes"
              />
              <p className="help-text">Estas notas solo son visibles para el equipo interno</p>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditModal(false)}>
              Cancelar
            </Button>
            <Button onClick={handleSaveEdit} disabled={saving} data-testid="btn-save-edit">
              {saving ? 'Guardando...' : 'Guardar Cambios'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <DialogContent data-testid="delete-modal">
          <DialogHeader>
            <DialogTitle>¿Eliminar Lead?</DialogTitle>
            <DialogDescription>
              Esta acción no se puede deshacer. El lead será eliminado permanentemente de la base de datos.
            </DialogDescription>
          </DialogHeader>
          
          <div className="delete-warning">
            <p><strong>Lead a eliminar:</strong></p>
            <p>{lead?.name || 'Sin nombre'}</p>
            <p>{lead?.phone}</p>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteModal(false)}>
              Cancelar
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={saving} data-testid="btn-confirm-delete">
              {saving ? 'Eliminando...' : 'Sí, Eliminar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}