import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import MetricsCharts from '../components/MetricsCharts';
import UsagePanel from '../components/UsagePanel';
import CoachNudges from '../components/CoachNudges';
import { MessageSquare, TrendingUp, Users, Calendar } from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [emailStats, setEmailStats] = useState(null);
  const [messageStats, setMessageStats] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchStats();
    fetchEmailStats();
    fetchMessageStats();
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

  const fetchMessageStats = async () => {
    try {
      const response = await axios.get(`${API}/metrics/messages?days=30`);
      setMessageStats(response.data);
    } catch (error) {
      console.error('Error fetching message stats:', error);
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

      <CoachNudges />

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

      {/* Métricas de Mensajes */}
      {messageStats && (
        <div className="info-section">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5" />
                Mensajes Procesados (últimos 30 días)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="message-stats-grid">
                <div className="message-stat">
                  <div className="message-stat-value">{messageStats.total_messages || 0}</div>
                  <div className="message-stat-label">Total mensajes</div>
                </div>
                <div className="message-stat">
                  <div className="message-stat-value">{messageStats.incoming_messages || 0}</div>
                  <div className="message-stat-label">Recibidos</div>
                </div>
                <div className="message-stat">
                  <div className="message-stat-value">{messageStats.outgoing_messages || 0}</div>
                  <div className="message-stat-label">Enviados</div>
                </div>
                <div className="message-stat">
                  <div className="message-stat-value">{messageStats.avg_per_day || 0}</div>
                  <div className="message-stat-label">Promedio/día</div>
                </div>
                <div className="message-stat">
                  <div className="message-stat-value">{messageStats.avg_messages_per_lead || 0}</div>
                  <div className="message-stat-label">Promedio/lead</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      
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
        
        {emailStats && (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle>📧 Notificaciones por Email</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="email-stats-grid">
                <div className="email-stat-item">
                  <div className="email-stat-label">Emails Enviados</div>
                  <div className="email-stat-value">{emailStats.total || 0}</div>
                  <div className="email-stat-change">+{emailStats.today || 0} hoy</div>
                </div>
                
                <div className="email-stat-item">
                  <div className="email-stat-label">Tasa de Éxito</div>
                  <div className="email-stat-value">{emailStats.success_rate || 0}%</div>
                  <div className="email-stat-change">{emailStats.successful || 0} exitosos</div>
                </div>
                
                <div className="email-stat-item">
                  <div className="email-stat-label">Esta Semana</div>
                  <div className="email-stat-value">{emailStats.this_week || 0}</div>
                  <div className="email-stat-change">
                    {emailStats.by_type?.hot_lead || 0} leads calientes
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
      
      {/* Uso del mes */}
      <UsagePanel />

      {/* Gráficos de métricas */}
      <MetricsCharts />
    </div>
  );
}