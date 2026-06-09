import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { toast } from 'sonner';
import {
  Plus, Search, Edit2, Trash2, DollarSign, X, Save, ChevronDown
} from 'lucide-react';
import '../styles/AutomatikDashboard.css';

const PLANS = ['starter', 'pro', 'scale', 'enterprise'];
const PLAN_PRICES = { starter: 497, pro: 997, scale: 1997, enterprise: 3997 };
const PLAN_COLOR = { starter: '#6366f1', pro: '#8b5cf6', scale: '#06b6d4', enterprise: '#f59e0b' };
const STATUSES = ['active', 'trial', 'paused', 'cancelled'];
const STATUS_LABEL = { active: 'Activo', trial: 'Trial', paused: 'Pausado', cancelled: 'Cancelado' };
const METHODS = ['transfer', 'stripe', 'mercadopago', 'cash'];

function fmt(n) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n || 0);
}

const EMPTY_FORM = {
  company_name: '', contact_name: '', contact_email: '', contact_phone: '',
  plan: 'pro', monthly_amount: '', currency: 'USD', status: 'active',
  start_date: '', next_payment_date: '', tenant_id: '', notes: '',
};

const EMPTY_PAYMENT = {
  client_id: '', amount: '', currency: 'USD', payment_date: '', method: 'transfer',
  status: 'paid', period: '', notes: '',
};

