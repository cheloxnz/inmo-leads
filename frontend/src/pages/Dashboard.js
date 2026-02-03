import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [emailStats, setEmailStats] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchStats();
    fetchEmailStats();
  }, []);
  
  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/leads/stats/summary`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const fetchEmailStats = async () => {
    try {
      const response = await axios.get(`${API}/email-stats`);
      setEmailStats(response.data);
    } catch (error) {
      console.error('Error fetching email stats:', error);
    }
  };
  
  if (loading) {
    return <div className="loading-container">Cargando...</div>;
  }
  
  return (
    <div className="page-container" data-testid="dashboard-page">
      <header className="page-header">
        <h1>Dashboard</h1>
        <p className="subtitle">Métricas y estadísticas en tiempo real</p>
      </header>
      
      <div className="stats-grid">
        <Card className="stat-card" data-testid="stat-total-leads">
          <CardHeader>
            <CardTitle className="stat-label">Total Leads</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{stats?.total || 0}</div>
            <div className="stat-change">+{stats?.today || 0} hoy</div>
          </CardContent>
        </Card>
        
        <Card className="stat-card hot" data-testid="stat-hot-leads">
          <CardHeader>
            <CardTitle className="stat-label">🔥 Leads Calientes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{stats?.hot || 0}</div>
            <div className="stat-change">{stats?.conversion_rate || 0}% conversión</div>
          </CardContent>
        </Card>
        
        <Card className="stat-card warm" data-testid="stat-warm-leads">
          <CardHeader>
            <CardTitle className="stat-label">🟡 Leads Tibios</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{stats?.warm || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="stat-card cold" data-testid="stat-cold-leads">
          <CardHeader>
            <CardTitle className="stat-label">❄️ Leads Fríos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{stats?.cold || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="stat-card" data-testid="stat-appointments">
          <CardHeader>
            <CardTitle className="stat-label">📅 Citas Agendadas</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{stats?.with_appointment || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="stat-card" data-testid="stat-avg-score">
          <CardHeader>
            <CardTitle className="stat-label">⭐ Score Promedio</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{stats?.avg_score || 0}</div>
            <div className="stat-change">de 12 puntos</div>
          </CardContent>
        </Card>
      </div>
      
      <div className="info-section">
        <Card>
          <CardHeader>
            <CardTitle>Estado del Sistema</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="system-status">
              <div className="status-item">
                <div className="status-indicator-dot active"></div>
                <div>
                  <div className="status-name">WhatsApp Bot</div>
                  <div className="status-description">Respondiendo mensajes 24/7</div>
                </div>
              </div>
              
              <div className="status-item">
                <div className="status-indicator-dot active"></div>
                <div>
                  <div className="status-name">LLM (GPT-4o)</div>
                  <div className="status-description">Procesamiento de lenguaje natural activo</div>
                </div>
              </div>
              
              <div className="status-item">
                <div className="status-indicator-dot active"></div>
                <div>
                  <div className="status-name">Scoring Engine</div>
                  <div className="status-description">Calificación automática funcionando</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}