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
  const [selectedLeads, setSelectedLeads] = useState([]);
  const [bulkAction, setBulkAction] = useState('');
  const [bulkValue, setBulkValue] = useState('');
  const [agents, setAgents] = useState([]);
  const [processingBulk, setProcessingBulk] = useState(false);
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchLeads();
    fetchAgents();
  }, [filterByAgent]);
  
  useEffect(() => {
    filterLeads();
  }, [activeTab, leads, searchName, searchZone, searchDateFrom, searchDateTo, searchIntent]);
  
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
    
    setFilteredLeads(filtered);
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
          
          <div className="filter-results">
            Mostrando {filteredLeads.length} de {leads.length} leads
          </div>
        </CardContent>
      </Card>
      
      <Tabs value={activeTab} onValueChange={setActiveTab} className="leads-tabs">
        <TabsList>
          <TabsTrigger value="all" data-testid="tab-all">Todos ({leads.length})</TabsTrigger>
          <TabsTrigger value="hot" data-testid="tab-hot">Calientes ({leads.filter(l => l.status === 'hot').length})</TabsTrigger>
          <TabsTrigger value="warm" data-testid="tab-warm">Tibios ({leads.filter(l => l.status === 'warm').length})</TabsTrigger>
          <TabsTrigger value="cold" data-testid="tab-cold">Fríos ({leads.filter(l => l.status === 'cold').length})</TabsTrigger>
        </TabsList>
        
        <TabsContent value={activeTab}>
          <div className="leads-grid">
            {filteredLeads.length === 0 ? (
              <div className="empty-state">
                <p>No hay leads en esta categoría</p>
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
                        <div onClick={() => navigate(`/leads/${lead.phone}`)} className="lead-info-clickable">
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
                    
                    <div className="lead-details" onClick={() => navigate(`/leads/${lead.phone}`)}>
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
                    
                    <div className="lead-footer">
                      <span className="created-date">
                        Creado: {formatDate(lead.created_at)}
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
    </div>
  );
}