import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';

const ZONAS_DISPONIBLES = ['Palermo', 'Recoleta', 'Belgrano', 'Caballito', 'Núñez', 'Puerto Madero', 'San Telmo', 'Microcentro'];
const ESPECIALIDADES = ['comprar', 'alquilar', 'inversion', 'ambos'];

export default function AgentManagement() {
  const { isAdmin } = useAuth();
  const [agents, setAgents] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    password: '',
    specialties: [],
    zones: [],
    max_concurrent_leads: 15
  });

  useEffect(() => {
    fetchAgents();
    fetchMetrics();
  }, []);

  const fetchAgents = async () => {
    try {
      const response = await axios.get(`${API}/auth/agents`);
      setAgents(response.data);
    } catch (error) {
      console.error('Error fetching agents:', error);
      toast.error('Error cargando asesores');
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await axios.get(`${API}/metrics/all-agents`);
      setMetrics(response.data);
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
  };

  const handleCreate = () => {
    setEditingAgent(null);
    setFormData({
      name: '',
      email: '',
      phone: '',
      password: '',
      specialties: [],
      zones: [],
      max_concurrent_leads: 15
    });
    setShowModal(true);
  };

  const handleEdit = (agent) => {
    setEditingAgent(agent);
    setFormData({
      name: agent.name,
      email: agent.email,
      phone: agent.phone,
      password: '',
      specialties: agent.specialties || [],
      zones: agent.zones || [],
      max_concurrent_leads: agent.max_concurrent_leads || 15
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      if (editingAgent) {
        // Actualizar
        const updateData = { ...formData };
        if (!updateData.password) delete updateData.password;
        delete updateData.email; // No se puede cambiar email
        
        await axios.put(`${API}/auth/agents/${editingAgent.email}`, updateData);
        toast.success('Asesor actualizado');
      } else {
        // Crear nuevo
        await axios.post(`${API}/auth/register`, formData);
        toast.success('Asesor creado exitosamente');
      }
      
      setShowModal(false);
      fetchAgents();
      fetchMetrics();
    } catch (error) {
      console.error('Error saving agent:', error);
      toast.error(error.response?.data?.detail || 'Error guardando asesor');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (email) => {
    if (!window.confirm('¿Estás seguro de eliminar este asesor?')) return;

    try {
      await axios.delete(`${API}/auth/agents/${email}`);
      toast.success('Asesor eliminado');
      fetchAgents();
    } catch (error) {
      console.error('Error deleting agent:', error);
      toast.error('Error eliminando asesor');
    }
  };

  const toggleActive = async (agent) => {
    try {
      await axios.put(`${API}/auth/agents/${agent.email}`, {
        active: !agent.active
      });
      toast.success(agent.active ? 'Asesor desactivado' : 'Asesor activado');
      fetchAgents();
    } catch (error) {
      toast.error('Error actualizando estado');
    }
  };

  const toggleSpecialty = (specialty) => {
    setFormData(prev => ({
      ...prev,
      specialties: prev.specialties.includes(specialty)
        ? prev.specialties.filter(s => s !== specialty)
        : [...prev.specialties, specialty]
    }));
  };

  const toggleZone = (zone) => {
    setFormData(prev => ({
      ...prev,
      zones: prev.zones.includes(zone)
        ? prev.zones.filter(z => z !== zone)
        : [...prev.zones, zone]
    }));
  };

  const getAgentMetrics = (email) => {
    return metrics.find(m => m.email === email) || {};
  };

  if (!isAdmin) {
    return (
      <div className="page-container">
        <div className="access-denied">
          <h2>Acceso Denegado</h2>
          <p>Solo los administradores pueden acceder a esta sección.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return <div className="loading-container">Cargando asesores...</div>;
  }

  return (
    <div className="page-container" data-testid="agents-page">
      <header className="page-header">
        <div>
          <h1>Gestión de Asesores</h1>
          <p className="subtitle">Administra el equipo y asigna zonas/especialidades</p>
        </div>
        <Button onClick={handleCreate} data-testid="btn-create-agent">
          + Nuevo Asesor
        </Button>
      </header>

      <div className="agents-grid">
        {agents.filter(a => a.role !== 'admin').map(agent => {
          const agentMetrics = getAgentMetrics(agent.email);
          const isOverloaded = agentMetrics.is_overloaded;

          return (
            <Card key={agent.email} className={`agent-card ${!agent.active ? 'inactive' : ''}`} data-testid={`agent-card-${agent.email}`}>
              <CardHeader>
                <div className="agent-header">
                  <div>
                    <CardTitle>{agent.name}</CardTitle>
                    <p className="agent-email">{agent.email}</p>
                  </div>
                  <div className="agent-status">
                    {agent.active ? (
                      <Badge className="badge-active">Activo</Badge>
                    ) : (
                      <Badge variant="secondary">Inactivo</Badge>
                    )}
                    {isOverloaded && <Badge className="badge-overloaded">⚠️ Sobrecargado</Badge>}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="agent-info">
                  <div className="info-row">
                    <span className="label">Teléfono:</span>
                    <span className="value">{agent.phone}</span>
                  </div>
                  
                  <div className="info-row">
                    <span className="label">Especialidades:</span>
                    <div className="tags">
                      {(agent.specialties || []).length > 0 ? (
                        agent.specialties.map(s => (
                          <Badge key={s} variant="outline">{s}</Badge>
                        ))
                      ) : (
                        <span className="no-data">Sin definir</span>
                      )}
                    </div>
                  </div>

                  <div className="info-row">
                    <span className="label">Zonas:</span>
                    <div className="tags">
                      {(agent.zones || []).length > 0 ? (
                        agent.zones.map(z => (
                          <Badge key={z} variant="outline">{z}</Badge>
                        ))
                      ) : (
                        <span className="no-data">Todas</span>
                      )}
                    </div>
                  </div>

                  <div className="metrics-row">
                    <div className="metric">
                      <span className="metric-value">{agentMetrics.active_leads || 0}</span>
                      <span className="metric-label">Leads Activos</span>
                    </div>
                    <div className="metric">
                      <span className="metric-value">{agentMetrics.with_appointment || 0}</span>
                      <span className="metric-label">Con Cita</span>
                    </div>
                    <div className="metric">
                      <span className="metric-value">{agentMetrics.conversion_rate || 0}%</span>
                      <span className="metric-label">Conversión</span>
                    </div>
                  </div>
                </div>

                <div className="agent-actions">
                  <Button variant="outline" size="sm" onClick={() => handleEdit(agent)} data-testid={`btn-edit-${agent.email}`}>
                    ✏️ Editar
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => toggleActive(agent)}>
                    {agent.active ? '🔴 Desactivar' : '🟢 Activar'}
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => handleDelete(agent.email)} data-testid={`btn-delete-${agent.email}`}>
                    🗑️
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}

        {agents.filter(a => a.role !== 'admin').length === 0 && (
          <div className="empty-state">
            <p>No hay asesores registrados</p>
            <Button onClick={handleCreate}>Crear primer asesor</Button>
          </div>
        )}
      </div>

      {/* Modal crear/editar */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="agent-modal" data-testid="agent-modal">
          <DialogHeader>
            <DialogTitle>{editingAgent ? 'Editar Asesor' : 'Nuevo Asesor'}</DialogTitle>
            <DialogDescription>
              {editingAgent ? 'Modifica los datos del asesor' : 'Completa los datos para crear un nuevo asesor'}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="agent-form">
            <div className="form-group">
              <label>Nombre completo *</label>
              <Input
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
                placeholder="Nombre y apellido"
                required
                data-testid="input-agent-name"
              />
            </div>

            <div className="form-group">
              <label>Email *</label>
              <Input
                type="email"
                value={formData.email}
                onChange={e => setFormData({ ...formData, email: e.target.value })}
                placeholder="email@ejemplo.com"
                required
                disabled={!!editingAgent}
                data-testid="input-agent-email"
              />
            </div>

            <div className="form-group">
              <label>Teléfono *</label>
              <Input
                value={formData.phone}
                onChange={e => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+5491123456789"
                required
                data-testid="input-agent-phone"
              />
            </div>

            <div className="form-group">
              <label>{editingAgent ? 'Nueva contraseña (dejar vacío para mantener)' : 'Contraseña *'}</label>
              <Input
                type="password"
                value={formData.password}
                onChange={e => setFormData({ ...formData, password: e.target.value })}
                placeholder="••••••••"
                required={!editingAgent}
                data-testid="input-agent-password"
              />
            </div>

            <div className="form-group">
              <label>Máximo de leads concurrentes</label>
              <Input
                type="number"
                min="1"
                max="50"
                value={formData.max_concurrent_leads}
                onChange={e => setFormData({ ...formData, max_concurrent_leads: parseInt(e.target.value) || 15 })}
                data-testid="input-max-leads"
              />
            </div>

            <div className="form-group">
              <label>Especialidades</label>
              <div className="checkbox-group">
                {ESPECIALIDADES.map(spec => (
                  <label key={spec} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.specialties.includes(spec)}
                      onChange={() => toggleSpecialty(spec)}
                    />
                    <span>{spec.charAt(0).toUpperCase() + spec.slice(1)}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label>Zonas asignadas</label>
              <div className="checkbox-group zones">
                {ZONAS_DISPONIBLES.map(zone => (
                  <label key={zone} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.zones.includes(zone)}
                      onChange={() => toggleZone(zone)}
                    />
                    <span>{zone}</span>
                  </label>
                ))}
              </div>
              <p className="help-text">Si no seleccionas ninguna zona, el asesor recibirá leads de todas las zonas.</p>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={saving} data-testid="btn-save-agent">
                {saving ? 'Guardando...' : (editingAgent ? 'Actualizar' : 'Crear Asesor')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
