import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [filteredLeads, setFilteredLeads] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchLeads();
  }, []);
  
  useEffect(() => {
    filterLeads();
  }, [activeTab, leads]);
  
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
    if (activeTab === 'all') {
      setFilteredLeads(leads);
    } else {
      setFilteredLeads(leads.filter(lead => lead.status === activeTab));
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
        <h1>Leads</h1>
        <p className="subtitle">Gestión y seguimiento de contactos</p>
      </header>
      
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