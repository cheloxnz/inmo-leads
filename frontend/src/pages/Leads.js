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
  const [searchQuery, setSearchQuery] = useState('');   // búsqueda unificada (nombre/tel/zona)
  const [searchDateFrom, setSearchDateFrom] = useState('');
  const [searchDateTo, setSearchDateTo] = useState('');
  const [searchIntent, setSearchIntent] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false); // panel avanzado colapsable
  const [quickFilter, setQuickFilter] = useState(null);  // 'citas_hoy' | 'nuevos_hoy' | 'sin_asesor' | null
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const PAGE_SIZE = 20;
  const [selectedLeads, setSelectedLeads] = useState([]);
  const [bulkAction, setBulkAction] = useState('');
  const [bulkValue, setBulkValue] = useState('');
  const [agents, setAgents] = useState([]);
  const [processingBulk, setProcessingBulk] = useState(false);
  const [bulkTagInput, setBulkTagInput] = useState('');
  const [showBulkTagInput, setShowBulkTagInput] = useState(false);
  const [drawerPhone, setDrawerPhone] = useState(null);
  const [assigningPhone, setAssigningPhone] = useState(null);
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchLeads();
    fetchAgents();
  }, [filterByAgent]);

  useEffect(() => {
    if (!assigningPhone) return;
    const handler = () => setAssigningPhone(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [assigningPhone]);
  
  useEffect(() => {
    filterLeads();
    setCurrentPage(1); // reset al cambiar filtros
  }, [activeTab, leads, searchQuery, searchDateFrom, searchDateTo, searchIntent, sortBy, sortDir, quickFilter]);
  
  const fetchLeads = async () => {
    try {
      const endpoint = filterByAgent
        ? `${API}/leads/assigned-to-me`
        : `${API}/leads?limit=500`;
      const response = await axios.get(endpoint);
      const data = response.data;
      setLeads(Array.isArray(data) ? data : (data.leads || []));
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
    if (activeTab === 'no_intent') {
      filtered = filtered.filter(l => !l.intent || l.intent === 'sin_definir');
    } else if (activeTab !== 'all') {
      filtered = filtered.filter(lead => lead.status === activeTab);
    }
    
    // Búsqueda unificada: nombre, teléfono o zona en un solo campo
    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim();
      const qNum = searchQuery.replace(/\D/g, '');
      filtered = filtered.filter(lead =>
        (lead.name || '').toLowerCase().includes(q) ||
        (qNum && String(lead.phone).includes(qNum)) ||
        (lead.zone || '').toLowerCase().includes(q)
      );
    }

    // Quick-filters desde KPIs
    if (quickFilter === 'citas_hoy') {
      const t = new Date(); t.setHours(0, 0, 0, 0);
      filtered = filtered.filter(l => {
        if (!l.appointment_datetime) return false;
        const d = new Date(l.appointment_datetime); d.setHours(0, 0, 0, 0);
        return d.getTime() === t.getTime();
      });
    } else if (quickFilter === 'nuevos_hoy') {
      const t = new Date(); t.setHours(0, 0, 0, 0);
      filtered = filtered.filter(l => {
        if (!l.created_at) return false;
        const d = new Date(l.created_at); d.setHours(0, 0, 0, 0);
        return d.getTime() === t.getTime();
      });
    } else if (quickFilter === 'sin_asesor') {
      filtered = filtered.filter(l => !l.assigned_agent_email && !l.assigned_agent);
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

  const getScoreCriteria = (lead) => [
    { label: 'Intención',      met: !!lead.intent && lead.intent !== 'sin_definir' },
    { label: 'Zona',           met: !!lead.zone },
    { label: 'Presupuesto',    met: !!lead.budget_text },
    { label: 'Tipo propiedad', met: !!lead.property_type },
    { label: 'Urgencia',       met: !!lead.urgency },
    { label: 'Financiamiento', met: !!lead.financing && lead.financing !== 'no_se' },
    { label: 'Must-have',      met: !!(lead.must_have?.length) },
    { label: 'Cita agendada',  met: !!lead.appointment_datetime },
    { label: 'Nombre',         met: !!lead.name },
  ];

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
    setSearchQuery('');
    setSearchDateFrom('');
    setSearchDateTo('');
    setSearchIntent('');
    setQuickFilter(null);
    setActiveTab('all');
  };

  // Manejador de click en KPIs
  const handleKpiClick = (filter) => {
    if (filter === 'hot') {
      // toggle el tab calientes
      setActiveTab(prev => prev === 'hot' ? 'all' : 'hot');
      setQuickFilter(null);
    } else {
      // para los demás, trabajamos sobre la vista "Todos"
      setActiveTab('all');
      setQuickFilter(prev => prev === filter ? null : filter);
    }
    setCurrentPage(1);
  };

  // Cuenta de filtros avanzados activos (para el badge del botón)
  const activeAdvancedCount = [
    searchIntent && searchIntent !== 'all',
    !!searchDateFrom,
    !!searchDateTo,
  ].filter(Boolean).length;

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

  const quickAssign = async (e, leadPhone, agentEmail) => {
    e.stopPropagation();
    setAssigningPhone(null);
    try {
      await axios.post(`${API}/leads/bulk-action`, {
        lead_phones: [leadPhone],
        action: 'assign',
        value: agentEmail,
      });
      toast.success('Asesor asignado');
      fetchLeads();
    } catch {
      toast.error('Error asignando asesor');
    }
  };

  // Acción masiva directa (para la barra flotante — sin paso intermedio de "Ejecutar")
  const quickBulkAction = async (action, value) => {
    if (selectedLeads.length === 0) return;
    if (action === 'delete') {
      const ok = window.confirm(`¿Eliminar ${selectedLeads.length} lead${selectedLeads.length > 1 ? 's' : ''}? Esta acción no se puede deshacer.`);
      if (!ok) return;
    }
    setProcessingBulk(true);
    try {
      const res = await axios.post(`${API}/leads/bulk-action`, {
        lead_phones: selectedLeads,
        action,
        value: value || null,
      });
      toast.success(`${res.data.updated_count} lead${res.data.updated_count > 1 ? 's' : ''} actualizado${res.data.updated_count > 1 ? 's' : ''}`);
      setSelectedLeads([]);
      setBulkTagInput('');
      setShowBulkTagInput(false);
      fetchLeads();
    } catch {
      toast.error('Error ejecutando acción masiva');
    } finally {
      setProcessingBulk(false);
    }
  };

  // Helpers de intención — icono + label legible
  const INTENT_MAP = {
    comprar:   { icon: '🏠', label: 'Comprar' },
    alquilar:  { icon: '🔑', label: 'Alquilar' },
    vender:    { icon: '💰', label: 'Vender' },
    inversion: { icon: '📈', label: 'Inversión' },
  };
  const intentIcon  = (intent) => INTENT_MAP[intent]?.icon  ?? '❓';
  const intentLabel = (intent) => INTENT_MAP[intent]?.label ?? null;

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
    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim();
      const qNum = searchQuery.replace(/\D/g, '');
      const match = (lead.name || '').toLowerCase().includes(q) ||
        (qNum && String(lead.phone).includes(qNum)) ||
        (lead.zone || '').toLowerCase().includes(q);
      if (!match) return false;
    }
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
    all:         leadsPreTab.length,
    hot:         leadsPreTab.filter(l => l.status === 'hot').length,
    warm:        leadsPreTab.filter(l => l.status === 'warm').length,
    cold:        leadsPreTab.filter(l => l.status === 'cold').length,
    no_intent:   leadsPreTab.filter(l => !l.intent || l.intent === 'sin_definir').length,
  };

  const totalPages = Math.ceil(filteredLeads.length / PAGE_SIZE);
  const pagedLeads = filteredLeads.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

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
        <div
          className={`kpi-card kpi-hot kpi-clickable ${activeTab === 'hot' ? 'kpi-active' : ''}`}
          onClick={() => handleKpiClick('hot')}
          title="Ver leads calientes"
        >
          <span className="kpi-icon">🔥</span>
          <div>
            <span className="kpi-value">{kpis.hot}</span>
            <span className="kpi-label">Calientes</span>
          </div>
          {activeTab === 'hot' && <span className="kpi-active-dot" />}
        </div>
        <div
          className={`kpi-card kpi-citas kpi-clickable ${quickFilter === 'citas_hoy' ? 'kpi-active' : ''}`}
          onClick={() => handleKpiClick('citas_hoy')}
          title="Ver leads con cita hoy"
        >
          <span className="kpi-icon">📅</span>
          <div>
            <span className="kpi-value">{kpis.citasHoy}</span>
            <span className="kpi-label">Citas hoy</span>
          </div>
          {quickFilter === 'citas_hoy' && <span className="kpi-active-dot" />}
        </div>
        <div
          className={`kpi-card kpi-nuevos kpi-clickable ${quickFilter === 'nuevos_hoy' ? 'kpi-active' : ''}`}
          onClick={() => handleKpiClick('nuevos_hoy')}
          title="Ver leads de hoy"
        >
          <span className="kpi-icon">⚡</span>
          <div>
            <span className="kpi-value">{kpis.nuevosHoy}</span>
            <span className="kpi-label">Nuevos hoy</span>
          </div>
          {quickFilter === 'nuevos_hoy' && <span className="kpi-active-dot" />}
        </div>
        <div
          className={`kpi-card kpi-sinasesor kpi-clickable ${quickFilter === 'sin_asesor' ? 'kpi-active kpi-active--warning' : ''}`}
          onClick={() => handleKpiClick('sin_asesor')}
          title="Ver leads sin asesor asignado"
        >
          <span className="kpi-icon">⚠️</span>
          <div>
            <span className="kpi-value">{kpis.sinAsesor}</span>
            <span className="kpi-label">Sin asesor</span>
          </div>
          {quickFilter === 'sin_asesor' && <span className="kpi-active-dot kpi-active-dot--warning" />}
        </div>
      </div>

      {/* ── Barra flotante de acciones masivas ── */}
      {selectedLeads.length > 0 && (
        <div className="bulk-float-bar" data-testid="bulk-actions-panel">
          {/* Izquierda: conteo + select all */}
          <div className="bulk-float-left">
            <Checkbox
              checked={selectedLeads.length === filteredLeads.length}
              onCheckedChange={toggleSelectAll}
              data-testid="checkbox-select-all"
              className="bulk-float-checkbox"
            />
            <span className="bulk-float-count">
              {selectedLeads.length} lead{selectedLeads.length > 1 ? 's' : ''}
            </span>
          </div>

          {/* Centro: acciones directas */}
          <div className="bulk-float-actions">

            {/* Asignar asesor */}
            <Select onValueChange={(val) => quickBulkAction('assign', val)} disabled={processingBulk}>
              <SelectTrigger className="bulk-float-select" data-testid="select-bulk-agent">
                <UserCheck className="w-3.5 h-3.5" />
                <span>Asignar</span>
              </SelectTrigger>
              <SelectContent>
                {agents.filter(a => a.role !== 'admin').map(agent => (
                  <SelectItem key={agent.email} value={agent.email}>{agent.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Cambiar estado */}
            <Select onValueChange={(val) => quickBulkAction('status', val)} disabled={processingBulk}>
              <SelectTrigger className="bulk-float-select" data-testid="select-bulk-status">
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Estado</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hot">🔥 Caliente</SelectItem>
                <SelectItem value="warm">🟡 Tibio</SelectItem>
                <SelectItem value="cold">❄️ Frío</SelectItem>
                <SelectItem value="contacted">Contactado</SelectItem>
                <SelectItem value="qualified">Calificado</SelectItem>
                <SelectItem value="completed">Cerrado</SelectItem>
              </SelectContent>
            </Select>

            {/* Tag rápido */}
            {showBulkTagInput ? (
              <div className="bulk-float-tag-wrap">
                <Input
                  className="bulk-float-tag-input"
                  placeholder="Nombre del tag..."
                  value={bulkTagInput}
                  onChange={e => setBulkTagInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && bulkTagInput.trim()) quickBulkAction('tag', bulkTagInput.trim());
                    if (e.key === 'Escape') { setShowBulkTagInput(false); setBulkTagInput(''); }
                  }}
                  autoFocus
                  data-testid="input-bulk-tag"
                />
                <button
                  className="bulk-float-tag-ok"
                  onClick={() => bulkTagInput.trim() && quickBulkAction('tag', bulkTagInput.trim())}
                  disabled={!bulkTagInput.trim() || processingBulk}
                >✓</button>
                <button
                  className="bulk-float-tag-cancel"
                  onClick={() => { setShowBulkTagInput(false); setBulkTagInput(''); }}
                >✕</button>
              </div>
            ) : (
              <button
                className="bulk-float-btn"
                onClick={() => setShowBulkTagInput(true)}
                disabled={processingBulk}
                title="Agregar tag"
              >
                <Tag className="w-3.5 h-3.5" /> Tag
              </button>
            )}

            {/* Separador */}
            <span className="bulk-float-sep" />

            {/* Eliminar */}
            <button
              className="bulk-float-btn bulk-float-btn--danger"
              onClick={() => quickBulkAction('delete')}
              disabled={processingBulk}
              title="Eliminar seleccionados"
              data-testid="btn-execute-bulk"
            >
              <Trash2 className="w-3.5 h-3.5" />
              {processingBulk ? '...' : 'Eliminar'}
            </button>
          </div>

          {/* Derecha: cerrar */}
          <button
            className="bulk-float-close"
            onClick={() => { setSelectedLeads([]); setShowBulkTagInput(false); setBulkTagInput(''); }}
            title="Deseleccionar todo"
          >✕</button>
        </div>
      )}
      
      <Card className="filters-card">
        <CardContent>
          {/* ── Barra principal: búsqueda unificada + toggle avanzado ── */}
          <div className="filter-main-row">
            <div className="filter-search-wrap">
              <span className="filter-search-icon">🔍</span>
              <Input
                className="filter-search-input"
                placeholder="Buscar por nombre, teléfono o zona..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                data-testid="filter-search"
              />
              {searchQuery && (
                <button className="filter-search-clear" onClick={() => setSearchQuery('')} title="Limpiar búsqueda">
                  ✕
                </button>
              )}
            </div>

            <button
              className={`filter-toggle-btn ${filtersOpen ? 'filter-toggle-btn--open' : ''}`}
              onClick={() => setFiltersOpen(v => !v)}
              data-testid="btn-toggle-filters"
            >
              ⚙️ Filtros
              {activeAdvancedCount > 0 && (
                <span className="filter-badge">{activeAdvancedCount}</span>
              )}
              <span className="filter-toggle-arrow">{filtersOpen ? '▲' : '▼'}</span>
            </button>

            {(searchQuery || activeAdvancedCount > 0 || quickFilter) && (
              <button className="filter-clear-all-btn" onClick={clearFilters} data-testid="btn-clear-filters">
                Limpiar todo
              </button>
            )}
          </div>

          {/* ── Chips de filtros activos ── */}
          {(searchQuery || activeAdvancedCount > 0 || quickFilter) && (
            <div className="filter-chips">
              {searchQuery && (
                <span className="filter-chip">
                  🔍 "{searchQuery}"
                  <button onClick={() => setSearchQuery('')}>✕</button>
                </span>
              )}
              {quickFilter === 'citas_hoy' && (
                <span className="filter-chip filter-chip--blue">
                  📅 Citas hoy
                  <button onClick={() => setQuickFilter(null)}>✕</button>
                </span>
              )}
              {quickFilter === 'nuevos_hoy' && (
                <span className="filter-chip filter-chip--purple">
                  ⚡ Nuevos hoy
                  <button onClick={() => setQuickFilter(null)}>✕</button>
                </span>
              )}
              {quickFilter === 'sin_asesor' && (
                <span className="filter-chip filter-chip--warning">
                  ⚠️ Sin asesor
                  <button onClick={() => setQuickFilter(null)}>✕</button>
                </span>
              )}
              {searchIntent && searchIntent !== 'all' && (
                <span className="filter-chip">
                  🏠 {searchIntent}
                  <button onClick={() => setSearchIntent('')}>✕</button>
                </span>
              )}
              {searchDateFrom && (
                <span className="filter-chip">
                  📅 Desde {searchDateFrom}
                  <button onClick={() => setSearchDateFrom('')}>✕</button>
                </span>
              )}
              {searchDateTo && (
                <span className="filter-chip">
                  📅 Hasta {searchDateTo}
                  <button onClick={() => setSearchDateTo('')}>✕</button>
                </span>
              )}
            </div>
          )}

          {/* ── Panel de filtros avanzados (colapsable) ── */}
          {filtersOpen && (
            <div className="filters-advanced">
              <div className="filters-grid">
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
              </div>
            </div>
          )}

          {/* ── Resultados + Sort ── */}
          <div className="filter-results-row">
            <span>
              Mostrando {filteredLeads.length} de {leads.length} leads
              {quickFilter && <span className="filter-active-hint"> · filtro activo</span>}
            </span>
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
          {tabCounts.no_intent > 0 && (
            <TabsTrigger value="no_intent" data-testid="tab-no-intent" className="tab-warning">
              ⚠️ Sin intención ({tabCounts.no_intent})
            </TabsTrigger>
          )}
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
              pagedLeads.map((lead) => (
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
                    
                    {/* ── Detalles: siempre 5 filas, altura uniforme ── */}
                    <div className="lead-details" onClick={() => setDrawerPhone(lead.phone)}>

                      {/* Fila 1 — Intención */}
                      <div className="detail-row">
                        <span className="label">{intentIcon(lead.intent)} Intención</span>
                        <span className={`value ${!intentLabel(lead.intent) ? 'value--empty' : ''}`}>
                          {intentLabel(lead.intent) || 'Sin definir'}
                        </span>
                      </div>

                      {/* Fila 2 — Zona */}
                      <div className="detail-row">
                        <span className="label">📍 Zona</span>
                        <span className={`value ${!lead.zone ? 'value--empty' : ''}`}>
                          {lead.zone || '—'}
                        </span>
                      </div>

                      {/* Fila 3 — Presupuesto */}
                      <div className="detail-row">
                        <span className="label">💰 Presupuesto</span>
                        <span className={`value ${!lead.budget_text ? 'value--empty' : ''}`}>
                          {lead.budget_text || '—'}
                        </span>
                      </div>

                      {/* Fila 4 — Score con barra + tooltip */}
                      <div className="detail-row score-row score-tooltip-wrap">
                        <span className="label">📊 Score</span>
                        <div className="score-bar-wrapper">
                          <div
                            className="score-bar-fill"
                            style={{ width: `${Math.round((lead.score / 12) * 100)}%` }}
                            data-score={lead.score}
                          />
                        </div>
                        <span className="score-label">{lead.score}/12</span>
                        <div className="score-tooltip">
                          {getScoreCriteria(lead).map(c => (
                            <div key={c.label} className={`score-tooltip-item ${c.met ? 'met' : 'unmet'}`}>
                              {c.met ? '✅' : '❌'} {c.label}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Fila 5 — Cita */}
                      <div className="detail-row">
                        <span className="label">📅 Cita</span>
                        <span className={`value ${!lead.appointment_datetime ? 'value--empty' : 'value--appointment'}`}>
                          {lead.appointment_datetime ? formatDate(lead.appointment_datetime) : 'Sin cita'}
                        </span>
                      </div>

                    </div>

                    {lead.flow_stage && <FlowStageBar stage={lead.flow_stage} />}

                    <div className="lead-footer">
                      <div className="lead-agent-wrap" onClick={e => e.stopPropagation()}>
                        <button
                          className={`lead-agent-btn ${!lead.assigned_agent_name ? 'lead-agent-btn--unassigned' : ''}`}
                          onClick={e => { e.stopPropagation(); setAssigningPhone(assigningPhone === lead.phone ? null : lead.phone); }}
                          title="Asignar asesor"
                        >
                          👤 {lead.assigned_agent_name || 'Sin asesor'} ▾
                        </button>
                        {assigningPhone === lead.phone && (
                          <div className="agent-dropdown">
                            {agents.filter(a => a.role !== 'admin').length === 0 ? (
                              <span className="agent-dropdown-empty">Sin asesores</span>
                            ) : (
                              agents.filter(a => a.role !== 'admin').map(agent => (
                                <button
                                  key={agent.email}
                                  className={`agent-dropdown-item ${lead.assigned_agent === agent.email ? 'agent-dropdown-item--active' : ''}`}
                                  onClick={e => quickAssign(e, lead.phone, agent.email)}
                                >
                                  {agent.name}
                                </button>
                              ))
                            )}
                          </div>
                        )}
                      </div>
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

          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(1)}
                disabled={currentPage === 1}
              >«</button>
              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >‹</button>

              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter(p => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
                .reduce((acc, p, idx, arr) => {
                  if (idx > 0 && p - arr[idx - 1] > 1) acc.push('...');
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, i) => p === '...'
                  ? <span key={`e${i}`} className="pagination-ellipsis">…</span>
                  : <button
                      key={p}
                      className={`pagination-btn ${currentPage === p ? 'pagination-btn--active' : ''}`}
                      onClick={() => setCurrentPage(p)}
                    >{p}</button>
                )
              }

              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >›</button>
              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(totalPages)}
                disabled={currentPage === totalPages}
              >»</button>

              <span className="pagination-info">
                {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, filteredLeads.length)} de {filteredLeads.length}
              </span>
            </div>
          )}
        </TabsContent>
      </Tabs>

      <LeadDrawer
        phone={drawerPhone}
        onClose={() => setDrawerPhone(null)}
      />
    </div>
  );
}