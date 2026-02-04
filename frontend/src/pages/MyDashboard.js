import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export default function MyDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState(null);
  const [myLeads, setMyLeads] = useState([]);
  const [upcomingAppointments, setUpcomingAppointments] = useState([]);
  const [inactiveLeads, setInactiveLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [metricsRes, leadsRes, appointmentsRes, inactiveRes] = await Promise.all([
        axios.get(`${API}/metrics/agent/${user.email}`),
        axios.get(`${API}/leads/assigned-to-me?limit=10`),
        axios.get(`${API}/notifications/upcoming-appointments`),
        axios.get(`${API}/notifications/inactive-leads`)
      ]);

      setMetrics(metricsRes.data);
      setMyLeads(leadsRes.data);
      setUpcomingAppointments(appointmentsRes.data);
      setInactiveLeads(inactiveRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
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
    return new Date(dateString).toLocaleString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return <div className="loading-container">Cargando tu dashboard...</div>;
  }

  return (
    <div className="page-container" data-testid="my-dashboard">
      <header className="page-header">
        <div>
          <h1>Mi Dashboard</h1>
          <p className="subtitle">Bienvenido, {user?.name || 'Asesor'}</p>
        </div>
      </header>

      {/* Métricas personales */}
      <div className="stats-grid">
        <Card className="stat-card">
          <CardHeader>
            <CardTitle className="stat-label">Leads Activos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{metrics?.active_leads || 0}</div>
            <div className="stat-change">de {metrics?.max_concurrent_leads || 15} max</div>
          </CardContent>
        </Card>

        <Card className="stat-card">
          <CardHeader>
            <CardTitle className="stat-label">Total Asignados</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{metrics?.total_assigned || 0}</div>
          </CardContent>
        </Card>

        <Card className="stat-card">
          <CardHeader>
            <CardTitle className="stat-label">Con Cita</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{metrics?.with_appointment || 0}</div>
          </CardContent>
        </Card>

        <Card className="stat-card">
          <CardHeader>
            <CardTitle className="stat-label">Tasa de Conversión</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{metrics?.conversion_rate || 0}%</div>
          </CardContent>
        </Card>

        <Card className="stat-card">
          <CardHeader>
            <CardTitle className="stat-label">Score Promedio</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="stat-value">{metrics?.avg_score || 0}</div>
            <div className="stat-change">de 12 puntos</div>
          </CardContent>
        </Card>
      </div>

      <div className="dashboard-grid">
        {/* Citas próximas */}
        <Card className="dashboard-card">
          <CardHeader>
            <CardTitle>⏰ Citas Próximas (1h)</CardTitle>
          </CardHeader>
          <CardContent>
            {upcomingAppointments.length === 0 ? (
              <div className="empty-state-small">
                <p>No hay citas próximas</p>
              </div>
            ) : (
              <div className="appointment-list">
                {upcomingAppointments.map(lead => (
                  <div 
                    key={lead.phone} 
                    className="appointment-item"
                    onClick={() => navigate(`/leads/${lead.phone}`)}
                  >
                    <div className="appointment-info">
                      <span className="name">{lead.name || 'Sin nombre'}</span>
                      <span className="time">{formatDate(lead.appointment_datetime)}</span>
                    </div>
                    <Badge variant="outline">{lead.appointment_type}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Leads inactivos */}
        <Card className="dashboard-card">
          <CardHeader>
            <CardTitle>🟡 Leads Sin Actividad (3+ días)</CardTitle>
          </CardHeader>
          <CardContent>
            {inactiveLeads.length === 0 ? (
              <div className="empty-state-small">
                <p>Todos tus leads están activos</p>
              </div>
            ) : (
              <div className="inactive-list">
                {inactiveLeads.slice(0, 5).map(lead => (
                  <div 
                    key={lead.phone} 
                    className="inactive-item"
                    onClick={() => navigate(`/leads/${lead.phone}`)}
                  >
                    <div className="lead-info">
                      <span className="name">{lead.name || 'Sin nombre'}</span>
                      <span className="zone">{lead.zone || 'Sin zona'}</span>
                    </div>
                    <Button size="sm" variant="outline">Contactar</Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Mis leads recientes */}
      <Card className="mt-6">
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Mis Leads Recientes</CardTitle>
            <Button variant="ghost" onClick={() => navigate('/my-leads')}>
              Ver todos →
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {myLeads.length === 0 ? (
            <div className="empty-state">
              <p>No tienes leads asignados aún</p>
            </div>
          ) : (
            <div className="leads-table">
              <table>
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Teléfono</th>
                    <th>Zona</th>
                    <th>Intención</th>
                    <th>Estado</th>
                    <th>Último contacto</th>
                  </tr>
                </thead>
                <tbody>
                  {myLeads.map(lead => (
                    <tr 
                      key={lead.phone} 
                      onClick={() => navigate(`/leads/${lead.phone}`)}
                      className="cursor-pointer hover:bg-gray-50"
                    >
                      <td>{lead.name || 'Sin nombre'}</td>
                      <td>{lead.phone}</td>
                      <td>{lead.zone || '-'}</td>
                      <td>{lead.intent || '-'}</td>
                      <td>{getStatusBadge(lead.status)}</td>
                      <td>{formatDate(lead.last_message_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
