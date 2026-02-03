import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export default function LeadDetail() {
  const { phone } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchLead();
  }, [phone]);
  
  const fetchLead = async () => {
    try {
      const response = await axios.get(`${API}/leads/${phone}`);
      setLead(response.data);
    } catch (error) {
      console.error('Error fetching lead:', error);
    } finally {
      setLoading(false);
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
            </div>
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
      </div>
    </div>
  );
}