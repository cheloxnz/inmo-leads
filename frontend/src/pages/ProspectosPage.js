import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { API } from '../App';
import { toast } from 'sonner';
import {
  Search, RefreshCw, Plus, Trash2, X, ExternalLink,
  Mail, Phone, Globe, MapPin, Star, Filter
} from 'lucide-react';
import '../styles/AutomatikDashboard.css';
import '../styles/ProspectosPage.css';

// ── Configuración ────────────────────────────────────────────────────────────

const N8N_BASE = 'https://automatik-crm.duckdns.org';

const ESTADOS = [
  { id: 'Pendiente',          color: '#9ca3af', bg: '#f9fafb' },
  { id: 'Volver a Contactar', color: '#8b5cf6', bg: '#f5f3ff' },
  { id: '✏️ Borrador',        color: '#3b82f6', bg: '#eff6ff' },
  { id: '✅ Aprobado',        color: '#10b981', bg: '#f0fdf4' },
  { id: '📨 Enviado',         color: '#06b6d4', bg: '#ecfeff' },
  { id: 'Contactado',         color: '#0ea5e9', bg: '#f0f9ff' },
  { id: 'Esperando Respuesta',color: '#f59e0b', bg: '#fffbeb' },
  { id: 'En Negociación',     color: '#f97316', bg: '#fff7ed' },
  { id: 'Reunión Agendada',   color: '#a855f7', bg: '#faf5ff' },
  { id: 'Cliente',            color: '#10b981', bg: '#f0fdf4' },
  { id: 'No Interesado',      color: '#ef4444', bg: '#fef2f2' },
  { id: 'Cerrado Ganado',     color: '#16a34a', bg: '#f0fdf4' },
  { id: 'Cerrado Perdido',    color: '#dc2626', bg: '#fef2f2' },
];
const ESTADO_MAP = Object.fromEntries(ESTADOS.map(e => [e.id, e]));

const SCORE_COLOR = { 5: '#10b981', 4: '#84cc16', 3: '#f59e0b', 2: '#f97316', 1: '#ef4444' };

