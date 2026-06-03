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

const ZONAS = ['Palermo', 'Recoleta', 'Belgrano', 'Caballito', 'Núñez', 'Puerto Madero', 'San Telmo'];
const SPECS = ['comprar', 'alquilar', 'inversion', 'ambos'];

function AgentCard({ agent, agentMetrics, onEdit, onDelete, onToggle }) {
  const isOverloaded = agentMetrics?.is_overloaded;
  
  return (
    <Card className={`agent-card ${!agent.active ? 'inactive' : ''}`} data-testid={`agent-card-${agent.email}`}>
      <CardHeader>
        <div className="agent-header">
          <div>
            <CardTitle>{agent.name}</CardTitle>
            <p className="agent-email">{agent.email}</p>
          </div>
          <div className="agent-status">
            <Badge className={agent.active ? "badge-active" : ""}>{agent.active ? 'Activo' : 'Inactivo'}</Badge>
            {isOverloaded && <Badge className="badge-overloaded">Sobrecargado</Badge>}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="agent-info">
          <div className="info-row">
            <span className="label">Tel:</span>
            <span className="value">{agent.phone}</span>
          </div>
          <div className="info-row">
            <span className="label">Especialidades:</span>
            <div className="tags">
              {(agent.specialties || []).map(s => <Badge key={s} variant="outline">{s}</Badge>)}
            </div>
          </div>
          <div className="info-row">
            <span className="label">Zonas:</span>
            <div className="tags">
              {(agent.zones || []).map(z => <Badge key={z} variant="outline">{z}</Badge>)}
            </div>
          </div>
          <div className="metrics-row">
            <div className="metric">
              <span className="metric-value">{agentMetrics?.active_leads || 0}</span>
              <span className="metric-label">Activos</span>
            </div>
            <div className="metric">
              <span className="metric-value">{agentMetrics?.with_appointment || 0}</span>
              <span className="metric-label">Con Cita</span>
            </div>
            <div className="metric">
              <span className="metric-value">{agentMetrics?.conversion_rate || 0}%</span>
              <span className="metric-label">Conv.</span>
            </div>
          </div>
        </div>
        <div className="agent-actions">
          <Button variant="outline" size="sm" onClick={() => onEdit(agent)}>Editar</Button>
          <Button variant="ghost" size="sm" onClick={() => onToggle(agent)}>
            {agent.active ? 'Desactivar' : 'Activar'}
          </Button>
          <Button variant="destructive" size="sm" onClick={() => onDelete(agent.email)}>Eliminar</Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AgentManagement() {
  const { isAdmin } = useAuth();
  const [agents, setAgents] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: '', email: '', phone: '', password: '',
    specialties: [], zones: [], max_concurrent_leads: 15
  });

  useEffect(() => {
    const loadData = async () => {
      try {
        const [agentsRes, metricsRes] = await Promise.all([
          axios.get(`${API}/auth/agents`),
          axios.get(`${API}/metrics/all-agents`)
        ]);
        setAgents(Array.isArray(agentsRes.data) ? agentsRes.data : (agentsRes.data.agents || []));
        setMetrics(metricsRes.data);
      } catch (error) {
        console.error('Error:', error);
        toast.error('Error cargando datos');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleCreate = () => {
    setEditingAgent(null);
    setFormData({ name: '', email: '', phone: '', password: '', specialties: [], zones: [], max_concurrent_leads: 15 });
    setShowModal(true);
  };

  const handleEdit = (agent) => {
    setEditingAgent(agent);
    setFormData({
      name: agent.name, email: agent.email, phone: agent.phone, password: '',
      specialties: agent.specialties || [], zones: agent.zones || [],
      max_concurrent_leads: agent.max_concurrent_leads || 15
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editingAgent) {
        const data = { ...formData };
        if (!data.password) delete data.password;
        delete data.email;
        await axios.put(`${API}/auth/agents/${editingAgent.email}`, data);
        toast.success('Asesor actualizado');
      } else {
        await axios.post(`${API}/auth/register`, formData);
        toast.success('Asesor creado');
      }
      setShowModal(false);
      const res = await axios.get(`${API}/auth/agents`);
      setAgents(Array.isArray(res.data) ? res.data : (res.data.agents || []));
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (email) => {
    if (!window.confirm('¿Eliminar asesor?')) return;
    try {
      await axios.delete(`${API}/auth/agents/${email}`);
      toast.success('Eliminado');
      setAgents(agents.filter(a => a.email !== email));
    } catch (error) {
      toast.error('Error');
    }
  };

  const toggleActive = async (agent) => {
    try {
      await axios.put(`${API}/auth/agents/${agent.email}`, { active: !agent.active });
      setAgents(agents.map(a => a.email === agent.email ? { ...a, active: !a.active } : a));
    } catch (error) {
      toast.error('Error');
    }
  };

  const toggleSpec = (s) => {
    setFormData(prev => ({
      ...prev, specialties: prev.specialties.includes(s) 
        ? prev.specialties.filter(x => x !== s) : [...prev.specialties, s]
    }));
  };

  const toggleZone = (z) => {
    setFormData(prev => ({
      ...prev, zones: prev.zones.includes(z) 
        ? prev.zones.filter(x => x !== z) : [...prev.zones, z]
    }));
  };

  const getMetrics = (email) => metrics.find(m => m.email === email);

  if (!isAdmin) {
    return <div className="page-container"><div className="access-denied"><h2>Acceso Denegado</h2></div></div>;
  }

  if (loading) return <div className="loading-container">Cargando...</div>;

  const filteredAgents = agents.filter(a => a.role !== 'admin');

  return (
    <div className="page-container" data-testid="agents-page">
      <header className="page-header">
        <div>
          <h1>Gestión de Asesores</h1>
          <p className="subtitle">Administra el equipo</p>
        </div>
        <Button onClick={handleCreate} data-testid="btn-create-agent">+ Nuevo Asesor</Button>
      </header>

      <div className="agents-grid">
        {filteredAgents.map(agent => (
          <AgentCard 
            key={agent.email} 
            agent={agent} 
            agentMetrics={getMetrics(agent.email)}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onToggle={toggleActive}
          />
        ))}
        {filteredAgents.length === 0 && (
          <div className="empty-state">
            <p>No hay asesores</p>
            <Button onClick={handleCreate}>Crear asesor</Button>
          </div>
        )}
      </div>

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="agent-modal" data-testid="agent-modal">
          <DialogHeader>
            <DialogTitle>{editingAgent ? 'Editar' : 'Nuevo'} Asesor</DialogTitle>
            <DialogDescription>Completa los datos del asesor</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="agent-form">
            <div className="form-group">
              <label>Nombre *</label>
              <Input value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} required data-testid="input-agent-name" />
            </div>
            <div className="form-group">
              <label>Email *</label>
              <Input type="email" value={formData.email} onChange={e => setFormData({ ...formData, email: e.target.value })} required disabled={!!editingAgent} data-testid="input-agent-email" />
            </div>
            <div className="form-group">
              <label>Teléfono *</label>
              <Input value={formData.phone} onChange={e => setFormData({ ...formData, phone: e.target.value })} required data-testid="input-agent-phone" />
            </div>
            <div className="form-group">
              <label>{editingAgent ? 'Nueva contraseña' : 'Contraseña *'}</label>
              <Input type="password" value={formData.password} onChange={e => setFormData({ ...formData, password: e.target.value })} required={!editingAgent} data-testid="input-agent-password" />
            </div>
            <div className="form-group">
              <label>Especialidades</label>
              <div className="checkbox-group">
                {SPECS.map(s => (
                  <label key={s} className="checkbox-label">
                    <input type="checkbox" checked={formData.specialties.includes(s)} onChange={() => toggleSpec(s)} />
                    <span>{s}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="form-group">
              <label>Zonas</label>
              <div className="checkbox-group zones">
                {ZONAS.map(z => (
                  <label key={z} className="checkbox-label">
                    <input type="checkbox" checked={formData.zones.includes(z)} onChange={() => toggleZone(z)} />
                    <span>{z}</span>
                  </label>
                ))}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>Cancelar</Button>
              <Button type="submit" disabled={saving} data-testid="btn-save-agent">
                {saving ? 'Guardando...' : 'Guardar'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
