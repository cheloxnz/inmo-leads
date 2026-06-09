import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { toast } from 'sonner';
import {
  Search, Plus, Download, FileText, X, Save, Filter,
  DollarSign, TrendingUp, Clock, CheckCircle, Trash2
} from 'lucide-react';
import '../styles/AutomatikDashboard.css';

const METHODS = ['transfer', 'stripe', 'mercadopago', 'cash'];
const METHOD_LABEL = {
  transfer: 'Transferencia',
  stripe: 'Stripe',
  mercadopago: 'MercadoPago',
  cash: 'Efectivo',
};
const METHOD_COLOR = {
  transfer: '#6366f1',
  stripe: '#635bff',
  mercadopago: '#009ee3',
  cash: '#10b981',
};
const STATUS_LABEL = { paid: 'Pagado', pending: 'Pendiente', failed: 'Fallido' };
const STATUS_COLOR = { paid: '#10b981', pending: '#f59e0b', failed: '#ef4444' };

function fmt(n) {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0,
  }).format(n || 0);
}

function fmtDate(str) {
  if (!str) return '—';
  const [y, m, d] = str.split('-');
  return `${d}/${m}/${y}`;
}

function currentPeriod() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function monthOptions() {
  const opts = [];
  const now = new Date();
  for (let i = 0; i < 12; i++) {
    let m = now.getMonth() - i;
    let y = now.getFullYear();
    while (m < 0) { m += 12; y -= 1; }
    const val = `${y}-${String(m + 1).padStart(2, '0')}`;
    const label = new Date(y, m, 1).toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });
    opts.push({ val, label });
  }
  return opts;
}

const EMPTY_PAYMENT = {
  client_id: '', amount: '', currency: 'USD',
  payment_date: new Date().toISOString().slice(0, 10),
  method: 'transfer', status: 'paid',
  period: currentPeriod(), notes: '',
};

