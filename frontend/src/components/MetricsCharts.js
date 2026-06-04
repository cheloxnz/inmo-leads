import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const COLORS = ['#10b981', '#f59e0b', '#6366f1', '#ec4899', '#8b5cf6'];
const STATUS_COLORS = {
  hot: '#ef4444',
  warm: '#f59e0b', 
  cold: '#3b82f6',
  archived: '#6b7280'
};

const STAGE_LABELS = {
  welcome: 'Bienvenida',
  intent: 'Intención',
  name: 'Nombre',
  zone: 'Zona',
  budget: 'Presupuesto',
  rental_details: 'Det. Alquiler',
  property_type: 'Tipo propiedad',
  bedrooms: 'Dormitorios',
  must_have: 'Requisitos',
  urgency: 'Urgencia',
  financing: 'Financiamiento',
  appointment_offer: 'Oferta cita',
  select_day: 'Elige día',
  select_time: 'Elige hora',
  confirmation: 'Confirmación',
  handoff: 'Handoff',
  completed: 'Completado',
};

export default function MetricsCharts() {
  const [leadsByDay, setLeadsByDay] = useState([]);
  const [leadsByStatus, setLeadsByStatus] = useState([]);
  const [leadsByIntent, setLeadsByIntent] = useState([]);
  const [funnel, setFunnel] = useState(null);
  const [funnelByStage, setFunnelByStage] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    try {
      const [byDay, byStatus, byIntent, funnelData, byStage] = await Promise.all([
        axios.get(`${API}/metrics/leads-by-day?days=14`),
        axios.get(`${API}/metrics/leads-by-status`),
        axios.get(`${API}/metrics/leads-by-intent`),
        axios.get(`${API}/metrics/conversion-funnel`),
        axios.get(`${API}/metrics/funnel-by-stage`),
      ]);

      setLeadsByDay(Array.isArray(byDay.data) ? byDay.data : []);
      setLeadsByStatus(Array.isArray(byStatus.data) ? byStatus.data : []);
      setLeadsByIntent(Array.isArray(byIntent.data) ? byIntent.data : []);
      setFunnel(funnelData.data);
      setFunnelByStage(byStage.data);
    } catch (error) {
      console.error('Error fetching metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' });
  };

  const getStatusLabel = (status) => {
    const labels = { hot: 'Caliente', warm: 'Tibio', cold: 'Frío', archived: 'Archivado', completed: 'Completado', new: 'Nuevo', contacted: 'Contactado', qualified: 'Calificado', appointment: 'Cita' };
    return labels[status] || status;
  };

  const getIntentLabel = (intent) => {
    const labels = { 
      comprar: 'Comprar', 
      alquilar: 'Alquilar', 
      inversion: 'Inversión',
      sin_definir: 'Sin definir'
    };
    return labels[intent] || intent;
  };

  if (loading) {
    return <div className="loading-container">Cargando métricas...</div>;
  }

  return (
    <div className="metrics-container" data-testid="metrics-charts">
      {/* Funnel de conversión */}
      {funnel && (
        <Card className="funnel-card">
          <CardHeader>
            <CardTitle>Funnel de Conversión</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="funnel-metrics">
              <div className="funnel-step">
                <div className="funnel-value">{funnel.total_leads}</div>
                <div className="funnel-label">Total Leads</div>
                <div className="funnel-rate">100%</div>
              </div>
              <div className="funnel-arrow">→</div>
              <div className="funnel-step">
                <div className="funnel-value">{funnel.qualified}</div>
                <div className="funnel-label">Calificados</div>
                <div className="funnel-rate">{funnel.qualification_rate}%</div>
              </div>
              <div className="funnel-arrow">→</div>
              <div className="funnel-step">
                <div className="funnel-value">{funnel.with_appointment}</div>
                <div className="funnel-label">Con Cita</div>
                <div className="funnel-rate">{funnel.appointment_rate}%</div>
              </div>
              <div className="funnel-arrow">→</div>
              <div className="funnel-step highlight">
                <div className="funnel-value">{funnel.hot_leads}</div>
                <div className="funnel-label">Hot Leads</div>
                <div className="funnel-rate">{funnel.conversion_rate}%</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Funnel por stage del bot */}
      {funnelByStage && funnelByStage.total > 0 && (
        <Card className="funnel-card" style={{ marginTop: 16 }}>
          <CardHeader>
            <CardTitle>Dónde se pierden los leads (por etapa del bot)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={funnelByStage.stages.filter(s => s.count > 0)}
                layout="vertical"
                margin={{ left: 10, right: 30 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis type="number" stroke="#9ca3af" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="stage"
                  tickFormatter={(s) => STAGE_LABELS[s] || s}
                  stroke="#9ca3af"
                  fontSize={11}
                  width={110}
                />
                <Tooltip
                  formatter={(value, _name, props) => [
                    `${value} leads (${props.payload.pct}%)`,
                    'Leads en esta etapa',
                  ]}
                  labelFormatter={(s) => STAGE_LABELS[s] || s}
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151' }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {funnelByStage.stages.filter(s => s.count > 0).map((entry, index) => (
                    <Cell
                      key={entry.stage}
                      fill={entry.stage === 'completed' ? '#10b981' : entry.stage === 'handoff' ? '#6366f1' : COLORS[index % COLORS.length]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 8, textAlign: 'center' }}>
              Total: {funnelByStage.total} leads · Las barras muestran cuántos leads están actualmente en cada etapa
            </div>
          </CardContent>
        </Card>
      )}

      <div className="charts-grid">
        {/* Leads por día */}
        <Card className="chart-card">
          <CardHeader>
            <CardTitle>Leads Últimos 14 Días</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={leadsByDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={formatDate}
                  stroke="#9ca3af"
                  fontSize={12}
                />
                <YAxis stroke="#9ca3af" fontSize={12} />
                <Tooltip 
                  labelFormatter={formatDate}
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="count" 
                  stroke="#10b981" 
                  strokeWidth={2}
                  dot={{ fill: '#10b981' }}
                  name="Leads"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Leads por estado */}
        <Card className="chart-card">
          <CardHeader>
            <CardTitle>Distribución por Estado</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={leadsByStatus}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="count"
                  nameKey="status"
                  label={({ status, count }) => `${getStatusLabel(status)}: ${count}`}
                  labelLine={false}
                >
                  {leadsByStatus.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={STATUS_COLORS[entry.status] || COLORS[index % COLORS.length]} 
                    />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value, name) => [value, getStatusLabel(name)]}
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Leads por intención */}
        <Card className="chart-card">
          <CardHeader>
            <CardTitle>Leads por Intención</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={leadsByIntent} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis type="number" stroke="#9ca3af" fontSize={12} />
                <YAxis 
                  type="category" 
                  dataKey="intent" 
                  tickFormatter={getIntentLabel}
                  stroke="#9ca3af"
                  fontSize={12}
                  width={80}
                />
                <Tooltip 
                  formatter={(value) => [value, 'Leads']}
                  labelFormatter={getIntentLabel}
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151' }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