export default function ClientesPage() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // Drawer de pagos
  const [paymentClient, setPaymentClient] = useState(null);
  const [payments, setPayments] = useState([]);
  const [paymentForm, setPaymentForm] = useState(EMPTY_PAYMENT);
  const [savingPayment, setSavingPayment] = useState(false);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/superadmin/clients`, { params: { search } });
      setClients(Array.isArray(res.data) ? res.data : []);
    } catch {
      toast.error('Error al cargar clientes');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { fetchClients(); }, [fetchClients]);

  // ── Guardar cliente ──
  const handleSave = async () => {
    if (!form.company_name || !form.contact_name) return toast.error('Completá empresa y contacto');
    setSaving(true);
    try {
      const payload = {
        ...form,
        monthly_amount: form.monthly_amount !== '' ? parseFloat(form.monthly_amount) : PLAN_PRICES[form.plan],
      };
      if (editingId) {
        await axios.put(`${API}/superadmin/clients/${editingId}`, payload);
        toast.success('Cliente actualizado');
      } else {
        await axios.post(`${API}/superadmin/clients`, payload);
        toast.success('Cliente creado');
      }
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY_FORM);
      fetchClients();
    } catch (e) {
      toast.error('Error al guardar cliente');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (c) => {
    setForm({
      company_name: c.company_name || '', contact_name: c.contact_name || '',
      contact_email: c.contact_email || '', contact_phone: c.contact_phone || '',
      plan: c.plan || 'pro', monthly_amount: c.monthly_amount || '',
      currency: c.currency || 'USD', status: c.status || 'active',
      start_date: c.start_date || '', next_payment_date: c.next_payment_date || '',
      tenant_id: c.tenant_id || '', notes: c.notes || '',
    });
    setEditingId(c.client_id);
    setShowForm(true);
  };

  const handleDelete = async (c) => {
    if (!window.confirm(`¿Eliminar "${c.company_name}"?`)) return;
    try {
      await axios.delete(`${API}/superadmin/clients/${c.client_id}`);
      toast.success('Cliente eliminado');
      fetchClients();
    } catch {
      toast.error('Error al eliminar');
    }
  };

  // ── Pagos ──
  const openPayments = async (c) => {
    setPaymentClient(c);
    setPaymentForm({ ...EMPTY_PAYMENT, client_id: c.client_id, amount: c.monthly_amount || '' });
    try {
      const res = await axios.get(`${API}/superadmin/clients/payments/all`, { params: { client_id: c.client_id } });
      setPayments(Array.isArray(res.data) ? res.data : []);
    } catch { setPayments([]); }
  };

  const handleSavePayment = async () => {
    if (!paymentForm.amount) return toast.error('Ingresá el monto');
    setSavingPayment(true);
    try {
      await axios.post(`${API}/superadmin/clients/payments`, paymentForm);
      toast.success('Pago registrado');
      openPayments(paymentClient);
      fetchClients();
    } catch {
      toast.error('Error al registrar pago');
    } finally {
      setSavingPayment(false);
    }
  };

  return (
    <div className="ak-dashboard">
      <div className="ak-header">
        <div>
          <h1 className="ak-title">Clientes</h1>
          <p className="ak-subtitle">Gestión de inmobiliarias suscritas a Automatik Media</p>
        </div>
        <button className="ak-btn ak-btn--primary" onClick={() => { setShowForm(true); setEditingId(null); setForm(EMPTY_FORM); }}>
          <Plus size={14} /> Nuevo cliente
        </button>
      </div>

      {/* Búsqueda */}
      <div className="ak-search-bar">
        <Search size={16} className="ak-search-icon" />
        <input
          className="ak-search-input"
          placeholder="Buscar por empresa, contacto o email…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Tabla */}
      <div className="ak-card" style={{ marginTop: 16 }}>
        {loading ? (
          <div className="ak-loading"><div className="ak-spinner" /></div>
        ) : clients.length === 0 ? (
          <div className="ak-empty">No hay clientes. <button className="ak-link-btn" onClick={() => setShowForm(true)}>Crear el primero</button></div>
        ) : (
          <table className="ak-table ak-table--full">
            <thead>
              <tr>
                <th>Empresa</th>
                <th>Plan</th>
                <th>Monto/mes</th>
                <th>Estado</th>
                <th>Inicio</th>
                <th>Próx. pago</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {clients.map(c => (
                <tr key={c.client_id}>
                  <td>
                    <div className="ak-client-name">{c.company_name}</div>
                    <div className="ak-client-contact">{c.contact_name} {c.contact_email ? `· ${c.contact_email}` : ''}</div>
                  </td>
                  <td>
                    <span className="ak-plan-chip" style={{ background: PLAN_COLOR[c.plan] + '22', color: PLAN_COLOR[c.plan] }}>
                      {c.plan?.toUpperCase()}
                    </span>
                  </td>
                  <td className="ak-amount">{fmt(c.monthly_amount)}</td>
                  <td>
                    <span className={`ak-badge ak-badge--${c.status}`}>{STATUS_LABEL[c.status] || c.status}</span>
                  </td>
                  <td className="ak-date">{c.start_date || '—'}</td>
                  <td className="ak-date">{c.next_payment_date || '—'}</td>
                  <td>
                    <div className="ak-row-actions">
                      <button className="ak-icon-btn" title="Registrar pago" onClick={() => openPayments(c)}>
                        <DollarSign size={14} />
                      </button>
                      <button className="ak-icon-btn" title="Editar" onClick={() => handleEdit(c)}>
                        <Edit2 size={14} />
                      </button>
                      <button className="ak-icon-btn ak-icon-btn--danger" title="Eliminar" onClick={() => handleDelete(c)}>
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

      {/* Modal: Crear/Editar cliente */}
      {showForm && (
        <div className="ak-modal-overlay" onClick={() => setShowForm(false)}>
          <div className="ak-modal" onClick={e => e.stopPropagation()}>
            <div className="ak-modal-header">
              <h2>{editingId ? 'Editar cliente' : 'Nuevo cliente'}</h2>
              <button onClick={() => setShowForm(false)}><X size={18} /></button>
            </div>
            <div className="ak-modal-body">
              <div className="ak-form-grid">
                <div className="ak-field">
                  <label>Empresa *</label>
                  <input value={form.company_name} onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))} placeholder="Inmobiliaria XYZ" />
                </div>
                <div className="ak-field">
                  <label>Contacto *</label>
                  <input value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} placeholder="Juan García" />
                </div>
                <div className="ak-field">
                  <label>Email</label>
                  <input value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} placeholder="juan@xyz.com" />
                </div>
                <div className="ak-field">
                  <label>WhatsApp</label>
                  <input value={form.contact_phone} onChange={e => setForm(f => ({ ...f, contact_phone: e.target.value }))} placeholder="+54 9 11 ..." />
                </div>
                <div className="ak-field">
                  <label>Plan</label>
                  <select value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value, monthly_amount: PLAN_PRICES[e.target.value] }))}>
                    {PLANS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)} — ${PLAN_PRICES[p]}/mes</option>)}
                  </select>
                </div>
                <div className="ak-field">
                  <label>Monto/mes (USD)</label>
                  <input type="number" value={form.monthly_amount} onChange={e => setForm(f => ({ ...f, monthly_amount: e.target.value }))} placeholder={PLAN_PRICES[form.plan]} />
                </div>
                <div className="ak-field">
                  <label>Estado</label>
                  <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                    {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                  </select>
                </div>
                <div className="ak-field">
                  <label>Fecha inicio</label>
                  <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
                </div>
                <div className="ak-field">
                  <label>Próximo pago</label>
                  <input type="date" value={form.next_payment_date} onChange={e => setForm(f => ({ ...f, next_payment_date: e.target.value }))} />
                </div>
                <div className="ak-field">
                  <label>Tenant InmoBot (opcional)</label>
                  <input value={form.tenant_id} onChange={e => setForm(f => ({ ...f, tenant_id: e.target.value }))} placeholder="tenant-id vinculado" />
                </div>
                <div className="ak-field ak-field--full">
                  <label>Notas</label>
                  <textarea rows={3} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Observaciones, acuerdos especiales…" />
                </div>
              </div>
            </div>
            <div className="ak-modal-footer">
              <button className="ak-btn ak-btn--ghost" onClick={() => setShowForm(false)}>Cancelar</button>
              <button className="ak-btn ak-btn--primary" onClick={handleSave} disabled={saving}>
                <Save size={14} /> {saving ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Drawer: Pagos */}
      {paymentClient && (
        <div className="ak-modal-overlay" onClick={() => setPaymentClient(null)}>
          <div className="ak-modal ak-modal--wide" onClick={e => e.stopPropagation()}>
            <div className="ak-modal-header">
              <h2>Pagos — {paymentClient.company_name}</h2>
              <button onClick={() => setPaymentClient(null)}><X size={18} /></button>
            </div>
            <div className="ak-modal-body">
              {/* Registrar pago */}
              <div className="ak-payment-form">
                <h3>Registrar pago</h3>
                <div className="ak-form-grid ak-form-grid--3">
                  <div className="ak-field">
                    <label>Monto (USD)</label>
                    <input type="number" value={paymentForm.amount} onChange={e => setPaymentForm(f => ({ ...f, amount: e.target.value }))} placeholder={paymentClient.monthly_amount} />
                  </div>
                  <div className="ak-field">
                    <label>Fecha</label>
                    <input type="date" value={paymentForm.payment_date} onChange={e => setPaymentForm(f => ({ ...f, payment_date: e.target.value }))} />
                  </div>
                  <div className="ak-field">
                    <label>Método</label>
                    <select value={paymentForm.method} onChange={e => setPaymentForm(f => ({ ...f, method: e.target.value }))}>
                      {METHODS.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                  <div className="ak-field">
                    <label>Estado</label>
                    <select value={paymentForm.status} onChange={e => setPaymentForm(f => ({ ...f, status: e.target.value }))}>
                      <option value="paid">Pagado</option>
                      <option value="pending">Pendiente</option>
                      <option value="failed">Fallido</option>
                    </select>
                  </div>
                  <div className="ak-field">
                    <label>Período</label>
                    <input type="month" value={paymentForm.period} onChange={e => setPaymentForm(f => ({ ...f, period: e.target.value }))} />
                  </div>
                  <div className="ak-field">
                    <label>Notas</label>
                    <input value={paymentForm.notes} onChange={e => setPaymentForm(f => ({ ...f, notes: e.target.value }))} placeholder="Opcional" />
                  </div>
                </div>
                <button className="ak-btn ak-btn--primary" onClick={handleSavePayment} disabled={savingPayment}>
                  <DollarSign size={14} /> {savingPayment ? 'Guardando…' : 'Registrar pago'}
                </button>
              </div>

              {/* Historial */}
              <h3 style={{ marginTop: 24, marginBottom: 12 }}>Historial de pagos</h3>
              {payments.length === 0 ? (
                <div className="ak-empty">Sin pagos registrados</div>
              ) : (
                <table className="ak-table ak-table--full">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Período</th>
                      <th>Monto</th>
                      <th>Método</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.map(p => (
                      <tr key={p.payment_id}>
                        <td className="ak-date">{p.payment_date}</td>
                        <td className="ak-date">{p.period}</td>
                        <td className="ak-amount">{fmt(p.amount)}</td>
                        <td>{p.method}</td>
                        <td><span className={`ak-badge ak-badge--${p.status === 'paid' ? 'active' : p.status === 'pending' ? 'trial' : 'cancelled'}`}>{p.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
