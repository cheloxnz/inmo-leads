import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { toast } from 'sonner';
import { Plus, Trash2, Edit2, X, RefreshCw, Download, RepeatIcon } from 'lucide-react';
import '../styles/AutomatikDashboard.css';

const CATEGORIES = [
  { id: 'ia',             label: '🤖 IA',              color: '#6366f1' },
  { id: 'herramientas',   label: '🛠️ Herramientas',    color: '#0ea5e9' },
  { id: 'ads',            label: '📣 Publicidad',       color: '#f59e0b' },
  { id: 'infraestructura',label: '🖥️ Infraestructura',  color: '#10b981' },
  { id: 'equipo',         label: '👥 Equipo',           color: '#8b5cf6' },
  { id: 'otro',           label: '📦 Otro',             color: '#9ca3af' },
];

const CAT_MAP = Object.fromEntries(CATEGORIES.map(c => [c.id, c]));

function currentPeriod() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function last12Periods() {
  const periods = [];
  const d = new Date();
  for (let i = 0; i < 12; i++) {
    const m = d.getMonth() - i;
    const y = d.getFullYear() + Math.floor(m / 12);
    const month = ((m % 12) + 12) % 12;
    periods.push(`${y}-${String(month + 1).padStart(2, '0')}`);
  }
  return periods;
}

function fmtMoney(amount, currency = 'USD') {
  return currency === 'USD'
    ? `$${Number(amount).toLocaleString('es-AR', { minimumFractionDigits: 0 })}`
    : `$${Number(amount).toLocaleString('es-AR', { minimumFractionDigits: 0 })} ARS`;
}

const EMPTY_FORM = { name: '', category: 'herramientas', amount: '', currency: 'USD', period: currentPeriod(), date: new Date().toISOString().split('T')[0], recurrent: false, notes: '' };

