import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useAuth } from '../context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Building2, Users, MessageSquare, Plus, Search, 
  ChevronDown, ChevronUp, Power, PowerOff, Settings,
  Globe, CreditCard, Activity, DollarSign, TrendingDown, Zap, Flag, Trash2, Sparkles
} from 'lucide-react';
import TenantFeatureFlags from '../components/TenantFeatureFlags';
import FounderSeatsPanel from '../components/FounderSeatsPanel';
import UnmetDemandPanel from '../components/UnmetDemandPanel';
import UpsellHistoryPanel from '../components/UpsellHistoryPanel';

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

      {/* Founder Seats management */}
      <div style={{ marginTop: 24, marginBottom: 24 }}>
        <FounderSeatsPanel />
      </div>

      {/* Demanda Insatisfecha cross-tenant */}
      <div style={{ marginBottom: 24 }}>
        <UnmetDemandPanel />
      </div>

      {/* Upsell History + Conversion tracking */}
      <div style={{ marginBottom: 24 }}>
        <UpsellHistoryPanel />
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


function formatTimeAgo(iso) {
  if (!iso) return '';
  try {
    const then = new Date(iso);
    const diffMs = Date.now() - then.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'recién';
    if (mins < 60) return `hace ${mins} min`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `hace ${hrs}h`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `hace ${days}d`;
    return then.toLocaleDateString('es');
  } catch {
    return '';
  }
}

function WhatsAppHealthBadge({ tenant, mini = false }) {
  const check = tenant.whatsapp_last_check;
  const hasCreds = !!tenant.whatsapp_phone_number_id;

  // Sin credenciales aún
  if (!check && !hasCreds) {
    return (
      <span
        className="sa-badge"
        style={{ background: '#f1f5f9', color: '#64748b', fontSize: 11 }}
        data-testid={`wa-health-${tenant.tenant_id}`}
        title="WhatsApp no configurado"
      >
        WA: —
      </span>
    );
  }

  // Tiene creds pero nunca corrió el check
  if (!check) {
    return (
      <span
        className="sa-badge"
        style={{ background: '#fef3c7', color: '#b45309', fontSize: 11 }}
        data-testid={`wa-health-${tenant.tenant_id}`}
        title="WhatsApp configurado pero sin test ejecutado"
      >
        WA: sin test
      </span>
    );
  }

  // Resultado conocido
  const ok = check.ok;
  const status = check.status;
  const quality = (check.details?.quality_rating || '').toUpperCase();

  let bg = '#fee2e2';
  let color = '#b91c1c';
  let label = 'WA: error';
  let icon = '✕';

  if (ok && status === 'connected') {
    if (quality === 'GREEN') {
      bg = '#dcfce7'; color = '#15803d'; label = 'WA: ✓ GREEN'; icon = '✓';
    } else if (quality === 'YELLOW') {
      bg = '#fef3c7'; color = '#b45309'; label = 'WA: ✓ YELLOW'; icon = '⚠';
    } else {
      bg = '#dcfce7'; color = '#15803d'; label = 'WA: conectado'; icon = '✓';
    }
  } else if (status === 'unverified_number') {
    bg = '#fef3c7'; color = '#b45309'; label = 'WA: sin verificar'; icon = '⚠';
  } else if (status === 'low_quality') {
    bg = '#fee2e2'; color = '#b91c1c'; label = 'WA: RED'; icon = '⚠';
  } else if (status === 'invalid_token') {
    bg = '#fee2e2'; color = '#b91c1c'; label = 'WA: token inválido'; icon = '✕';
  } else if (status === 'not_found' || status === 'permission_denied') {
    bg = '#fee2e2'; color = '#b91c1c'; label = 'WA: creds incorrectas'; icon = '✕';
  } else if (status === 'missing_credentials') {
    bg = '#f1f5f9'; color = '#64748b'; label = 'WA: pendiente'; icon = '○';
  }

  const ago = formatTimeAgo(check.checked_at);
  const tooltip = `${check.message}${ago ? ` · ${ago}` : ''}`;

  if (mini) {
    return (
      <span
        className="sa-badge"
        style={{ background: bg, color, fontSize: 11, fontWeight: 600 }}
        title={tooltip}
        data-testid={`wa-health-${tenant.tenant_id}`}
      >
        {icon} {label}
      </span>
    );
  }

  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        background: bg, color, padding: '4px 10px', borderRadius: 12,
        fontSize: 12, fontWeight: 600,
      }}
      title={tooltip}
      data-testid={`wa-health-${tenant.tenant_id}`}
    >
      <span>{icon}</span>
      <span>{label}</span>
      {ago && <span style={{ opacity: 0.7, fontWeight: 400 }}>· {ago}</span>}
    </span>
  );
}

