import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import MetricsCharts from '../components/MetricsCharts';
import UsagePanel from '../components/UsagePanel';
import CoachNudges from '../components/CoachNudges';
import CoachCelebrations from '../components/CoachCelebrations';
import PremiumFeaturesShowcase from '../components/PremiumFeaturesShowcase';
import ROICard from '../components/ROICard';
import { MessageSquare, TrendingUp, Users, Calendar } from 'lucide-react';
import { motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, delay: i * 0.07, ease: [0.4, 0, 0.2, 1] }
  })
};

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
      <motion.header
        className="page-header"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      >
        <div>
          <h1>Dashboard</h1>
          <p className="subtitle">Métricas y estadísticas en tiempo real</p>
        </div>
      </motion.header>

      <CoachCelebrations />
      <CoachNudges />

      {/* ROI Hero Card */}
      <motion.div variants={fadeUp} initial="hidden" animate="visible" custom={0}>
        <ROICard />
      </motion.div>

      <div className="stats-grid">
        {[
          { testid: 'stat-total-leads', label: 'Total Leads', value: stats?.total || 0, change: `+${stats?.today || 0} hoy`, className: '' },
          { testid: 'stat-hot-leads', label: '🔥 Leads Calientes', value: stats?.hot || 0, change: `${stats?.conversion_rate || 0}% conversión`, className: 'hot' },
          { testid: 'stat-warm-leads', label: '🟡 Leads Tibios', value: stats?.warm || 0, change: null, className: 'warm' },
          { testid: 'stat-cold-leads', label: '❄️ Leads Fríos', value: stats?.cold || 0, change: null, className: 'cold' },
          { testid: 'stat-appointments', label: '📅 Citas Agendadas', value: stats?.with_appointment || 0, change: null, className: '' },
          { testid: 'stat-avg-score', label: '⭐ Score Promedio', value: stats?.avg_score || 0, change: 'de 12 puntos', className: '' },
        ].map((card, i) => (
          <motion.div key={card.testid} variants={fadeUp} initial="hidden" animate="visible" custom={i + 1}>
            <Card className={`stat-card ${card.className}`} data-testid={card.testid}>
              <CardHeader>
                <CardTitle className="stat-label">{card.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="stat-value">{card.value}</div>
                {card.change && <div className="stat-change">{card.change}</div>}
              </CardContent>
            </Card>
          </motion.div>
        ))}
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

      {/* Premium Features showcase */}
      <PremiumFeaturesShowcase />

      {/* Gráficos de métricas */}
      <MetricsCharts />
    </div>
  );
}