export default function GastosPage() {
  const [expenses, setExpenses]     = useState([]);
  const [loading, setLoading]       = useState(true);
  const [period, setPeriod]         = useState(currentPeriod());
  const [filterCat, setFilterCat]   = useState('');
  const [showModal, setShowModal]   = useState(false);
  const [editingId, setEditingId]   = useState(null);
  const [form, setForm]             = useState(EMPTY_FORM);
  const [saving, setSaving]         = useState(false);
  const [replicating, setReplicating] = useState(false);

  const fetchExpenses = useCallback(async () => {
    setLoading(true);
    try {
      const params = { period };
      if (filterCat) params.category = filterCat;
      const res = await axios.get(`${API}/superadmin/clients/expenses`, { params });
      setExpenses(res.data);
    } catch {
      toast.error('Error cargando gastos');
    } finally {
      setLoading(false);
    }
  }, [period, filterCat]);

  useEffect(() => { fetchExpenses(); }, [fetchExpenses]);

  // ── KPIs ──────────────────────────────────────────────────────────────────
  const totalUSD = expenses.filter(e => e.currency === 'USD').reduce((s, e) => s + e.amount, 0);
  const totalARS = expenses.filter(e => e.currency === 'ARS').reduce((s, e) => s + e.amount, 0);
  const byCategory = CATEGORIES.map(c => ({
    ...c,
    total: expenses.filter(e => e.category === c.id && e.currency === 'USD').reduce((s, e) => s + e.amount, 0),
  })).filter(c => c.total > 0);

  // ── Formulario ─────────────────────────────────────────────────────────────
  const openNew = () => {
    setForm({ ...EMPTY_FORM, period });
    setEditingId(null);
    setShowModal(true);
  };

  const openEdit = (exp) => {
    setForm({
      name: exp.name,
      category: exp.category,
      amount: exp.amount,
      currency: exp.currency,
      period: exp.period,
      date: exp.date,
      recurrent: exp.recurrent || false,
      notes: exp.notes || '',
    });
    setEditingId(exp.expense_id);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.name || !form.amount) return toast.error('Nombre y monto son obligatorios');
    setSaving(true);
    try {
      if (editingId) {
        const res = await axios.put(`${API}/superadmin/clients/expenses/${editingId}`, form);
        setExpenses(prev => prev.map(e => e.expense_id === editingId ? res.data : e));
        toast.success('Gasto actualizado');
      } else {
        const res = await axios.post(`${API}/superadmin/clients/expenses`, form);
        setExpenses(prev => [res.data, ...prev]);
        toast.success('Gasto registrado');
      }
      setShowModal(false);
    } catch {
      toast.error('Error guardando gasto');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (exp) => {
    if (!window.confirm(`¿Eliminás "${exp.name}"?`)) return;
    try {
      await axios.delete(`${API}/superadmin/clients/expenses/${exp.expense_id}`);
      setExpenses(prev => prev.filter(e => e.expense_id !== exp.expense_id));
      toast.success('Gasto eliminado');
    } catch {
      toast.error('Error eliminando gasto');
    }
  };

  const handleReplicate = async () => {
    setReplicating(true);
    try {
      const res = await axios.post(`${API}/superadmin/clients/expenses/replicate-recurrent`, null, {
        params: { target_period: period },
      });
      toast.success(`${res.data.copied} gasto(s) recurrente(s) copiados`);
      fetchExpenses();
    } catch {
      toast.error('Error replicando gastos recurrentes');
    } finally {
      setReplicating(false);
    }
  };

  const exportCSV = () => {
    const rows = [
      ['Nombre', 'Categoría', 'Monto', 'Moneda', 'Período', 'Fecha', 'Recurrente', 'Notas'],
      ...expenses.map(e => [e.name, CAT_MAP[e.category]?.label || e.category, e.amount, e.currency, e.period, e.date, e.recurrent ? 'Sí' : 'No', e.notes || '']),
    ];
    const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `gastos-${period}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="ak-dashboard">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Gastos</h1>
          <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0', fontSize: 14 }}>
            Control de costos operativos mensuales
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="ak-btn ak-btn-ghost ak-btn-sm" onClick={exportCSV} title="Exportar CSV">
            <Download size={14} /> CSV
          </button>
          <button className="ak-btn ak-btn-ghost ak-btn-sm" onClick={handleReplicate} disabled={replicating} title="Copiar gastos recurrentes del mes anterior">
            <RepeatIcon size={14} /> {replicating ? 'Copiando...' : 'Replicar recurrentes'}
          </button>
          <button className="ak-btn ak-btn-ghost ak-btn-sm" onClick={fetchExpenses}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
          <button className="ak-btn ak-btn-primary ak-btn-sm" onClick={openNew}>
            <Plus size={14} /> Nuevo gasto
          </button>
        </div>
      </div>

      {/* Filtros de período y categoría */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <select
          className="ak-input"
          style={{ width: 160 }}
          value={period}
          onChange={e => setPeriod(e.target.value)}
        >
          {last12Periods().map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button
            className="ak-btn ak-btn-sm"
            style={{ background: !filterCat ? '#6366f1' : '#f3f4f6', color: !filterCat ? '#fff' : '#374151' }}
            onClick={() => setFilterCat('')}
          >Todos</button>
          {CATEGORIES.map(c => (
            <button
              key={c.id}
              className="ak-btn ak-btn-sm"
              style={{ background: filterCat === c.id ? c.color : '#f3f4f6', color: filterCat === c.id ? '#fff' : '#374151' }}
              onClick={() => setFilterCat(filterCat === c.id ? '' : c.id)}
            >{c.label}</button>
          ))}
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="ak-kpi-card" style={{ minWidth: 150 }}>
          <div className="ak-kpi-content">
            <span className="ak-kpi-label">Total USD</span>
            <span className="ak-kpi-value" style={{ color: '#dc2626' }}>{fmtMoney(totalUSD)}</span>
          </div>
        </div>
        {totalARS > 0 && (
          <div className="ak-kpi-card" style={{ minWidth: 150 }}>
            <div className="ak-kpi-content">
              <span className="ak-kpi-label">Total ARS</span>
              <span className="ak-kpi-value" style={{ color: '#d97706' }}>{fmtMoney(totalARS, 'ARS')}</span>
            </div>
          </div>
        )}
        {byCategory.map(c => (
          <div key={c.id} className="ak-kpi-card" style={{ minWidth: 130 }}>
            <div className="ak-kpi-content">
              <span className="ak-kpi-label">{c.label}</span>
              <span className="ak-kpi-value" style={{ color: c.color }}>{fmtMoney(c.total)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Tabla */}
      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>Cargando...</div>
      ) : expenses.length === 0 ? (
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>
          <p style={{ fontSize: 32, marginBottom: 8 }}>💸</p>
          <p>No hay gastos registrados para {period}</p>
          <button className="ak-btn ak-btn-primary ak-btn-sm" style={{ marginTop: 12 }} onClick={openNew}>
            + Registrar primer gasto
          </button>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border-color)', textAlign: 'left' }}>
                {['Nombre', 'Categoría', 'Monto', 'Moneda', 'Fecha', 'Recurrente', 'Notas', ''].map(h => (
                  <th key={h} style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--text-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {expenses.map(exp => {
                const cat = CAT_MAP[exp.category] || CAT_MAP.otro;
                return (
                  <tr key={exp.expense_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '10px 12px', fontWeight: 600 }}>{exp.name}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ background: cat.color + '18', color: cat.color, padding: '2px 8px', borderRadius: 20, fontSize: 12, fontWeight: 600 }}>
                        {cat.label}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 700, color: '#dc2626' }}>{fmtMoney(exp.amount, exp.currency)}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>{exp.currency}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>{exp.date}</td>
                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      {exp.recurrent ? <span title="Recurrente" style={{ color: '#6366f1' }}>🔁</span> : <span style={{ color: '#d1d5db' }}>—</span>}
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{exp.notes || '—'}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button className="ak-btn ak-btn-ghost ak-btn-icon" onClick={() => openEdit(exp)} title="Editar"><Edit2 size={13} /></button>
                        <button className="ak-btn ak-btn-ghost ak-btn-icon" style={{ color: '#dc2626' }} onClick={() => handleDelete(exp)} title="Eliminar"><Trash2 size={13} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal nuevo/editar */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div style={{ background: 'var(--card-bg, #fff)', borderRadius: 16, padding: 28, width: '100%', maxWidth: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <h3 style={{ fontWeight: 700, fontSize: 16, margin: 0 }}>{editingId ? 'Editar gasto' : 'Nuevo gasto'}</h3>
              <button className="ak-btn ak-btn-ghost ak-btn-icon" onClick={() => setShowModal(false)}><X size={15} /></button>
            </div>

            <div style={{ display: 'grid', gap: 12 }}>
              <div>
                <label className="ak-label">Nombre *</label>
                <input className="ak-input" placeholder="ej: ChatGPT Plus, Meta Ads Junio..." value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="ak-label">Categoría</label>
                  <select className="ak-input" value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                    {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="ak-label">Moneda</label>
                  <select className="ak-input" value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}>
                    <option value="USD">USD</option>
                    <option value="ARS">ARS</option>
                  </select>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="ak-label">Monto *</label>
                  <input className="ak-input" type="number" placeholder="0" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} />
                </div>
                <div>
                  <label className="ak-label">Fecha</label>
                  <input className="ak-input" type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="ak-label">Período (YYYY-MM)</label>
                <select className="ak-input" value={form.period} onChange={e => setForm(f => ({ ...f, period: e.target.value }))}>
                  {last12Periods().map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="ak-label">Notas</label>
                <input className="ak-input" placeholder="Opcional" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', userSelect: 'none' }}>
                <input type="checkbox" checked={form.recurrent} onChange={e => setForm(f => ({ ...f, recurrent: e.target.checked }))} style={{ width: 16, height: 16 }} />
                <span style={{ fontSize: 13 }}>🔁 Gasto recurrente (se copia automáticamente cada mes)</span>
              </label>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 24, justifyContent: 'flex-end' }}>
              <button className="ak-btn ak-btn-ghost" onClick={() => setShowModal(false)}>Cancelar</button>
              <button className="ak-btn ak-btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Guardando...' : editingId ? 'Guardar cambios' : 'Registrar gasto'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