// ── Generador de PDF/Factura ──────────────────────────────────────────────────
function printInvoice(payment) {
  const html = `
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Recibo #${payment.payment_id?.slice(0, 8).toUpperCase()}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Arial, sans-serif; color: #1a1a2e; padding: 40px; }
    .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; }
    .brand { font-size: 24px; font-weight: 800; color: #6366f1; letter-spacing: -0.5px; }
    .brand span { color: #1a1a2e; }
    .badge { background: #10b981; color: white; padding: 4px 12px; border-radius: 99px; font-size: 13px; font-weight: 600; }
    .badge.pending { background: #f59e0b; }
    .badge.failed { background: #ef4444; }
    h1 { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
    .subtitle { color: #6b7280; font-size: 14px; }
    .divider { border: none; border-top: 2px solid #e5e7eb; margin: 24px 0; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }
    .field label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #9ca3af; font-weight: 600; }
    .field p { font-size: 15px; font-weight: 500; margin-top: 2px; }
    .amount-box { background: #f3f4f6; border-radius: 12px; padding: 24px; text-align: center; margin: 24px 0; }
    .amount-box .label { font-size: 13px; color: #6b7280; margin-bottom: 4px; }
    .amount-box .value { font-size: 42px; font-weight: 800; color: #6366f1; }
    .amount-box .currency { font-size: 18px; font-weight: 600; color: #9ca3af; }
    .footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #e5e7eb; text-align: center; color: #9ca3af; font-size: 12px; }
    @media print { body { padding: 20px; } }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="brand">Automatik<span> Media</span></div>
      <div class="subtitle" style="margin-top:4px">Suite IA para Inmobiliarias</div>
    </div>
    <span class="badge ${payment.status !== 'paid' ? payment.status : ''}">
      ${STATUS_LABEL[payment.status] || payment.status}
    </span>
  </div>

  <h1>Comprobante de Pago</h1>
  <p class="subtitle">Recibo #${payment.payment_id?.slice(0, 8).toUpperCase() || '—'}</p>
  <hr class="divider" />

  <div class="amount-box">
    <div class="label">IMPORTE TOTAL</div>
    <div class="value">${payment.currency === 'USD' ? 'USD' : '$'} ${Number(payment.amount || 0).toLocaleString('es-AR')}</div>
  </div>

  <div class="grid">
    <div class="field">
      <label>Cliente</label>
      <p>${payment.company_name || '—'}</p>
    </div>
    <div class="field">
      <label>Período</label>
      <p>${payment.period || '—'}</p>
    </div>
    <div class="field">
      <label>Fecha de Pago</label>
      <p>${fmtDate(payment.payment_date)}</p>
    </div>
    <div class="field">
      <label>Método de Pago</label>
      <p>${METHOD_LABEL[payment.method] || payment.method || '—'}</p>
    </div>
    <div class="field">
      <label>Moneda</label>
      <p>${payment.currency || 'USD'}</p>
    </div>
    <div class="field">
      <label>ID Transacción</label>
      <p>${payment.payment_id?.slice(0, 16) || '—'}</p>
    </div>
  </div>

  ${payment.notes ? `<div class="field" style="margin-top:16px"><label>Notas</label><p>${payment.notes}</p></div>` : ''}

  <div class="footer">
    <p>Automatik Media · automatik-media.com · Generado el ${new Date().toLocaleDateString('es-AR')}</p>
    <p style="margin-top:4px">Este comprobante es válido como constancia de pago.</p>
  </div>

  <script>window.onload = () => { window.print(); }</script>
</body>
</html>`;

  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// ── Export CSV ────────────────────────────────────────────────────────────────
function exportCSV(payments) {
  const headers = ['ID', 'Cliente', 'Monto', 'Moneda', 'Fecha', 'Período', 'Método', 'Estado', 'Notas'];
  const rows = payments.map(p => [
    p.payment_id?.slice(0, 8) || '',
    p.company_name || '',
    p.amount || 0,
    p.currency || 'USD',
    p.payment_date || '',
    p.period || '',
    METHOD_LABEL[p.method] || p.method || '',
    STATUS_LABEL[p.status] || p.status || '',
    (p.notes || '').replace(/,/g, ';'),
  ]);
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `pagos-automatik-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
}

// ─────────────────────────────────────────────────────────────────────────────

export default function PagosPage() {
  const [payments, setPayments] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filtros
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterMethod, setFilterMethod] = useState('');
  const [filterPeriod, setFilterPeriod] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Modal nuevo pago
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_PAYMENT);
  const [saving, setSaving] = useState(false);

  const months = monthOptions();

  const fetchPayments = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      if (filterStatus) params.status = filterStatus;
      if (filterMethod) params.method = filterMethod;
      if (filterPeriod) params.period = filterPeriod;
      const res = await axios.get(`${API}/superadmin/clients/payments/all`, { params });
      setPayments(res.data);
    } catch {
      toast.error('Error cargando pagos');
    } finally {
      setLoading(false);
    }
  }, [search, filterStatus, filterMethod, filterPeriod]);

  useEffect(() => { fetchPayments(); }, [fetchPayments]);

  useEffect(() => {
    axios.get(`${API}/superadmin/clients`).then(r => setClients(r.data)).catch(() => {});
  }, []);

  // Stats
  const totalCobrado = payments.filter(p => p.status === 'paid').reduce((s, p) => s + (p.amount || 0), 0);
  const thisPeriod = currentPeriod();
  const cobradoMes = payments.filter(p => p.status === 'paid' && p.period === thisPeriod).reduce((s, p) => s + (p.amount || 0), 0);
  const pendientes = payments.filter(p => p.status === 'pending').length;
  const totalCount = payments.length;

  const handleSave = async () => {
    if (!form.client_id || !form.amount) {
      toast.error('Cliente y monto son obligatorios');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/superadmin/clients/payments`, {
        ...form,
        amount: parseFloat(form.amount),
      });
      toast.success('Pago registrado');
      setShowForm(false);
      setForm(EMPTY_PAYMENT);
      fetchPayments();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`¿Eliminar el pago de ${p.company_name} por ${p.currency} ${p.amount}?`)) return;
    try {
      await axios.delete(`${API}/superadmin/clients/payments/${p.payment_id}`);
      toast.success('Pago eliminado');
      fetchPayments();
    } catch {
      toast.error('Error al eliminar el pago');
    }
  };

  const activeFilters = [filterStatus, filterMethod, filterPeriod].filter(Boolean).length;

  return (
    <div className="ak-dashboard">
      {/* Header */}
      <div className="ak-page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Pagos</h1>
          <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0', fontSize: 14 }}>
            Historial de cobros · {totalCount} registros
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="ak-btn ak-btn-ghost" onClick={() => exportCSV(payments)} title="Exportar CSV">
            <Download size={15} /> Exportar CSV
          </button>
          <button className="ak-btn ak-btn-primary" onClick={() => setShowForm(true)}>
            <Plus size={15} /> Registrar Pago
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="ak-kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 24 }}>
        <div className="ak-kpi-card">
          <div className="ak-kpi-icon" style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)' }}>
            <DollarSign size={20} color="#fff" />
          </div>
          <div className="ak-kpi-content">
            <span className="ak-kpi-label">Total Cobrado</span>
            <span className="ak-kpi-value">{fmt(totalCobrado)}</span>
          </div>
        </div>
        <div className="ak-kpi-card">
          <div className="ak-kpi-icon" style={{ background: 'linear-gradient(135deg,#10b981,#059669)' }}>
            <TrendingUp size={20} color="#fff" />
          </div>
          <div className="ak-kpi-content">
            <span className="ak-kpi-label">Este Mes</span>
            <span className="ak-kpi-value">{fmt(cobradoMes)}</span>
          </div>
        </div>
        <div className="ak-kpi-card">
          <div className="ak-kpi-icon" style={{ background: 'linear-gradient(135deg,#f59e0b,#d97706)' }}>
            <Clock size={20} color="#fff" />
          </div>
          <div className="ak-kpi-content">
            <span className="ak-kpi-label">Pendientes</span>
            <span className="ak-kpi-value">{pendientes}</span>
          </div>
        </div>
        <div className="ak-kpi-card">
          <div className="ak-kpi-icon" style={{ background: 'linear-gradient(135deg,#06b6d4,#0891b2)' }}>
            <CheckCircle size={20} color="#fff" />
          </div>
          <div className="ak-kpi-content">
            <span className="ak-kpi-label">Total Registros</span>
            <span className="ak-kpi-value">{totalCount}</span>
          </div>
        </div>
      </div>

      {/* Barra de búsqueda + filtros */}
      <div className="ak-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input
              className="ak-input"
              style={{ paddingLeft: 32, width: '100%' }}
              placeholder="Buscar por empresa..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <button
            className={`ak-btn ${filtersOpen || activeFilters > 0 ? 'ak-btn-primary' : 'ak-btn-ghost'}`}
            onClick={() => setFiltersOpen(v => !v)}
          >
            <Filter size={15} />
            Filtros {activeFilters > 0 && <span className="ak-badge" style={{ background: '#fff', color: '#6366f1', marginLeft: 4 }}>{activeFilters}</span>}
          </button>
          {activeFilters > 0 && (
            <button className="ak-btn ak-btn-ghost" onClick={() => { setFilterStatus(''); setFilterMethod(''); setFilterPeriod(''); }}>
              <X size={14} /> Limpiar
            </button>
          )}
        </div>

        {filtersOpen && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border-color)' }}>
            <div>
              <label className="ak-label">Estado</label>
              <select className="ak-input" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                <option value="">Todos</option>
                <option value="paid">Pagado</option>
                <option value="pending">Pendiente</option>
                <option value="failed">Fallido</option>
              </select>
            </div>
            <div>
              <label className="ak-label">Método</label>
              <select className="ak-input" value={filterMethod} onChange={e => setFilterMethod(e.target.value)}>
                <option value="">Todos</option>
                {METHODS.map(m => <option key={m} value={m}>{METHOD_LABEL[m]}</option>)}
              </select>
            </div>
            <div>
              <label className="ak-label">Período</label>
              <select className="ak-input" value={filterPeriod} onChange={e => setFilterPeriod(e.target.value)}>
                <option value="">Todos</option>
                {months.map(m => <option key={m.val} value={m.val}>{m.label}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Tabla */}
      <div className="ak-card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>Cargando...</div>
        ) : payments.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>
            <DollarSign size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
            <p>No hay pagos registrados aún</p>
          </div>
        ) : (
          <table className="ak-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Monto</th>
                <th>Período</th>
                <th>Fecha</th>
                <th>Método</th>
                <th>Estado</th>
                <th>Notas</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(p => (
                <tr key={p.payment_id}>
                  <td>
                    <span style={{ fontWeight: 600 }}>{p.company_name || '—'}</span>
                    <span style={{ display: 'block', fontSize: 11, color: 'var(--text-secondary)', marginTop: 1 }}>
                      #{p.payment_id?.slice(0, 8).toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontWeight: 700, fontSize: 15, color: p.status === 'paid' ? '#10b981' : p.status === 'pending' ? '#f59e0b' : '#ef4444' }}>
                      {p.currency === 'USD' ? 'USD ' : '$ '}{Number(p.amount || 0).toLocaleString('es-AR')}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{p.period || '—'}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{fmtDate(p.payment_date)}</td>
                  <td>
                    <span style={{
                      background: METHOD_COLOR[p.method] + '22',
                      color: METHOD_COLOR[p.method] || '#6b7280',
                      padding: '2px 10px', borderRadius: 99, fontSize: 12, fontWeight: 600,
                    }}>
                      {METHOD_LABEL[p.method] || p.method || '—'}
                    </span>
                  </td>
                  <td>
                    <span style={{
                      background: (STATUS_COLOR[p.status] || '#9ca3af') + '22',
                      color: STATUS_COLOR[p.status] || '#9ca3af',
                      padding: '2px 10px', borderRadius: 99, fontSize: 12, fontWeight: 600,
                    }}>
                      {STATUS_LABEL[p.status] || p.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.notes || '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                      <button
                        className="ak-btn ak-btn-ghost ak-btn-sm"
                        title="Ver/Imprimir comprobante"
                        onClick={() => printInvoice(p)}
                      >
                        <FileText size={14} />
                      </button>
                      <button
                        className="ak-btn ak-btn-ghost ak-btn-sm"
                        title="Eliminar pago"
                        style={{ color: '#ef4444' }}
                        onClick={() => handleDelete(p)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal nuevo pago */}
      {showForm && (
        <div className="ak-modal-overlay" onClick={() => setShowForm(false)}>
          <div className="ak-modal" onClick={e => e.stopPropagation()}>
            <div className="ak-modal-header">
              <h3>Registrar Pago</h3>
              <button className="ak-btn ak-btn-ghost ak-btn-icon" onClick={() => setShowForm(false)}><X size={16} /></button>
            </div>
            <div className="ak-modal-body">
              <div className="ak-form-grid">
                <div className="ak-form-full">
                  <label className="ak-label">Cliente *</label>
                  <select className="ak-input" value={form.client_id} onChange={e => {
                    const cl = clients.find(c => c.client_id === e.target.value);
                    setForm(f => ({
                      ...f,
                      client_id: e.target.value,
                      amount: cl ? String(cl.monthly_amount || '') : f.amount,
                    }));
                  }}>
                    <option value="">— Seleccionar cliente —</option>
                    {clients.map(c => (
                      <option key={c.client_id} value={c.client_id}>{c.company_name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="ak-label">Monto *</label>
                  <input
                    className="ak-input" type="number" min="0" placeholder="997"
                    value={form.amount}
                    onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="ak-label">Moneda</label>
                  <select className="ak-input" value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}>
                    <option value="USD">USD</option>
                    <option value="ARS">ARS</option>
                  </select>
                </div>

                <div>
                  <label className="ak-label">Fecha de Pago</label>
                  <input
                    className="ak-input" type="date"
                    value={form.payment_date}
                    onChange={e => setForm(f => ({ ...f, payment_date: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="ak-label">Período</label>
                  <select className="ak-input" value={form.period} onChange={e => setForm(f => ({ ...f, period: e.target.value }))}>
                    {months.map(m => <option key={m.val} value={m.val}>{m.label}</option>)}
                  </select>
                </div>

                <div>
                  <label className="ak-label">Método</label>
                  <select className="ak-input" value={form.method} onChange={e => setForm(f => ({ ...f, method: e.target.value }))}>
                    {METHODS.map(m => <option key={m} value={m}>{METHOD_LABEL[m]}</option>)}
                  </select>
                </div>
                <div>
                  <label className="ak-label">Estado</label>
                  <select className="ak-input" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                    <option value="paid">Pagado</option>
                    <option value="pending">Pendiente</option>
                    <option value="failed">Fallido</option>
                  </select>
                </div>

                <div className="ak-form-full">
                  <label className="ak-label">Notas</label>
                  <input
                    className="ak-input" placeholder="Opcional..."
                    value={form.notes}
                    onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  />
                </div>
              </div>
            </div>
            <div className="ak-modal-footer">
              <button className="ak-btn ak-btn-ghost" onClick={() => setShowForm(false)}>Cancelar</button>
              <button className="ak-btn ak-btn-primary" onClick={handleSave} disabled={saving}>
                <Save size={14} /> {saving ? 'Guardando...' : 'Registrar Pago'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
