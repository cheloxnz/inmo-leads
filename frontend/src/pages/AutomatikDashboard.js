import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts';
import {
  Users, DollarSign, TrendingUp, Calendar, AlertCircle,
  RefreshCw, Plus, ChevronRight, Activity
} from 'lucide-react';
import '../styles/AutomatikDashboard.css';

const PLAN_COLOR = { starter: '#6366f1', pro: '#8b5cf6', scale: '#06b6d4', enterprise: '#f59e0b' };
const PLAN_LABEL = { starter: 'Starter $497', pro: 'Pro $997', scale: 'Scale $1.997', enterprise: 'Enterprise $3.997' };
const STATUS_BADGE = {
  active: <span className="ak-badge ak-badge--active">Activo</span>,
  trial: <span className="ak-badge ak-badge--trial">Trial</span>,
  paused: <span className="ak-badge ak-badge--paused">Pausado</span>,
  cancelled: <span className="ak-badge ak-badge--cancelled">Cancelado</span>,
};

function fmt(n) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n || 0);
}

function monthLabel(m) {
  if (!m) return '';
  const [y, mo] = m.split('-');
  const names = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  return `${names[parseInt(mo)]} ${y.slice(2)}`;
}

export default function AutomatikDashboard() {
  const [stats, setStats] = useState(null);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showPlanBreakdown, setShowPlanBreakdown] = useState(true);
  const [showRevTrend, setShowRevTrend] = useState(true);
  const [showUpcoming, setShowUpcoming] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, clientsRes] = await Promise.all([
        axios.get(`${API}/superadmin/clients/dashboard/stats`),
        axios.get(`${API}/superadmin/clients?limit=10`),
      ]);
      setStats(statsRes.data);
      setClients(Array.isArray(clientsRes.data) ? clientsRes.data.slice(0, 8) : []);
    } catch (err) {
      setError('No se pudo cargar el dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) return (
    <div className="ak-loading">
      <div className="ak-spinner" />
      <span>Cargando dashboard…</span>
    </div>
  );

  if (error) return (
    <div className="ak-error">
      <AlertCircle size={20} /> {error}
      <button onClick={fetchAll}><RefreshCw size={14} /> Reintentar</button>
    </div>
  );

  const kpis = [
    {
      label: 'Clientes Activos',
      value: stats?.active_clients ?? 0,
      icon: <Users size={20} />,
      sub: `${stats?.trial_clients ?? 0} en trial`,
      color: '#6366f1',
    },
    {
      label: 'MRR',
      value: fmt(stats?.mrr),
      icon: <DollarSign size={20} />,
      sub: 'Ingreso mensual recurrente',
      color: '#10b981',
    },
    {
      label: 'ARR',
      value: fmt(stats?.arr),
      icon: <TrendingUp size={20} />,
      sub: 'Ingreso anual proyectado',
      color: '#06b6d4',
    },
    {
      label: 'Total Cobrado',
      value: fmt(stats?.total_collected),
      icon: <Activity size={20} />,
      sub: 'Acumulado histórico USD',
      color: '#f59e0b',
    },
    {
      label: 'Vencen en 30 días',
      value: stats?.upcoming_payments_30d ?? 0,
      icon: <Calendar size={20} />,
      sub: 'Cobros próximos',
      color: '#ef4444',
    },
  ];

  const chartData = (stats?.revenue_by_month || []).map(d => ({
    month: monthLabel(d.month),
    revenue: d.revenue,
  }));

  const planData = (stats?.plan_breakdown || []).map(p => ({
    name: PLAN_LABEL[p.plan] || p.plan,
    count: p.count,
    color: PLAN_COLOR[p.plan] || '#6366f1',
  }));

  return (
    <div className="ak-dashboard">
      {/* Header */}
      <div className="ak-header">
        <div>
          <h1 className="ak-title">Dashboard</h1>
          <p className="ak-subtitle">Automatik Media — Vista general de clientes y revenue</p>
        </div>
        <div className="ak-header-actions">
          <button className="ak-btn ak-btn--ghost" onClick={fetchAll}>
            <RefreshCw size={14} /> Actualizar
          </button>
          <a href="/superadmin/clientes" className="ak-btn ak-btn--primary">
            <Plus size={14} /> Nuevo cliente
          </a>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="ak-kpi-grid">
        {kpis.map((k, i) => (
          <div key={i} className="ak-kpi-card" style={{ '--accent': k.color }}>
            <div className="ak-kpi-icon" style={{ background: k.color + '18', color: k.color }}>
              {k.icon}
            </div>
            <div className="ak-kpi-body">
              <div className="ak-kpi-label">{k.label}</div>
              <div className="ak-kpi-value">{k.value}</div>
              <div className="ak-kpi-sub">{k.sub}</div>
            </div>
            <div className="ak-kpi-bar" style={{ background: k.color }} />
          </div>
        ))}
      </div>

      {/* Main layout: chart + sidebar */}
      <div className="ak-main-layout">
        {/* Izquierda: chart + tabla reciente */}
        <div className="ak-left-pane">
          {/* Revenue chart */}
          {showRevTrend && (
            <div className="ak-card">
              <div className="ak-card-header">
                <span className="ak-card-title">Revenue Mensual (USD)</span>
              </div>
              {chartData.length === 0 || chartData.every(d => d.revenue === 0) ? (
                <div className="ak-empty-chart">Registrá pagos para ver el gráfico</div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `$${v.toLocaleString()}`} />
                    <Tooltip formatter={v => [`$${v.toLocaleString('es-AR')}`, 'Revenue']} />
                    <Area type="monotone" dataKey="revenue" stroke="#6366f1" strokeWidth={2} fill="url(#revGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

          {/* Tabla últimos clientes */}
          <div className="ak-card">
            <div className="ak-card-header">
              <span className="ak-card-title">Clientes recientes</span>
              <a href="/superadmin/clientes" className="ak-link">Ver todos <ChevronRight size={14} /></a>
            </div>
            {clients.length === 0 ? (
              <div className="ak-empty">No hay clientes todavía. <a href="/superadmin/clientes">Crear cliente</a></div>
            ) : (
              <table className="ak-table">
                <thead>
                  <tr>
                    <th>Empresa</th>
                    <th>Plan</th>
                    <th>Monto/mes</th>
                    <th>Estado</th>
                    <th>Próx. pago</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map(c => (
                    <tr key={c.client_id}>
                      <td>
                        <div className="ak-client-name">{c.company_name}</div>
                        <div className="ak-client-contact">{c.contact_name}</div>
                      </td>
                      <td>
                        <span className="ak-plan-chip" style={{ background: PLAN_COLOR[c.plan] + '22', color: PLAN_COLOR[c.plan] }}>
                          {c.plan?.toUpperCase()}
                        </span>
                      </td>
                      <td className="ak-amount">{fmt(c.monthly_amount)}</td>
                      <td>{STATUS_BADGE[c.status] || c.status}</td>
                      <td className="ak-date">{c.next_payment_date || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Derecha: sidebar de análisis */}
        <div className="ak-right-pane">
          {/* Toggles de vista */}
          <div className="ak-card ak-analysis-card">
            <div className="ak-card-header">
              <span className="ak-card-title">Análisis rápido</span>
            </div>
            <div className="ak-analysis-toggles">
              {[
                ['Revenue', showRevTrend, setShowRevTrend],
                ['Plan breakdown', showPlanBreakdown, setShowPlanBreakdown],
                ['Próximos cobros', showUpcoming, setShowUpcoming],
              ].map(([label, val, setter]) => (
                <div key={label} className="ak-toggle-row">
                  <span>{label}</span>
                  <button
                    className={`ak-toggle ${val ? 'ak-toggle--on' : ''}`}
                    onClick={() => setter(!val)}
                  >
                    <span className="ak-toggle-knob" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Plan breakdown */}
          {showPlanBreakdown && (
            <div className="ak-card">
              <div className="ak-card-header">
                <span className="ak-card-title">Distribución por plan</span>
              </div>
              {planData.length === 0 ? (
                <div className="ak-empty">Sin clientes activos</div>
              ) : (
                <div className="ak-plan-breakdown">
                  {planData.map(p => (
                    <div key={p.name} className="ak-plan-row">
                      <div className="ak-plan-info">
                        <span className="ak-plan-dot" style={{ background: p.color }} />
                        <span className="ak-plan-name">{p.name}</span>
                      </div>
                      <div className="ak-plan-bar-wrap">
                        <div
                          className="ak-plan-bar"
                          style={{
                            width: `${Math.max(10, (p.count / (stats?.active_clients || 1)) * 100)}%`,
                            background: p.color,
                          }}
                        />
                      </div>
                      <span className="ak-plan-count">{p.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Próximos cobros */}
          {showUpcoming && (
            <div className="ak-card">
              <div className="ak-card-header">
                <span className="ak-card-title">Próximos cobros (30 días)</span>
              </div>
              <UpcomingPayments />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function UpcomingPayments() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/superadmin/clients`)
      .then(res => {
        const today = new Date();
        const in30 = new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000);
        const filtered = (Array.isArray(res.data) ? res.data : [])
          .filter(c => c.status === 'active' && c.next_payment_date)
          .filter(c => {
            const d = new Date(c.next_payment_date);
            return d >= today && d <= in30;
          })
          .sort((a, b) => new Date(a.next_payment_date) - new Date(b.next_payment_date))
          .slice(0, 6);
        setItems(filtered);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="ak-empty">Cargando…</div>;
  if (items.length === 0) return <div className="ak-empty">Sin cobros próximos</div>;

  return (
    <div className="ak-upcoming-list">
      {items.map(c => (
        <div key={c.client_id} className="ak-upcoming-row">
          <div>
            <div className="ak-client-name" style={{ fontSize: 13 }}>{c.company_name}</div>
            <div className="ak-date">{c.next_payment_date}</div>
          </div>
          <span className="ak-amount" style={{ fontSize: 13 }}>
            {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(c.monthly_amount || 0)}
          </span>
        </div>
      ))}
    </div>
  );
}
