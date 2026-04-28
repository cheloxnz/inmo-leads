import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useAuth } from '../context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Building2, Users, MessageSquare, Plus, Search, 
  ChevronDown, ChevronUp, Power, PowerOff, Settings,
  Globe, CreditCard, Activity, DollarSign, TrendingDown, Zap
} from 'lucide-react';

export default function SuperAdminPanel() {
  const { isSuperAdmin } = useAuth();
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [expandedTenant, setExpandedTenant] = useState(null);
  const [search, setSearch] = useState('');
  const [templates, setTemplates] = useState([]);
  const [globalMetrics, setGlobalMetrics] = useState(null);

  const fetchTenants = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/auth/tenants`);
      setTenants(res.data);
    } catch (err) {
      console.error('Error fetching tenants:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/templates`);
      setTemplates(res.data);
    } catch (err) {
      console.error('Error fetching templates:', err);
    }
  }, []);

  const fetchGlobalMetrics = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/superadmin/metrics`);
      setGlobalMetrics(res.data);
    } catch (err) {
      console.error('Error fetching global metrics:', err);
    }
  }, []);

  useEffect(() => {
    fetchTenants();
    fetchTemplates();
    fetchGlobalMetrics();
  }, [fetchTenants, fetchTemplates, fetchGlobalMetrics]);

  if (!isSuperAdmin) {
    return <div className="sa-denied" data-testid="sa-denied">Acceso denegado</div>;
  }

  const filteredTenants = tenants.filter(t => 
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.tenant_id.toLowerCase().includes(search.toLowerCase()) ||
    t.contact_email?.toLowerCase().includes(search.toLowerCase())
  );

  const activeTenants = tenants.filter(t => t.active);
  const totalLeads = tenants.reduce((sum, t) => sum + (t.leads_count || 0), 0);
  const totalAgents = tenants.reduce((sum, t) => sum + (t.agents_count || 0), 0);

  return (
    <div className="sa-panel" data-testid="superadmin-panel">
      <div className="sa-header">
        <h1>Panel SuperAdmin</h1>
        <p>Gestion de clientes (tenants)</p>
      </div>

      {/* Global SaaS Metrics */}
      {globalMetrics && (
        <div className="sa-global-metrics" data-testid="sa-global-metrics">
          <Card className="sa-global-card sa-mrr">
            <CardContent>
              <DollarSign className="sa-global-icon" />
              <div className="sa-global-value" data-testid="sa-mrr">${globalMetrics.mrr || 0}</div>
              <div className="sa-global-label">MRR</div>
              <div className="sa-global-sub">ARR ~${globalMetrics.arr_estimated || 0}</div>
            </CardContent>
          </Card>
          <Card className="sa-global-card">
            <CardContent>
              <Building2 className="sa-global-icon" />
              <div className="sa-global-value">{globalMetrics.tenants?.active || 0}</div>
              <div className="sa-global-label">Activos</div>
              <div className="sa-global-sub">{globalMetrics.tenants?.past_due || 0} morosos</div>
            </CardContent>
          </Card>
          <Card className="sa-global-card">
            <CardContent>
              <TrendingDown className="sa-global-icon" />
              <div className="sa-global-value">{globalMetrics.tenants?.churn_rate_pct || 0}%</div>
              <div className="sa-global-label">Churn 30d</div>
              <div className="sa-global-sub">{globalMetrics.tenants?.churned_last_30d || 0} cancelados</div>
            </CardContent>
          </Card>
          <Card className="sa-global-card">
            <CardContent>
              <Zap className="sa-global-icon" />
              <div className="sa-global-value">{globalMetrics.usage?.total_overage_messages || 0}</div>
              <div className="sa-global-label">Overage IA</div>
              <div className="sa-global-sub">{globalMetrics.usage?.total_ai_messages || 0} totales</div>
            </CardContent>
          </Card>
          <Card className="sa-global-card">
            <CardContent>
              <DollarSign className="sa-global-icon" />
              <div className="sa-global-value">${globalMetrics.revenue_last_30d?.total || 0}</div>
              <div className="sa-global-label">Revenue 30d</div>
              <div className="sa-global-sub">{globalMetrics.leads?.new_last_30d || 0} leads nuevos</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Stats */}
      <div className="sa-stats">
        <Card className="sa-stat-card">
          <CardContent className="sa-stat-content">
            <Building2 className="sa-stat-icon" />
            <div>
              <div className="sa-stat-number" data-testid="sa-total-tenants">{activeTenants.length}</div>
              <div className="sa-stat-label">Clientes activos</div>
            </div>
          </CardContent>
        </Card>
        <Card className="sa-stat-card">
          <CardContent className="sa-stat-content">
            <MessageSquare className="sa-stat-icon" />
            <div>
              <div className="sa-stat-number" data-testid="sa-total-leads">{totalLeads}</div>
              <div className="sa-stat-label">Leads totales</div>
            </div>
          </CardContent>
        </Card>
        <Card className="sa-stat-card">
          <CardContent className="sa-stat-content">
            <Users className="sa-stat-icon" />
            <div>
              <div className="sa-stat-number" data-testid="sa-total-agents">{totalAgents}</div>
              <div className="sa-stat-label">Agentes totales</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Toolbar */}
      <div className="sa-toolbar">
        <div className="sa-search">
          <Search className="w-4 h-4" />
          <input 
            placeholder="Buscar cliente..." 
            value={search} 
            onChange={e => setSearch(e.target.value)}
            data-testid="sa-search"
          />
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} data-testid="sa-btn-create">
          <Plus className="w-4 h-4 mr-2" />
          Nuevo Cliente
        </Button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <CreateTenantForm 
          templates={templates}
          onCreated={() => { setShowCreate(false); fetchTenants(); }} 
          onCancel={() => setShowCreate(false)}
        />
      )}

      {/* Tenant List */}
      <div className="sa-tenant-list">
        {loading ? (
          <div className="sa-loading">Cargando clientes...</div>
        ) : filteredTenants.length === 0 ? (
          <div className="sa-empty">
            {search ? 'No se encontraron resultados' : 'No hay clientes. Crea el primero.'}
          </div>
        ) : (
          filteredTenants.map(tenant => (
            <TenantCard 
              key={tenant.tenant_id} 
              tenant={tenant}
              expanded={expandedTenant === tenant.tenant_id}
              onToggle={() => setExpandedTenant(
                expandedTenant === tenant.tenant_id ? null : tenant.tenant_id
              )}
              onUpdate={fetchTenants}
            />
          ))
        )}
      </div>
    </div>
  );
}


function TenantCard({ tenant, expanded, onToggle, onUpdate }) {
  const [updating, setUpdating] = useState(false);

  const toggleActive = async () => {
    setUpdating(true);
    try {
      if (tenant.active) {
        await axios.delete(`${API}/auth/tenants/${tenant.tenant_id}`);
      } else {
        await axios.put(`${API}/auth/tenants/${tenant.tenant_id}`, { 
          active: true, subscription_status: 'active' 
        });
      }
      onUpdate();
    } catch (err) {
      alert('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUpdating(false);
    }
  };

  return (
    <Card className={`sa-tenant-card ${!tenant.active ? 'inactive' : ''}`} data-testid={`tenant-${tenant.tenant_id}`}>
      <div className="sa-tenant-row" onClick={onToggle}>
        <div className="sa-tenant-main">
          <div className={`sa-tenant-status ${tenant.active ? 'active' : 'inactive'}`} />
          <div>
            <div className="sa-tenant-name">{tenant.name}</div>
            <div className="sa-tenant-id">{tenant.tenant_id} &middot; {tenant.contact_email}</div>
          </div>
        </div>
        <div className="sa-tenant-badges">
          <span className="sa-badge plan">{tenant.plan || 'basic'}</span>
          <span className="sa-badge template">{tenant.template_id || 'servicios'}</span>
          <span className="sa-badge">{tenant.country || '-'}</span>
          <span className="sa-badge leads">{tenant.leads_count || 0} leads</span>
          <span className="sa-badge agents">{tenant.agents_count || 0} agentes</span>
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </div>

      {expanded && (
        <div className="sa-tenant-detail">
          <div className="sa-detail-grid">
            <div className="sa-detail-item">
              <Globe className="w-4 h-4" />
              <span>Pais: {tenant.country || 'No definido'}</span>
            </div>
            <div className="sa-detail-item">
              <Settings className="w-4 h-4" />
              <span>Template: {tenant.template_id || 'servicios'}</span>
            </div>
            <div className="sa-detail-item">
              <CreditCard className="w-4 h-4" />
              <span>Suscripcion: {tenant.subscription_status || 'active'}</span>
            </div>
            <div className="sa-detail-item">
              <Activity className="w-4 h-4" />
              <span>WhatsApp: {tenant.whatsapp_phone_number_id ? 'Configurado' : 'Pendiente'}</span>
            </div>
            <div className="sa-detail-item">
              <MessageSquare className="w-4 h-4" />
              <span>Max leads: {tenant.max_leads || 500}</span>
            </div>
            <div className="sa-detail-item">
              <Users className="w-4 h-4" />
              <span>Max agentes: {tenant.max_agents || 5}</span>
            </div>
          </div>
          <div className="sa-detail-actions">
            <Button 
              size="sm" 
              variant={tenant.active ? "destructive" : "default"}
              onClick={toggleActive} 
              disabled={updating}
              data-testid={`toggle-${tenant.tenant_id}`}
            >
              {tenant.active ? <PowerOff className="w-3 h-3 mr-1" /> : <Power className="w-3 h-3 mr-1" />}
              {tenant.active ? 'Desactivar' : 'Reactivar'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}


function CreateTenantForm({ templates, onCreated, onCancel }) {
  const [form, setForm] = useState({
    tenant_id: '', name: '', contact_email: '', contact_phone: '',
    country: '', plan: 'basic', template_id: 'servicios',
    admin_email: '', admin_password: '', admin_name: 'Administrador'
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
    if (field === 'name' && !form.tenant_id) {
      setForm(prev => ({ 
        ...prev, 
        [field]: value,
        tenant_id: value.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-')
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      await axios.post(`${API}/auth/tenants`, form);
      // Set template
      await axios.put(`${API}/auth/tenants/${form.tenant_id}`, { 
        template_id: form.template_id 
      });
      onCreated();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al crear cliente');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="sa-create-form" data-testid="sa-create-form">
      <CardHeader>
        <CardTitle>Nuevo Cliente</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          {error && <div className="sa-form-error">{error}</div>}

          <div className="sa-form-section">
            <h4>Datos del negocio</h4>
            <div className="sa-form-grid">
              <div className="sa-form-field">
                <label>Nombre del negocio *</label>
                <input value={form.name} onChange={e => handleChange('name', e.target.value)} required data-testid="input-tenant-name" />
              </div>
              <div className="sa-form-field">
                <label>ID (slug) *</label>
                <input value={form.tenant_id} onChange={e => setForm({...form, tenant_id: e.target.value})} required data-testid="input-tenant-id" />
              </div>
              <div className="sa-form-field">
                <label>Email de contacto *</label>
                <input type="email" value={form.contact_email} onChange={e => setForm({...form, contact_email: e.target.value})} required data-testid="input-tenant-email" />
              </div>
              <div className="sa-form-field">
                <label>Telefono</label>
                <input value={form.contact_phone} onChange={e => setForm({...form, contact_phone: e.target.value})} data-testid="input-tenant-phone" />
              </div>
              <div className="sa-form-field">
                <label>Pais</label>
                <select value={form.country} onChange={e => setForm({...form, country: e.target.value})} data-testid="select-country">
                  <option value="">Seleccionar</option>
                  <option value="AR">Argentina</option>
                  <option value="UY">Uruguay</option>
                  <option value="PY">Paraguay</option>
                  <option value="MX">Mexico</option>
                  <option value="CO">Colombia</option>
                  <option value="CL">Chile</option>
                  <option value="PE">Peru</option>
                  <option value="ES">Espana</option>
                </select>
              </div>
              <div className="sa-form-field">
                <label>Rubro (template) *</label>
                <select value={form.template_id} onChange={e => setForm({...form, template_id: e.target.value})} required data-testid="select-template">
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="sa-form-section">
            <h4>Cuenta admin del cliente</h4>
            <div className="sa-form-grid">
              <div className="sa-form-field">
                <label>Nombre del admin</label>
                <input value={form.admin_name} onChange={e => setForm({...form, admin_name: e.target.value})} data-testid="input-admin-name" />
              </div>
              <div className="sa-form-field">
                <label>Email del admin *</label>
                <input type="email" value={form.admin_email} onChange={e => setForm({...form, admin_email: e.target.value})} required data-testid="input-admin-email" />
              </div>
              <div className="sa-form-field">
                <label>Password del admin *</label>
                <input type="password" value={form.admin_password} onChange={e => setForm({...form, admin_password: e.target.value})} required minLength={6} data-testid="input-admin-password" />
              </div>
              <div className="sa-form-field">
                <label>Plan</label>
                <select value={form.plan} onChange={e => setForm({...form, plan: e.target.value})} data-testid="select-plan">
                  <option value="basic">Basic</option>
                  <option value="pro">Pro</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
            </div>
          </div>

          <div className="sa-form-actions">
            <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
            <Button type="submit" disabled={submitting} data-testid="btn-submit-tenant">
              {submitting ? 'Creando...' : 'Crear Cliente'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