const EMPTY_FORM = {
  empresa: '', web: '', email: '', telefono: '', ciudad: '',
  sector: '', puntuacion: '', resenas: '', estado: 'Pendiente',
  notas_ia: '', score_ia: '', proxima_accion: '', notas: '',
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function EstadoBadge({ estado, small }) {
  const s = ESTADO_MAP[estado] || { color: '#9ca3af', bg: '#f9fafb' };
  return (
    <span style={{
      background: s.bg, color: s.color,
      border: `1px solid ${s.color}50`,
      padding: small ? '1px 6px' : '3px 9px',
      borderRadius: 20, fontSize: small ? 10 : 11, fontWeight: 600,
      whiteSpace: 'nowrap', display: 'inline-block',
    }}>{estado}</span>
  );
}

function ScoreStars({ score }) {
  if (!score) return <span style={{ color: '#d1d5db' }}>—</span>;
  return (
    <span style={{ color: SCORE_COLOR[score] || '#9ca3af', fontWeight: 700, fontSize: 12 }}>
      {'★'.repeat(score)}{'☆'.repeat(5 - score)}
    </span>
  );
}

// ── Inline estado select ──────────────────────────────────────────────────────

function EstadoCell({ prospect, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef();

  useEffect(() => {
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <div style={{ cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        <EstadoBadge estado={prospect.estado} small />
      </div>
      {open && (
        <div className="prosp-estado-dropdown">
          {ESTADOS.map(e => (
            <div
              key={e.id}
              className="prosp-estado-option"
              onClick={() => { onChange(prospect, e.id); setOpen(false); }}
            >
              <EstadoBadge estado={e.id} small />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Modal nuevo prospecto ─────────────────────────────────────────────────────

function ProspectModal({ onClose, onSave }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    if (!form.empresa) return toast.error('El nombre de la empresa es obligatorio');
    setSaving(true);
    try { await onSave(form); onClose(); }
    catch (e) { if (e?.response?.status === 409) toast.error('Ya existe este prospecto'); }
    finally { setSaving(false); }
  };

  return (
    <div className="crm-modal-overlay" onClick={onClose}>
      <div className="crm-modal" onClick={e => e.stopPropagation()}>
        <div className="crm-modal-header">
          <h3>Nuevo prospecto</h3>
          <button className="ak-btn ak-btn-ghost ak-btn-icon" onClick={onClose}><X size={15} /></button>
        </div>
        <div className="crm-modal-body">
          <div className="crm-form-grid">
            <div className="crm-form-full">
              <label className="ak-label">Empresa *</label>
              <input className="ak-input" value={form.empresa} onChange={e => f('empresa', e.target.value)} placeholder="Nombre de la inmobiliaria" />
            </div>
            <div>
              <label className="ak-label">Web</label>
              <input className="ak-input" value={form.web} onChange={e => f('web', e.target.value)} placeholder="https://..." />
            </div>
            <div>
              <label className="ak-label">Email</label>
              <input className="ak-input" type="email" value={form.email} onChange={e => f('email', e.target.value)} />
            </div>
            <div>
              <label className="ak-label">Teléfono</label>
              <input className="ak-input" value={form.telefono} onChange={e => f('telefono', e.target.value)} />
            </div>
            <div>
              <label className="ak-label">Ciudad</label>
              <input className="ak-input" value={form.ciudad} onChange={e => f('ciudad', e.target.value)} />
            </div>
            <div>
              <label className="ak-label">Estado</label>
              <select className="ak-input" value={form.estado} onChange={e => f('estado', e.target.value)}>
                {ESTADOS.map(e => <option key={e.id} value={e.id}>{e.id}</option>)}
              </select>
            </div>
            <div>
              <label className="ak-label">Score IA (1-5)</label>
              <select className="ak-input" value={form.score_ia} onChange={e => f('score_ia', e.target.value)}>
                <option value="">—</option>
                {[5,4,3,2,1].map(n => <option key={n} value={n}>{n} {'★'.repeat(n)}</option>)}
              </select>
            </div>
            <div>
              <label className="ak-label">Puntuación Google</label>
              <input className="ak-input" type="number" step="0.1" min="0" max="5" value={form.puntuacion} onChange={e => f('puntuacion', e.target.value)} placeholder="4.2" />
            </div>
            <div className="crm-form-full">
              <label className="ak-label">Próxima acción</label>
              <input className="ak-input" value={form.proxima_accion} onChange={e => f('proxima_accion', e.target.value)} placeholder="ej: Enviar propuesta el lunes" />
            </div>
            <div className="crm-form-full">
              <label className="ak-label">Notas IA / Análisis</label>
              <textarea className="ak-input" rows={3} style={{ resize: 'vertical' }} value={form.notas_ia} onChange={e => f('notas_ia', e.target.value)} placeholder="Problema detectado, oportunidad, tipo de solución..." />
            </div>
            <div className="crm-form-full">
              <label className="ak-label">Notas manuales</label>
              <textarea className="ak-input" rows={2} style={{ resize: 'vertical' }} value={form.notas} onChange={e => f('notas', e.target.value)} />
            </div>
          </div>
        </div>
        <div className="crm-modal-footer">
          <button className="ak-btn ak-btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="ak-btn ak-btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Guardando...' : 'Crear prospecto'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function ProspectosPage() {
  const [prospects, setProspects] = useState([]);
  const [stats, setStats]         = useState({});
  const [loading, setLoading]     = useState(true);
  const [search, setSearch]       = useState('');
  const [filterEstado, setFilterEstado] = useState('');
  const [filterCiudad, setFilterCiudad] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [n8nLoading, setN8nLoading] = useState('');

  const fetchProspects = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      if (filterEstado) params.estado = filterEstado;
      if (filterCiudad) params.ciudad = filterCiudad;
      const [pRes, sRes] = await Promise.all([
        axios.get(`${API}/superadmin/clients/prospects`, { params }),
        axios.get(`${API}/superadmin/clients/prospects/stats`),
      ]);
      setProspects(pRes.data);
      setStats(sRes.data);
    } catch { toast.error('Error cargando prospectos'); }
    finally { setLoading(false); }
  }, [search, filterEstado, filterCiudad]);

  useEffect(() => { fetchProspects(); }, [fetchProspects]);

  // ── CRUD ─────────────────────────────────────────────────────────────────
  const handleCreate = async (form) => {
    const body = { ...form, score_ia: form.score_ia ? parseInt(form.score_ia) : null, puntuacion: form.puntuacion ? parseFloat(form.puntuacion) : null };
    const res = await axios.post(`${API}/superadmin/clients/prospects`, body);
    setProspects(prev => [res.data, ...prev]);
    toast.success('Prospecto creado');
  };

  const handleEstadoChange = async (prospect, newEstado) => {
    try {
      const res = await axios.put(`${API}/superadmin/clients/prospects/${prospect.prospect_id}`, { estado: newEstado });
      setProspects(prev => prev.map(p => p.prospect_id === prospect.prospect_id ? res.data : p));
      toast.success(`Estado → ${newEstado}`);
    } catch { toast.error('Error actualizando estado'); }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`¿Eliminás "${p.empresa}"?`)) return;
    try {
      await axios.delete(`${API}/superadmin/clients/prospects/${p.prospect_id}`);
      setProspects(prev => prev.filter(x => x.prospect_id !== p.prospect_id));
      if (expandedId === p.prospect_id) setExpandedId(null);
      toast.success('Prospecto eliminado');
    } catch { toast.error('Error eliminando'); }
  };

  // ── n8n triggers ─────────────────────────────────────────────────────────
  const triggerN8n = async (webhook, label) => {
    setN8nLoading(label);
    try {
      await axios.post(`${N8N_BASE}/webhook/${webhook}`);
      toast.success(`✅ ${label} disparado en n8n`);
    } catch {
      toast.error(`Error disparando ${label}. Verificá que n8n esté activo.`);
    } finally { setN8nLoading(''); }
  };

  // ── Ciudades únicas para filtro ───────────────────────────────────────────
  const ciudades = [...new Set(prospects.map(p => p.ciudad).filter(Boolean))].sort();

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="ak-dashboard">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Prospectos</h1>
          <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0', fontSize: 14 }}>
            InmoDesk · Base de inmobiliarias a contactar
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {/* Acciones n8n */}
          <button
            className="ak-btn ak-btn-ghost ak-btn-sm"
            onClick={() => triggerN8n('generar-borradores', 'Generar borradores')}
            disabled={!!n8nLoading}
            title="Genera borradores en Gmail para leads Pendientes"
          >
            {n8nLoading === 'Generar borradores' ? '⏳' : '✉️'} Generar borradores
          </button>
          <button
            className="ak-btn ak-btn-ghost ak-btn-sm"
            onClick={() => triggerN8n('enviar-confirmados', 'Enviar confirmados')}
            disabled={!!n8nLoading}
            title="Envía los borradores aprobados"
          >
            {n8nLoading === 'Enviar confirmados' ? '⏳' : '📤'} Enviar confirmados
          </button>
          <button className="ak-btn ak-btn-ghost ak-btn-sm" onClick={fetchProspects}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
          <button className="ak-btn ak-btn-primary ak-btn-sm" onClick={() => setShowModal(true)}>
            <Plus size={14} /> Nuevo
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        {[
          { label: 'Total',        val: stats.total      || 0, color: '#6366f1' },
          { label: 'Pendientes',   val: stats.pendientes || 0, color: '#9ca3af' },
          { label: 'Enviados',     val: stats.enviados   || 0, color: '#06b6d4' },
          { label: 'Negociación',  val: stats.negociacion|| 0, color: '#f97316' },
          { label: 'Clientes',     val: stats.clientes   || 0, color: '#10b981' },
        ].map(k => (
          <div key={k.label} className="ak-kpi-card" style={{ minWidth: 110, cursor: k.label !== 'Total' ? 'pointer' : 'default' }}
            onClick={() => k.label === 'Pendientes' ? setFilterEstado('Pendiente') :
                          k.label === 'Negociación' ? setFilterEstado('En Negociación') :
                          k.label === 'Clientes'    ? setFilterEstado('Cliente') : null}>
            <div className="ak-kpi-content">
              <span className="ak-kpi-label">{k.label}</span>
              <span className="ak-kpi-value" style={{ color: k.color }}>{k.val}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
          <input className="ak-input" style={{ paddingLeft: 30 }} placeholder="Buscar empresa, email, ciudad..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="ak-input" style={{ width: 200 }} value={filterEstado} onChange={e => setFilterEstado(e.target.value)}>
          <option value="">Todos los estados</option>
          {ESTADOS.map(e => <option key={e.id} value={e.id}>{e.id}</option>)}
        </select>
        <select className="ak-input" style={{ width: 160 }} value={filterCiudad} onChange={e => setFilterCiudad(e.target.value)}>
          <option value="">Todas las ciudades</option>
          {ciudades.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {(filterEstado || filterCiudad || search) && (
          <button className="ak-btn ak-btn-ghost ak-btn-sm" onClick={() => { setFilterEstado(''); setFilterCiudad(''); setSearch(''); }}>
            <X size={12} /> Limpiar
          </button>
        )}
      </div>

      {/* Tabla */}
      {loading ? (
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>Cargando...</div>
      ) : prospects.length === 0 ? (
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>
          <p style={{ fontSize: 36, marginBottom: 8 }}>🔍</p>
          <p>No hay prospectos{search || filterEstado ? ' con esos filtros' : ' todavía'}</p>
          <p style={{ fontSize: 12, marginTop: 8, opacity: 0.7 }}>
            Los prospectos de n8n aparecen automáticamente aquí.<br/>
            Webhook: <code>POST /api/webhooks/inmobot-prospect</code>
          </p>
          <button className="ak-btn ak-btn-primary ak-btn-sm" style={{ marginTop: 12 }} onClick={() => setShowModal(true)}>
            + Agregar manualmente
          </button>
        </div>
      ) : (
        <div className="prosp-table-wrap">
          <table className="prosp-table">
            <thead>
              <tr>
                {['Empresa', 'Ciudad', 'Email', 'Teléfono', 'Score IA', '★ Google', 'Estado', 'Fecha envío', 'Próxima acción', ''].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {prospects.map(p => (
                <React.Fragment key={p.prospect_id}>
                  <tr
                    className={`prosp-row${expandedId === p.prospect_id ? ' prosp-row--expanded' : ''}`}
                    onClick={() => setExpandedId(expandedId === p.prospect_id ? null : p.prospect_id)}
                  >
                    <td className="prosp-td prosp-td--empresa">
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{p.empresa}</div>
                      {p.web && (
                        <a href={p.web} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} style={{ fontSize: 11, color: '#6366f1', display: 'flex', alignItems: 'center', gap: 3 }}>
                          <Globe size={10} /> {p.web.replace(/^https?:\/\//, '').split('/')[0]}
                        </a>
                      )}
                    </td>
                    <td className="prosp-td">{p.ciudad || '—'}</td>
                    <td className="prosp-td">
                      {p.email ? (
                        <a href={`mailto:${p.email}`} onClick={e => e.stopPropagation()} style={{ color: '#3b82f6', fontSize: 12 }}>
                          <Mail size={11} style={{ marginRight: 3 }} />{p.email}
                        </a>
                      ) : '—'}
                    </td>
                    <td className="prosp-td" style={{ fontSize: 12 }}>{p.telefono || '—'}</td>
                    <td className="prosp-td"><ScoreStars score={p.score_ia} /></td>
                    <td className="prosp-td" style={{ fontSize: 12 }}>
                      {p.puntuacion ? <span><Star size={11} style={{ marginRight: 2 }} />{p.puntuacion}</span> : '—'}
                    </td>
                    <td className="prosp-td" onClick={e => e.stopPropagation()}>
                      <EstadoCell prospect={p} onChange={handleEstadoChange} />
                    </td>
                    <td className="prosp-td" style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{p.fecha_envio || '—'}</td>
                    <td className="prosp-td" style={{ fontSize: 11, color: 'var(--text-secondary)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.proxima_accion || '—'}</td>
                    <td className="prosp-td" onClick={e => e.stopPropagation()}>
                      <button className="crm-icon-btn" style={{ color: '#dc2626' }} onClick={() => handleDelete(p)}><Trash2 size={12} /></button>
                    </td>
                  </tr>
                  {expandedId === p.prospect_id && (
                    <tr className="prosp-detail-row">
                      <td colSpan={10}>
                        <div className="prosp-detail">
                          {p.notas_ia && (
                            <div className="prosp-detail-block">
                              <span className="prosp-detail-label">🤖 Análisis IA</span>
                              <p>{p.notas_ia}</p>
                            </div>
                          )}
                          {p.etiqueta && (
                            <div className="prosp-detail-block">
                              <span className="prosp-detail-label">🏷️ Etiqueta</span>
                              <p>{p.etiqueta}</p>
                            </div>
                          )}
                          {p.tipo_solucion && (
                            <div className="prosp-detail-block">
                              <span className="prosp-detail-label">🎯 Solución recomendada</span>
                              <p>{p.tipo_solucion}</p>
                            </div>
                          )}
                          {p.notas && (
                            <div className="prosp-detail-block">
                              <span className="prosp-detail-label">📝 Notas</span>
                              <p>{p.notas}</p>
                            </div>
                          )}
                          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                            {p.estado === 'Pendiente' && (
                              <button className="ak-btn ak-btn-sm" style={{ background: '#eff6ff', color: '#3b82f6' }}
                                onClick={() => handleEstadoChange(p, 'Volver a Contactar')}>
                                🔄 Marcar "Volver a Contactar"
                              </button>
                            )}
                            {p.estado === '✏️ Borrador' && (
                              <button className="ak-btn ak-btn-sm" style={{ background: '#f0fdf4', color: '#10b981' }}
                                onClick={() => handleEstadoChange(p, '✅ Aprobado')}>
                                ✅ Aprobar para envío
                              </button>
                            )}
                            {p.email && (
                              <a href={`https://mail.google.com/mail/?view=cm&to=${p.email}`} target="_blank" rel="noreferrer" className="ak-btn ak-btn-sm ak-btn-ghost">
                                <ExternalLink size={12} /> Abrir Gmail
                              </a>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '8px 12px', fontSize: 11, color: 'var(--text-secondary)', borderTop: '1px solid var(--border-color)' }}>
            {prospects.length} prospecto{prospects.length !== 1 ? 's' : ''}
          </div>
        </div>
      )}

      {showModal && <ProspectModal onClose={() => setShowModal(false)} onSave={handleCreate} />}
    </div>
  );
}
