import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Trash2, Tag, UserCheck, RefreshCw, Copy, MessageCircle } from 'lucide-react';
import LeadDrawer from '../components/LeadDrawer';

export default function Leads({ filterByAgent = null }) {
  const [leads, setLeads] = useState([]);
  const [filteredLeads, setFilteredLeads] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(true);
  const [searchName, setSearchName] = useState('');
  const [searchZone, setSearchZone] = useState('');
  const [searchDateFrom, setSearchDateFrom] = useState('');
  const [searchDateTo, setSearchDateTo] = useState('');
  const [searchIntent, setSearchIntent] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');
  const [selectedLeads, setSelectedLeads] = useState([]);
  const [bulkAction, setBulkAction] = useState('');
  const [bulkValue, setBulkValue] = useState('');
  const [agents, setAgents] = useState([]);
  const [processingBulk, setProcessingBulk] = useState(false);
  const [drawerPhone, setDrawerPhone] = useState(null);
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchLeads();
    fetchAgents();
  }, [filterByAgent]);
  
  useEffect(() => {
    filterLeads();
  }, [activeTab, leads, searchName, searchZone, searchDateFrom, searchDateTo, searchIntent, sortBy, sortDir]);
  
  const fetchLeads = async () => {
    try {
      const endpoint = filterByAgent ? `${API}/leads/assigned-to-me` : `${API}/leads`;
      const response = await axios.get(endpoint);
      setLeads(Array.isArray(response.data) ? response.data : (response.data.leads || []));
    } catch (error) {
      console.error('Error fetching leads:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgents = async () => {
    try {
      const response = await axios.get(`${API}/agents`);
      setAgents(Array.isArray(response.data) ? response.data : (response.data.agents || []));
    } catch (error) {
      console.error('Error fetching agents:', error);
    }
  };
  
  const filterLeads = () => {
    let filtered = leads;
    
    // Filtrar por status (tab)
    if (activeTab !== 'all') {
      filtered = filtered.filter(lead => lead.status === activeTab);
    }
    
    // Filtrar por nombre
    if (searchName) {
      filtered = filtered.filter(lead => 
        (lead.name || '').toLowerCase().includes(searchName.toLowerCase())
      );
    }
    
    // Filtrar por zona
    if (searchZone) {
      filtered = filtered.filter(lead => 
        (lead.zone || '').toLowerCase().includes(searchZone.toLowerCase())
      );
    }
    
    // Filtrar por intención
    if (searchIntent && searchIntent !== 'all') {
      if (searchIntent === 'sin_definir') {
        filtered = filtered.filter(lead => !lead.intent);
      } else {
        filtered = filtered.filter(lead => lead.intent === searchIntent);
      }
    }

    // Filtrar por fecha
    if (searchDateFrom) {
      filtered = filtered.filter(lead => {
        const leadDate = new Date(lead.created_at);
        const fromDate = new Date(searchDateFrom);
        return leadDate >= fromDate;
      });
    }
    
    if (searchDateTo) {
      filtered = filtered.filter(lead => {
        const leadDate = new Date(lead.created_at);
        const toDate = new Date(searchDateTo);
        toDate.setHours(23, 59, 59);
        return leadDate <= toDate;
      });
    }
    
    // Ordenar
    const statusOrder = { hot: 0, warm: 1, cold: 2 };
    filtered = [...filtered].sort((a, b) => {
      let valA, valB;
      if (sortBy === 'score') {
        valA = a.score ?? 0; valB = b.score ?? 0;
      } else if (sortBy === 'status') {
        valA = statusOrder[a.status] ?? 9; valB = statusOrder[b.status] ?? 9;
      } else if (sortBy === 'last_message_at') {
        valA = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
        valB = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
      } else {
        valA = a.created_at ? new Date(a.created_at).getTime() : 0;
        valB = b.created_at ? new Date(b.created_at).getTime() : 0;
      }
      return sortDir === 'asc' ? valA - valB : valB - valA;
    });

    setFilteredLeads(filtered);
  };

  const FLOW_STEPS = [
    { key: 'welcome',          label: 'Inicio' },
    { key: 'intent',           label: 'Intención' },
    { key: 'zone',             label: 'Zona' },
    { key: 'budget',           label: 'Presupuesto' },
    { key: 'appointment_offer',label: 'Cita' },
    { key: 'hot_lead',         label: '✅ Listo' },
  ];

  const FlowStageBar = ({ stage }) => {
    const idx = FLOW_STEPS.findIndex(s =>
      stage === s.key ||
      (['scoring', 'property_type', 'select_day', 'confirm_appointment', 'bedrooms', 'urgency'].includes(stage) && s.key === 'budget') ||
      (['appointment_reminder', 'completed'].includes(stage) && s.key === 'hot_lead')
    );
    const activeIdx = idx === -1 ? 0 : idx;
    const pct = Math.round((activeIdx / (FLOW_STEPS.length - 1)) * 100);
    const currentLabel = FLOW_STEPS[activeIdx]?.label || stage;

    return (
      <div className="flow-stage-bar" title={`Etapa del bot: ${currentLabel}`}>
        <div className="flow-stage-track">
          <div className="flow-stage-fill" style={{ width: `${pct}%` }} />
        </div>
        <span className="flow-stage-label">{currentLabel}</span>
      </div>
    );
  };

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('desc');
    }
  };

  const SortBtn = ({ field, label }) => {
    const active = sortBy === field;
    return (
      <button
        className={`sort-btn ${active ? 'sort-btn--active' : ''}`}
        onClick={() => toggleSort(field)}
        title={`Ordenar por ${label}`}
      >
        {label}
        <span className="sort-arrow">
          {active ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ' ↕'}
        </span>
      </button>
    );
  };
  
  const clearFilters = () => {
    setSearchName('');
    setSearchZone('');
    setSearchDateFrom('');
    setSearchDateTo('');
    setSearchIntent('');
  };

  // Bulk Actions
  const toggleSelectLead = (phone) => {
    setSelectedLeads(prev => 
      prev.includes(phone) 
        ? prev.filter(p => p !== phone)
        : [...prev, phone]
    );
  };

  const toggleSelectAll = () => {
    if (selectedLeads.length === filteredLeads.length) {
      setSelectedLeads([]);
    } else {
      setSelectedLeads(filteredLeads.map(l => l.phone));
    }
  };

  const executeBulkAction = async () => {
    if (!bulkAction || selectedLeads.length === 0) {
      toast.error('Seleccioná una acción y al menos un lead');
      return;
    }

    if ((bulkAction === 'tag' || bulkAction === 'assign' || bulkAction === 'status') && !bulkValue) {
      toast.error('Ingresá un valor para la acción');
      return;
    }

    if (bulkAction === 'delete') {
      const confirmed = window.confirm(`¿Estás seguro de eliminar ${selectedLeads.length} leads? Esta acción no se puede deshacer.`);
      if (!confirmed) return;
    }

    setProcessingBulk(true);
    try {
      const response = await axios.post(`${API}/leads/bulk-action`, {
        lead_phones: selectedLeads,
        action: bulkAction,
        value: bulkValue || null
      });

      toast.success(`Acción ejecutada: ${response.data.updated_count} leads actualizados`);
      setSelectedLeads([]);
      setBulkAction('');
      setBulkValue('');
      fetchLeads();
    } catch (error) {
      console.error('Error executing bulk action:', error);
      toast.error('Error ejecutando acción masiva');
    } finally {
      setProcessingBulk(false);
    }
  };
  
  const exportToCSV = () => {
    try {
      const headers = ['Nombre', 'Teléfono', 'Intención', 'Zona', 'Presupuesto', 'Tipo', 'Dormitorios', 'Urgencia', 'Score', 'Estado', 'Fecha Creación', 'Cita'];
      
      const rows = filteredLeads.map(lead => [
        lead.name || 'Sin nombre',
        lead.phone,
        lead.intent || '',
        lead.zone || '',
        lead.budget_text || '',
        lead.property_type || '',
        lead.bedrooms || '',
        lead.urgency || '',
        lead.score,
        lead.status,
        new Date(lead.created_at).toLocaleDateString('es-AR'),
        lead.appointment_datetime ? new Date(lead.appointment_datetime).toLocaleString('es-AR') : 'Sin cita'
      ]);
      
      let csvContent = headers.join(',') + '\n';
      rows.forEach(row => {
        csvContent += row.map(cell => `"${cell}"`).join(',') + '\n';
      });
      
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `leads_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      toast.success(`${filteredLeads.length} leads exportados a CSV`);
    } catch (error) {
      console.error('Error exporting CSV:', error);
      toast.error('Error exportando leads');
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
    return date.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  };

  const timeAgo = (dateString) => {
    if (!dateString) return null;
    const diff = Math.floor((Date.now() - new Date(dateString)) / 1000);
    if (diff < 60) return 'hace un momento';
    if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
    if (diff < 172800) return 'ayer';
    if (diff < 604800) return `hace ${Math.floor(diff / 86400)} días`;
    return formatDate(dateString);
  };
  
  const formatPhone = (phone) => {
    // Convierte 5491168754798 → +54 9 11 6875-4798
    const p = String(phone).replace(/\D/g, '');
    if (p.startsWith('549') && p.length === 13) {
      return `+54 9 ${p.slice(3, 5)} ${p.slice(5, 9)}-${p.slice(9)}`;
    }
    if (p.startsWith('54') && p.length === 12) {
      return `+54 ${p.slice(2, 4)} ${p.slice(4, 8)}-${p.slice(8)}`;
    }
    return `+${p}`;
  };

  const copyPhone = (e, phone) => {
    e.stopPropagation();
    navigator.clipboard.writeText(formatPhone(phone));
    toast.success('Teléfono copiado');
  };

  const openWhatsApp = (e, phone) => {
    e.stopPropagation();
    window.open(`https://wa.me/${phone}`, '_blank');
  };

  if (loading) {
    return <div className="loading-container">Cargando leads...</div>;
  }
  
  // Leads con los filtros de texto/fecha/intención aplicados pero sin filtro de tab
  // — se usa para los conteos dinámicos de los tabs
  const leadsPreTab = leads.filter(lead => {
    if (searchName && !(lead.name || '').toLowerCase().includes(searchName.toLowerCase())) return false;
    if (searchZone && !(lead.zone || '').toLowerCase().includes(searchZone.toLowerCase())) return false;
    if (searchIntent && searchIntent !== 'all') {
      if (searchIntent === 'sin_definir' && lead.intent) return false;
      if (searchIntent !== 'sin_definir' && lead.intent !== searchIntent) return false;
    }
    if (searchDateFrom) {
      const from = new Date(searchDateFrom);
      if (new Date(lead.created_at) < from) return false;
    }
    if (searchDateTo) {
      const to = new Date(searchDateTo);
      to.setHours(23, 59, 59);
      if (new Date(lead.created_at) > to) return false;
    }
    return true;
  });

  const tabCounts = {
    all:  leadsPreTab.length,
    hot:  leadsPreTab.filter(l => l.status === 'hot').length,
    warm: leadsPreTab.filter(l => l.status === 'warm').length,
    cold: leadsPreTab.filter(l => l.status === 'cold').length,
  };

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const kpis = {
    hot: leads.filter(l => l.status === 'hot').length,
    citasHoy: leads.filter(l => {
      if (!l.appointment_datetime) return false;
      const d = new Date(l.appointment_datetime);
      d.setHours(0, 0, 0, 0);
      return d.getTime() === today.getTime();
    }).length,
    nuevosHoy: leads.filter(l => {
      if (!l.created_at) return false;
      const d = new Date(l.created_at);
      d.setHours(0, 0, 0, 0);
      return d.getTime() === today.getTime();
    }).length,
    sinAsesor: leads.filter(l => !l.assigned_agent_email).length,
  };

  return (
    <div className="page-container" data-testid="leads-page">
      <header className="page-header">
        <div>
          <h1>Leads</h1>
          <p className="subtitle">Gestión y seguimiento de contactos</p>
        </div>
        <div className="header-actions">
          <Button onClick={fetchLeads} variant="ghost" size="sm" data-testid="btn-refresh">
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button onClick={exportToCSV} variant="outline" data-testid="btn-export-csv">
            📥 Exportar CSV ({filteredLeads.length})
          </Button>
        </div>
      </header>

      <div className="leads-kpis">
        <div className="kpi-card kpi-hot">
          <span className="kpi-icon">🔥</span>
          <div>
            <span className="kpi-value">{kpis.hot}</span>
            <span className="kpi-label">Calientes</span>
          </div>
        </div>
        <div className="kpi-card kpi-citas">
          <span className="kpi-icon">📅</span>
          <div>
            <span className="kpi-value">{kpis.citasHoy}</span>
            <span className="kpi-label">Citas hoy</span>
          </div>
        </div>
        <div className="kpi-card kpi-nuevos">
          <span className="kpi-icon">⚡</span>
          <div>
            <span className="kpi-value">{kpis.nuevosHoy}</span>
            <span className="kpi-label">Nuevos hoy</span>
          </div>
        </div>
        <div className="kpi-card kpi-sinasesor">
          <span className="kpi-icon">⚠️</span>
          <div>
            <span className="kpi-value">{kpis.sinAsesor}</span>
            <span className="kpi-label">Sin asesor</span>
          </div>
        </div>
      </div>

      {/* Bulk Actions Panel */}
      {selectedLeads.length > 0 && (
        <Card className="bulk-actions-panel" data-testid="bulk-actions-panel">
          <CardContent className="bulk-actions-content">
            <div className="bulk-selection-info">
              <Checkbox 
                checked={selectedLeads.length === filteredLeads.length}
                onCheckedChange={toggleSelectAll}
                data-testid="checkbox-select-all"
              />
              <span>{selectedLeads.length} leads seleccionados</span>
              <Button variant="ghost" size="sm" onClick={() => setSelectedLeads([])}>
                Deseleccionar
              </Button>
            </div>
            
            <div className="bulk-actions-form">
              <Select value={bulkAction} onValueChange={setBulkAction}>
                <SelectTrigger className="w-40" data-testid="select-bulk-action">
                  <SelectValue placeholder="Acción..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="tag"><Tag className="w-4 h-4 inline mr-2" />Agregar Tag</SelectItem>
                  <SelectItem value="status"><RefreshCw className="w-4 h-4 inline mr-2" />Cambiar Estado</SelectItem>
                  <SelectItem value="assign"><UserCheck className="w-4 h-4 inline mr-2" />Asignar Asesor</SelectItem>
                  <SelectItem value="delete"><Trash2 className="w-4 h-4 inline mr-2" />Eliminar</SelectItem>
                </SelectContent>
              </Select>

              {bulkAction === 'tag' && (
                <Input 
                  placeholder="Nombre del tag..."
                  value={bulkValue}
                  onChange={(e) => setBulkValue(e.target.value)}
                  className="w-40"
                  data-testid="input-bulk-tag"
                />
              )}

              {bulkAction === 'status' && (
                <Select value={bulkValue} onValueChange={setBulkValue}>
                  <SelectTrigger className="w-40" data-testid="select-bulk-status">
                    <SelectValue placeholder="Estado..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">Nuevo</SelectItem>
                    <SelectItem value="contacted">Contactado</SelectItem>
                    <SelectItem value="qualified">Calificado</SelectItem>
                    <SelectItem value="hot">Caliente</SelectItem>
                    <SelectItem value="warm">Tibio</SelectItem>
                    <SelectItem value="cold">Frío</SelectItem>
                    <SelectItem value="completed">Cerrado</SelectItem>
                  </SelectContent>
                </Select>
              )}

              {bulkAction === 'assign' && (
                <Select value={bulkValue} onValueChange={setBulkValue}>
                  <SelectTrigger className="w-48" data-testid="select-bulk-agent">
                    <SelectValue placeholder="Asesor..." />
                  </SelectTrigger>
                  <SelectContent>
                    {agents.filter(a => a.role !== 'admin').map(agent => (
                      <SelectItem key={agent.email} value={agent.email}>
                        {agent.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              <Button 
                onClick={executeBulkAction} 
                disabled={processingBulk || !bulkAction}
                variant={bulkAction === 'delete' ? 'destructive' : 'default'}
                data-testid="btn-execute-bulk"
              >
                {processingBulk ? 'Procesando...' : 'Ejecutar'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      
      <Card className="filters-card">
        <CardContent>
          <div className="filters-grid">
            <div className="filter-item">
              <label>Buscar por nombre</label>
              <Input 
                placeholder="Ej: Juan Pérez"
                value={searchName}
                onChange={(e) => setSearchName(e.target.value)}
                data-testid="filter-name"
              />
            </div>
            
            <div className="filter-item">
              <label>Buscar por zona</label>
              <Input 
                placeholder="Ej: Palermo"
                value={searchZone}
                onChange={(e) => setSearchZone(e.target.value)}
                data-testid="filter-zone"
              />
            </div>
            
            <div className="filter-item">
              <label>Intención</label>
              <Select value={searchIntent} onValueChange={setSearchIntent}>
                <SelectTrigger data-testid="filter-intent">
                  <SelectValue placeholder="Todas" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  <SelectItem value="comprar">🏠 Comprar</SelectItem>
                  <SelectItem value="alquilar">🔑 Alquilar</SelectItem>
                  <SelectItem value="vender">💰 Vender</SelectItem>
                  <SelectItem value="inversion">📈 Inversión</SelectItem>
                  <SelectItem value="sin_definir">❓ Sin definir</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="filter-item">
              <label>Fecha desde</label>
              <Input 
                type="date"
                value={searchDateFrom}
                onChange={(e) => setSearchDateFrom(e.target.value)}
                data-testid="filter-date-from"
              />
            </div>
            
            <div className="filter-item">
              <label>Fecha hasta</label>
              <Input 
                type="date"
                value={searchDateTo}
                onChange={(e) => setSearchDateTo(e.target.value)}
                data-testid="filter-date-to"
              />
            </div>
            
            <div className="filter-item filter-actions">
              <Button onClick={clearFilters} variant="ghost" data-testid="btn-clear-filters">
                🔄 Limpiar Filtros
              </Button>
            </div>
          </div>
          
          <div className="filter-results-row">
            <span>Mostrando {filteredLeads.length} de {leads.length} leads</span>
            <div className="sort-bar">
              <span className="sort-label">Ordenar:</span>
              <SortBtn field="score" label="Score" />
              <SortBtn field="status" label="Temperatura" />
              <SortBtn field="last_message_at" label="Actividad" />
              <SortBtn field="created_at" label="Fecha" />
            </div>
          </div>
        </CardContent>
      </Card>
      
      <Tabs value={activeTab} onValueChange={setActiveTab} className="leads-tabs">
        <TabsList>
          <TabsTrigger value="all" data-testid="tab-all">Todos ({tabCounts.all})</TabsTrigger>
          <TabsTrigger value="hot" data-testid="tab-hot">🔥 Calientes ({tabCounts.hot})</TabsTrigger>
          <TabsTrigger value="warm" data-testid="tab-warm">🟡 Tibios ({tabCounts.warm})</TabsTrigger>
          <TabsTrigger value="cold" data-testid="tab-cold">❄️ Fríos ({tabCounts.cold})</TabsTrigger>
        </TabsList>
        
        <TabsContent value={activeTab}>
          <div className="leads-grid">
            {filteredLeads.length === 0 ? (
              <div className="empty-state-leads">
                {leads.length === 0 ? (
                  <>
                    <span className="empty-state-icon">🤖</span>
                    <h3>Aún no hay leads</h3>
                    <p>Cuando el bot capture contactos por WhatsApp aparecerán aquí automáticamente.</p>
                  </>
                ) : (
                  <>
                    <span className="empty-state-icon">🔍</span>
                    <h3>Sin resultados</h3>
                    <p>Ningún lead coincide con los filtros activos.</p>
                    <Button variant="outline" size="sm" onClick={clearFilters}>
                      Limpiar filtros
                    </Button>
                  </>
                )}
              </div>
            ) : (
              filteredLeads.map((lead) => (
                <Card 
                  key={lead.phone} 
                  className={`lead-card ${selectedLeads.includes(lead.phone) ? 'selected' : ''}`}
                  data-testid={`lead-card-${lead.phone}`}
                >
                  <CardContent className="lead-card-content">
                    <div className="lead-header">
                      <div className="lead-header-left">
                        <Checkbox 
                          checked={selectedLeads.includes(lead.phone)}
                          onCheckedChange={() => toggleSelectLead(lead.phone)}
                          onClick={(e) => e.stopPropagation()}
                          data-testid={`checkbox-lead-${lead.phone}`}
                        />
                        <div onClick={() => setDrawerPhone(lead.phone)} className="lead-info-clickable">
                          <h3>{lead.name || 'Sin nombre'}</h3>
                          <p className="lead-phone">
                            {formatPhone(lead.phone)}
                            <button
                              className="phone-action-btn"
                              onClick={(e) => copyPhone(e, lead.phone)}
                              title="Copiar teléfono"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                            <button
                              className="phone-action-btn whatsapp-btn"
                              onClick={(e) => openWhatsApp(e, lead.phone)}
                              title="Abrir en WhatsApp"
                            >
                              <MessageCircle className="w-3 h-3" />
                            </button>
                          </p>
                        </div>
                      </div>
                      {getStatusBadge(lead.status)}
                    </div>
                    
                    <div className="lead-details" onClick={() => setDrawerPhone(lead.phone)}>
                      <div className="detail-row">
                        <span className="label">Intención:</span>
                        <span className="value">{lead.intent || 'No definida'}</span>
                      </div>
                      
                      {lead.zone && (
                        <div className="detail-row">
                          <span className="label">Zona:</span>
                          <span className="value">{lead.zone}</span>
                        </div>
                      )}
                      
                      {lead.budget_text && (
                        <div className="detail-row">
                          <span className="label">Presupuesto:</span>
                          <span className="value">{lead.budget_text}</span>
                        </div>
                      )}
                      
                      <div className="detail-row score-row">
                        <span className="label">Score:</span>
                        <div className="score-bar-wrapper">
                          <div
                            className="score-bar-fill"
                            style={{ width: `${Math.round((lead.score / 12) * 100)}%` }}
                            data-score={lead.score}
                          />
                        </div>
                        <span className="score-label">{lead.score}/12</span>
                      </div>
                      
                      {lead.appointment_datetime && (
                        <div className="appointment-badge">
                          📅 Cita: {formatDate(lead.appointment_datetime)}
                        </div>
                      )}
                    </div>

                    {lead.flow_stage && <FlowStageBar stage={lead.flow_stage} />}

                    <div className="lead-footer">
                      {lead.assigned_agent_name ? (
                        <span className="lead-agent" title="Asesor asignado">
                          👤 {lead.assigned_agent_name}
                        </span>
                      ) : (
                        <span className="lead-agent lead-agent--unassigned">Sin asesor</span>
                      )}
                      <span className="created-date" title={`Creado: ${formatDate(lead.created_at)}`}>
                        {lead.last_message_at
                          ? <>🕐 {timeAgo(lead.last_message_at)}</>
                          : <>📅 {formatDate(lead.created_at)}</>
                        }
                      </span>
                      {lead.tags && lead.tags.length > 0 && (
                        <div className="lead-tags">
                          {lead.tags.slice(0, 2).map(tag => (
                            <Badge key={tag} variant="outline" className="tag-badge">{tag}</Badge>
                          ))}
                          {lead.tags.length > 2 && <span className="more-tags">+{lead.tags.length - 2}</span>}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>

      <LeadDrawer
        phone={drawerPhone}
        onClose={() => setDrawerPhone(null)}
      />
    </div>
  );
}