function TenantCard({ tenant, expanded, onToggle, onUpdate }) {
  const [updating, setUpdating] = useState(false);
  const [editingBranding, setEditingBranding] = useState(false);
  const [showFeatureFlags, setShowFeatureFlags] = useState(false);
  const [brandData, setBrandData] = useState({
    business_name: tenant.business_name || tenant.name || '',
    business_tagline: tenant.business_tagline || '',
    template_id: tenant.template_id || 'servicios',
    contact_phone: tenant.contact_phone || '',
    logo_url: tenant.logo_url || '',
    primary_color: tenant.primary_color || '#3b82f6',
    accent_color: tenant.accent_color || '#8b5cf6',
  });

  const saveBranding = async () => {
    setUpdating(true);
    try {
      await axios.put(`${API}/auth/tenants/${tenant.tenant_id}`, brandData);
      setEditingBranding(false);
      onUpdate();
    } catch (err) {
      alert('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUpdating(false);
    }
  };

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

  const resetDemoData = async () => {
    const includeLeads = window.confirm(
      `¿Querés incluir leads y conversaciones en el reset?\n\n` +
      `OK = borrar productos + waitlist + leads + conversaciones (reset TOTAL)\n` +
      `Cancelar = borrar sólo productos + waitlist (reset parcial)`
    );
    const confirmMsg = includeLeads
      ? `⚠️ RESET TOTAL de "${tenant.name}":\n\nSe borrarán productos, waitlist, leads, conversaciones y mensajes.\n\n¿Confirmás?`
      : `Reset parcial de "${tenant.name}":\n\nSe borrarán solamente productos y waitlist.\n\n¿Confirmás?`;
    if (!window.confirm(confirmMsg)) return;
    setUpdating(true);
    try {
      const res = await axios.post(
        `${API}/superadmin/tenants/${tenant.tenant_id}/reset-demo-data`,
        { confirm: true, include_leads: includeLeads }
      );
      const d = res.data;
      const parts = [
        `✅ Demo data reseteado para ${tenant.name}`,
        `• Productos: ${d.products_deleted}`,
        `• Waitlist: ${d.waitlist_deleted}`,
        `• Alerts waitlist: ${d.waitlist_alerts_deleted}`,
      ];
      if (d.leads_deleted !== undefined) {
        parts.push(`• Leads: ${d.leads_deleted}`);
        parts.push(`• Conversaciones: ${d.conversations_deleted}`);
        parts.push(`• Mensajes: ${d.messages_deleted}`);
      }
      if (d.partial) {
        parts.push(`\n⚠️ Borrado parcial — algunas colecciones fallaron:`);
        (d.errors || []).forEach(e => parts.push(`  - ${e.collection}: ${e.error}`));
      }
      alert(parts.join('\n'));
      onUpdate();
    } catch (err) {
      alert('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUpdating(false);
    }
  };

  const seedDemoData = async () => {
    const includeLeads = window.confirm(
      `¿Generar también leads y conversaciones ficticios?\n\n` +
      `OK = productos + waitlist + leads + conversaciones (demo COMPLETA)\n` +
      `Cancelar = solo productos + waitlist (demo BÁSICA)`
    );
    const confirmMsg = includeLeads
      ? `🎲 Seed demo data COMPLETA para "${tenant.name}":\n\nSe generarán ~12 productos + ~30 leads en waitlist + 20 leads con conversaciones.\n\n¿Continuar?`
      : `🎲 Seed demo data BÁSICA para "${tenant.name}":\n\nSe generarán ~12 productos + ~30 leads en waitlist.\n\n¿Continuar?`;
    if (!window.confirm(confirmMsg)) return;
    setUpdating(true);
    try {
      const res = await axios.post(
        `${API}/superadmin/tenants/${tenant.tenant_id}/seed-demo-data`,
        { products_count: 12, waitlist_per_product: 5, include_leads: includeLeads, force: false }
      );
      const d = res.data;
      if (d.skipped) {
        if (window.confirm(`El tenant ya tiene ${d.existing_products} productos. ¿Querés AGREGAR los demo de todos modos?`)) {
          const res2 = await axios.post(
            `${API}/superadmin/tenants/${tenant.tenant_id}/seed-demo-data`,
            { products_count: 12, waitlist_per_product: 5, include_leads: includeLeads, force: true }
          );
          const d2 = res2.data;
          alert(
            `✅ Seed agregado a "${tenant.name}" (template: ${d2.template_used})\n` +
            `• Productos: +${d2.products_inserted}\n` +
            `• Waitlist: +${d2.waitlist_inserted}\n` +
            `• Leads: +${d2.leads_inserted}\n` +
            `• Conversaciones: +${d2.conversations_inserted}`
          );
        }
      } else {
        alert(
          `✅ Demo data generada para "${tenant.name}" (template: ${d.template_used})\n` +
          `• Productos: ${d.products_inserted}\n` +
          `• Waitlist: ${d.waitlist_inserted}\n` +
          `• Leads: ${d.leads_inserted}\n` +
          `• Conversaciones: ${d.conversations_inserted}`
        );
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
          <WhatsAppHealthBadge tenant={tenant} mini />
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
            <div className="sa-detail-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Activity className="w-4 h-4" />
                <span>WhatsApp:</span>
              </div>
              <WhatsAppHealthBadge tenant={tenant} />
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
              variant="outline"
              onClick={() => setEditingBranding(!editingBranding)}
              data-testid={`edit-branding-${tenant.tenant_id}`}
            >
              <Settings className="w-3 h-3 mr-1" />
              {editingBranding ? 'Cerrar editor' : 'Editar branding'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowFeatureFlags(!showFeatureFlags)}
              data-testid={`feature-flags-btn-${tenant.tenant_id}`}
            >
              <Flag className="w-3 h-3 mr-1" />
              {showFeatureFlags ? 'Cerrar flags' : 'Feature Flags'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              asChild
              data-testid={`view-landing-${tenant.tenant_id}`}
            >
              <a href={`/inicio/${tenant.tenant_id}`} target="_blank" rel="noopener noreferrer">
                <Globe className="w-3 h-3 mr-1" /> Ver landing
              </a>
            </Button>
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
            <Button
              size="sm"
              variant="outline"
              onClick={seedDemoData}
              disabled={updating}
              style={{ borderColor: '#a7f3d0', color: '#059669' }}
              data-testid={`seed-demo-${tenant.tenant_id}`}
              title="Genera productos + waitlist (+ leads) ficticios para demos comerciales"
            >
              <Sparkles className="w-3 h-3 mr-1" />
              Seed demo data
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={resetDemoData}
              disabled={updating}
              style={{ borderColor: '#fecaca', color: '#dc2626' }}
              data-testid={`reset-demo-${tenant.tenant_id}`}
              title="Borra productos y waitlist (opcional: leads/conversaciones) para este tenant"
            >
              <Trash2 className="w-3 h-3 mr-1" />
              Reset demo data
            </Button>
          </div>

          {editingBranding && (
            <div className="sa-branding-edit" data-testid={`branding-form-${tenant.tenant_id}`}>
              <div className="sa-branding-grid">
                <div>
                  <label>Nombre del negocio</label>
                  <input
                    value={brandData.business_name}
                    onChange={e => setBrandData({...brandData, business_name: e.target.value})}
                    data-testid="sa-bn"
                  />
                </div>
                <div>
                  <label>Tagline</label>
                  <input
                    value={brandData.business_tagline}
                    onChange={e => setBrandData({...brandData, business_tagline: e.target.value})}
                  />
                </div>
                <div>
                  <label>WhatsApp</label>
                  <input
                    value={brandData.contact_phone}
                    onChange={e => setBrandData({...brandData, contact_phone: e.target.value})}
                    placeholder="5491133334444"
                  />
                </div>
                <div>
                  <label>Template</label>
                  <select
                    value={brandData.template_id}
                    onChange={e => setBrandData({...brandData, template_id: e.target.value})}
                  >
                    <option value="inmobiliaria">Inmobiliaria</option>
                    <option value="clinica">Clínica / Salud</option>
                    <option value="restaurante">Restaurante</option>
                    <option value="ecommerce">E-commerce</option>
                    <option value="servicios">Servicios</option>
                  </select>
                </div>
                <div className="sa-branding-full">
                  <label>URL del logo</label>
                  <input
                    value={brandData.logo_url}
                    onChange={e => setBrandData({...brandData, logo_url: e.target.value})}
                    placeholder="https://..."
                  />
                </div>
                <div>
                  <label>Color primario</label>
                  <div className="sa-color-group">
                    <input type="color" value={brandData.primary_color} onChange={e => setBrandData({...brandData, primary_color: e.target.value})} />
                    <input value={brandData.primary_color} onChange={e => setBrandData({...brandData, primary_color: e.target.value})} />
                  </div>
                </div>
                <div>
                  <label>Color acento</label>
                  <div className="sa-color-group">
                    <input type="color" value={brandData.accent_color} onChange={e => setBrandData({...brandData, accent_color: e.target.value})} />
                    <input value={brandData.accent_color} onChange={e => setBrandData({...brandData, accent_color: e.target.value})} />
                  </div>
                </div>
              </div>
              <div className="sa-branding-actions">
                <Button size="sm" onClick={saveBranding} disabled={updating} data-testid={`save-branding-${tenant.tenant_id}`}>
                  {updating ? 'Guardando...' : 'Guardar branding'}
                </Button>
              </div>
            </div>
          )}

          {showFeatureFlags && (
            <TenantFeatureFlags tenantId={tenant.tenant_id} />
          )}
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
