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
import TagsManager from '../components/TagsManager';
import AILeadSummary from '../components/AILeadSummary';
import { Sparkles, Lightbulb, Copy } from 'lucide-react';

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
  
  const [savingLearned, setSavingLearned] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  useEffect(() => {
    fetchLead();
  }, [phone]);

  // Cuando carga el lead, si el último mensaje es del cliente, pedimos sugerencias
  useEffect(() => {
    if (!lead?.conversation_history?.length) return;
    const last = lead.conversation_history[lead.conversation_history.length - 1];
    if (last?.from !== 'customer' || !last?.text) {
      setSuggestions([]);
      return;
    }
    fetchSuggestions(last.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead?.conversation_history?.length, lead?.phone]);

  const fetchSuggestions = async (lastCustomerMessage) => {
    setLoadingSuggestions(true);
    try {
      const res = await axios.post(`${API}/agent-suggestions`, {
        message: lastCustomerMessage,
        lead_phone: lead?.phone || '',
      });
      setSuggestions(res.data.suggestions || []);
    } catch (err) {
      console.error('agent-suggestions error:', err);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copiado — ya podés pegarlo en WhatsApp');
  };

  /**
   * Guarda este mensaje del agente/bot como "respuesta válida" para que el bot
   * la use en el futuro cuando reciba preguntas similares.
   * Toma como pregunta el último mensaje del cliente justo antes de este.
   */
  const saveLearned = async (msgIndex) => {
    if (!lead?.conversation_history) return;
    const targetMsg = lead.conversation_history[msgIndex];
    if (!targetMsg || targetMsg.from === 'customer') return;
    // Buscar el último mensaje del cliente antes de este
    let questionMsg = null;
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (lead.conversation_history[i].from === 'customer') {
        questionMsg = lead.conversation_history[i];
        break;
      }
    }
    if (!questionMsg) {
      toast.error('No hay pregunta del cliente previa para asociar');
      return;
    }
    setSavingLearned(msgIndex);
    try {
      await axios.post(`${API}/bot-learning`, {
        question: questionMsg.text,
        answer: targetMsg.text,
        lead_phone: lead.phone,
      });
      toast.success('✅ El bot va a usar esta respuesta para preguntas similares');
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingLearned(null);
    }
  };

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
              {lead.is_urgent && (
                <div className="info-row">
                  <span className="label">Urgente:</span>
                  <Badge className="badge-hot">🚨 URGENTE</Badge>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
        
        {/* Tags del lead */}
        <Card>
          <CardHeader>
            <CardTitle>🏷️ Tags</CardTitle>
          </CardHeader>
          <CardContent>
            <TagsManager 
              leadPhone={lead.phone} 
              initialTags={lead.tags || []}
              onTagsChange={(newTags) => setLead({...lead, tags: newTags})}
            />
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

        <AILeadSummary leadPhone={lead.phone} />

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
        
        {/* Sugerencias para el asesor (basadas en últimas conversaciones) */}
        {(loadingSuggestions || suggestions.length > 0) && (
          <Card data-testid="agent-suggestions-card" style={{ borderLeft: '4px solid #f59e0b' }}>
            <CardHeader style={{ paddingBottom: 8 }}>
              <CardTitle style={{ fontSize: 15, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Lightbulb className="w-4 h-4" style={{ color: '#f59e0b' }} />
                Sugerencias para responder
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loadingSuggestions ? (
                <div style={{ fontSize: 12, color: '#6b7280' }}>Buscando respuestas similares...</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {suggestions.map((sug, i) => (
                    <div
                      key={i}
                      data-testid={`suggestion-${i}`}
                      style={{
                        padding: '10px 12px',
                        background: sug.source === 'learned' ? '#f0fdf4' : '#fffbeb',
                        border: `1px solid ${sug.source === 'learned' ? '#bbf7d0' : '#fde68a'}`,
                        borderRadius: 8,
                        fontSize: 13,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start', marginBottom: 4 }}>
                        <span style={{
                          fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                          color: sug.source === 'learned' ? '#15803d' : '#b45309',
                        }}>
                          {sug.source === 'learned' ? '🧠 Enseñado al bot' : '💬 Tu respuesta previa'}
                          <span style={{ marginLeft: 6, opacity: 0.7, fontWeight: 400 }}>· {sug.score}</span>
                          {sug.match_method === 'embedding' && (
                            <span
                              style={{
                                marginLeft: 6, padding: '1px 6px',
                                background: '#ede9fe', color: '#6d28d9',
                                borderRadius: 4, fontSize: 9, letterSpacing: 0,
                              }}
                              title="Match semántico vía embeddings (detecta paráfrasis)"
                            >
                              IA semántica
                            </span>
                          )}
                        </span>
                        <div style={{ display: 'flex', gap: 4 }}>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => copyToClipboard(sug.answer)}
                            data-testid={`copy-suggestion-${i}`}
                            style={{ padding: '2px 8px', fontSize: 11, height: 24 }}
                            title="Copiar al portapapeles"
                          >
                            <Copy className="w-3 h-3 mr-1" /> Copiar
                          </Button>
                        </div>
                      </div>
                      <div style={{ color: '#374151', whiteSpace: 'pre-wrap' }}>{sug.answer}</div>
                      <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 6, fontStyle: 'italic' }}>
                        {sug.context}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Historial de Conversación de WhatsApp */}
        <Card className="conversation-card" data-testid="conversation-history">
          <CardHeader>
            <CardTitle>💬 Conversación de WhatsApp</CardTitle>
          </CardHeader>
          <CardContent>
            {lead.conversation_history && lead.conversation_history.length > 0 ? (
              <ScrollArea className="conversation-scroll">
                <div className="conversation-messages">
                  {lead.conversation_history.map((msg, index) => (
                    <div 
                      key={index} 
                      className={`message-bubble ${msg.from === 'customer' ? 'message-incoming' : 'message-outgoing'}`}
                    >
                      <div className="message-content">
                        {msg.text}
                      </div>
                      <div className="message-time">
                        {msg.timestamp ? new Date(msg.timestamp).toLocaleString('es-AR', {
                          day: '2-digit',
                          month: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit'
                        }) : ''}
                      </div>
                      {msg.from !== 'customer' && (
                        <button
                          type="button"
                          onClick={() => saveLearned(index)}
                          disabled={savingLearned === index}
                          data-testid={`save-learned-${index}`}
                          title="Guardar esta respuesta para que el bot la use con preguntas similares"
                          style={{
                            marginTop: 6,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            background: 'transparent',
                            border: '1px dashed #94a3b8',
                            color: '#475569',
                            padding: '3px 8px',
                            borderRadius: 6,
                            fontSize: 11,
                            cursor: 'pointer',
                          }}
                        >
                          <Sparkles className="w-3 h-3" />
                          {savingLearned === index ? 'Guardando...' : 'Enseñar al bot'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <div className="notes-empty">
                No hay mensajes registrados en esta conversación.
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