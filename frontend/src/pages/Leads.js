import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [filteredLeads, setFilteredLeads] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(true);
  const [searchName, setSearchName] = useState('');
  const [searchZone, setSearchZone] = useState('');
  const [searchDateFrom, setSearchDateFrom] = useState('');
  const [searchDateTo, setSearchDateTo] = useState('');
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchLeads();
  }, []);
  
  useEffect(() => {
    filterLeads();
  }, [activeTab, leads, searchName, searchZone, searchDateFrom, searchDateTo]);
  
  const fetchLeads = async () => {
    try {
      const response = await axios.get(`${API}/leads`);
      setLeads(response.data);
    } catch (error) {
      console.error('Error fetching leads:', error);
    } finally {
      setLoading(false);
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
        <Button onClick={exportToCSV} variant="outline" data-testid="btn-export-csv">
          📥 Exportar CSV ({filteredLeads.length})
        </Button>
      </header>
      
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
                  className="lead-card"
                  onClick={() => navigate(`/leads/${lead.phone}`)}
                  data-testid={`lead-card-${lead.phone}`}
                >
                  <CardContent className="lead-card-content">
                    <div className="lead-header">
                      <div>
                        <h3>{lead.name || 'Sin nombre'}</h3>
                        <p className="lead-phone">{lead.phone}</p>
                      </div>
                      {getStatusBadge(lead.status)}
                    </div>
                    
                    <div className="lead-details">
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
                      
                      <div className="detail-row">
                        <span className="label">Score:</span>
                        <span className="value score">{lead.score}/12</span>
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