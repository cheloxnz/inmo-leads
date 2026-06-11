import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { toast } from 'sonner';
import { Plus, X, Trash2, Search, RefreshCw, LayoutGrid, List, ArrowRight } from 'lucide-react';
import '../styles/AutomatikDashboard.css';
import '../styles/CRMPage.css';

// ── Configuración de etapas ────────────────────────────────────────────────
const STAGES = [
  { id: 'prospecto',         label: 'Prospecto',         color: '#9ca3af', bg: '#f9fafb' },
  { id: 'demo_agendada',     label: 'Demo Agendada',     color: '#3b82f6', bg: '#eff6ff' },
  { id: 'demo_realizada',    label: 'Demo Realizada',    color: '#f59e0b', bg: '#fffbeb' },
  { id: 'propuesta_enviada', label: 'Propuesta Enviada', color: '#f97316', bg: '#fff7ed' },
  { id: 'cerrado',           label: 'Cerrado ✅',         color: '#10b981', bg: '#f0fdf4' },
  { id: 'perdido',           label: 'Perdido ❌',         color: '#f87171', bg: '#fef2f2' },
];
const STAGE_MAP = Object.fromEntries(STAGES.map(s => [s.id, s]));

const PLANES = [
  { id: 'starter',    label: 'Starter $497' },
  { id: 'pro',        label: 'Pro $997' },
  { id: 'scale',      label: 'Scale $1,997' },
  { id: 'enterprise', label: 'Enterprise $3,997' },
];
const PLAN_MRR = { starter: 497, pro: 997, scale: 1997, enterprise: 3997 };

const CANALES = [
  { id: 'meta_ads',  label: 'Meta Ads' },
  { id: 'inmodesk',  label: 'InmoDesk email' },
  { id: 'organico',  label: 'Orgánico' },
  { id: 'referido',  label: 'Referido' },
];

const PAISES = ['AR', 'MX', 'CO', 'CL', 'UY', 'PE', 'otro'];

const MOTIVOS_PERDIDA = [
  'Precio', 'No es el momento', 'Eligió competencia', 'Sin respuesta', 'Otro'
];

// ── Helpers ────────────────────────────────────────────────────────────────
function diasEnEtapa(prospect) {
  const ref = prospect.updated_at || prospect.created_at;
  if (!ref) return 0;
  return Math.floor((Date.now() - new Date(ref)) / 86400000);
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

const EMPTY_FORM = {
  nombre: '', inmobiliaria: '', pais: 'AR', canal: 'meta_ads',
  whatsapp: '', email: '', fecha_entrada: new Date().toISOString().split('T')[0],
  etapa: 'prospecto', plan: 'pro', fecha_demo: '', fecha_propuesta: '',
  fecha_cierre: '', mrr: '', motivo_perdida: '', notas: '',
  proxima_accion: '', followup_activo: false,
};

// ── Card kanban ────────────────────────────────────────────────────────────
function ProspectCard({ prospect, onEdit, onDelete, onMoveStage }) {
  const sm = STAGE_MAP[prospect.etapa] || STAGES[0];
  const dias = diasEnEtapa(prospect);
  const stageIdx = STAGES.findIndex(s => s.id === prospect.etapa);
  const nextStage = STAGES[stageIdx + 1];

  return (
    <div className="crm-card" onClick={() => onEdit(prospect)}>
      <div className="crm-card-stripe" style={{ background: sm.color }} />
      <div className="crm-card-body">
        <div className="crm-card-name">{prospect.nombre}</div>
        {prospect.inmobiliaria && <div className="crm-card-company">{prospect.inmobiliaria}</div>}
        <div className="crm-card-meta">
          <span>{prospect.pais}</span>
          {prospect.plan && <span style={{ color: '#6366f1', fontWeight: 600 }}>{PLANES.find(p => p.id === prospect.plan)?.label || prospect.plan}</span>}
        </div>
        <div className="crm-card-footer">
          <span className="crm-card-days" style={{ color: dias > 7 ? '#dc2626' : '#9ca3af' }}>
            {dias}d en etapa
          </span>
          <div style={{ display: 'flex', gap: 4 }}>
            {nextStage && !['cerrado', 'perdido'].includes(prospect.etapa) && (
              <button
                className="crm-move-btn"
                title={`Mover a ${nextStage.label}`}
                style={{ borderColor: nextStage.color, color: nextStage.color }}
                onClick={e => { e.stopPropagation(); onMoveStage(prospect, nextStage.id); }}
              >
                <ArrowRight size={11} /> {nextStage.label.split(' ')[0]}
              </button>
            )}
            <button className="crm-icon-btn" title="Eliminar" onClick={e => { e.stopPropagation(); onDelete(prospect); }}>
              <Trash2 size={11} />
            </button>
          </div>
        </div>
        {prospect.followup_activo && (
          <div className="crm-followup-badge">🔄 Follow-up activo</div>
        )}
      </div>
    </div>
  );
}

// ── Modal edición ──────────────────────────────────────────────────────────
function ProspectModal({ prospect, onClose, onSave }) {
  const [form, setForm] = useState(prospect
    ? { ...EMPTY_FORM, ...prospect, mrr: prospect.mrr || '' }
    : { ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  const f = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  const handleSave = async () => {
    if (!form.nombre) return toast.error('El nombre es obligatorio');
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="crm-modal-overlay" onClick={onClose}>
      <div className="crm-modal" onClick={e => e.stopPropagation()}>
        <div className="crm-modal-header">
          <h3>{prospect ? 'Editar prospecto' : 'Nuevo prospecto'}</h3>
          <button className="ak-btn ak-btn-ghost ak-btn-icon" onClick={onClose}><X size={15} /></button>
        </div>

        <div className="crm-modal-body">
          <div className="crm-form-grid">
            <div className="crm-form-full">
              <label className="ak-label">Nombre *</label>
              <input className="ak-input" value={form.nombre} onChange={e => f('nombre', e.target.value)} placeholder="Nombre del dueño/director" />
            </div>
            <div>
              <label className="ak-label">Inmobiliaria / Empresa</label>
              <input className="ak-input" value={form.inmobiliaria} onChange={e => f('inmobiliaria', e.target.value)} placeholder="Nombre de la empresa" />
            </div>
            <div>
              <label className="ak-label">País</label>
              <select className="ak-input" value={form.pais} onChange={e => f('pais', e.target.value)}>
                {PAISES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="ak-label">Canal de entrada</label>
              <select className="ak-input" value={form.canal} onChange={e => f('canal', e.target.value)}>
                {CANALES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="ak-label">Etapa</label>
              <select className="ak-input" value={form.etapa} onChange={e => f('etapa', e.target.value)}>
                {STAGES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="ak-label">WhatsApp</label>
              <input className="ak-input" value={form.whatsapp} onChange={e => f('whatsapp', e.target.value)} placeholder="+549..." />
            </div>
            <div>
              <label className="ak-label">Email</label>
              <input className="ak-input" type="email" value={form.email} onChange={e => f('email', e.target.value)} />
            </div>
            <div>
              <label className="ak-label">Plan de interés</label>
              <select className="ak-input" value={form.plan} onChange={e => f('plan', e.target.value)}>
                <option value="">— Sin definir —</option>
                {PLANES.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="ak-label">Fecha de entrada</label>
              <input className="ak-input" type="date" value={form.fecha_entrada} onChange={e => f('fecha_entrada', e.target.value)} />
            </div>
            <div>
              <label className="ak-label">Fecha demo</label>
              <input className="ak-input" type="date" value={form.fecha_demo || ''} onChange={e => f('fecha_demo', e.target.value)} />
            </div>
            <div>
              <label className="ak-label">Fecha propuesta</label>
              <input className="ak-input" type="date" value={form.fecha_propuesta || ''} onChange={e => f('fecha_propuesta', e.target.value)} />
            </div>
            <div>
              <label className="ak-label">Fecha cierre</label>
              <input className="ak-input" type="date" value={form.fecha_cierre || ''} onChange={e => f('fecha_cierre', e.target.value)} />
            </div>
            {form.etapa === 'cerrado' && (
              <div>
                <label className="ak-label">MRR generado (USD)</label>
                <input className="ak-input" type="number" value={form.mrr} onChange={e => f('mrr', e.target.value)} placeholder={PLAN_MRR[form.plan] || ''} />
              </div>
            )}
            {form.etapa === 'perdido' && (
              <div>
                <label className="ak-label">Motivo de pérdida</label>
                <select className="ak-input" value={form.motivo_perdida || ''} onChange={e => f('motivo_perdida', e.target.value)}>
                  <option value="">— Seleccionar —</option>
                  {MOTIVOS_PERDIDA.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            )}
            <div className="crm-form-full">
              <label className="ak-label">Próxima acción</label>
              <input className="ak-input" value={form.proxima_accion || ''} onChange={e => f('proxima_accion', e.target.value)} placeholder="ej: Enviar propuesta el lunes" />
            </div>
            <div className="crm-form-full">
              <label className="ak-label">Notas</label>
              <textarea className="ak-input" rows={3} style={{ resize: 'vertical' }} value={form.notas || ''} onChange={e => f('notas', e.target.value)} placeholder="Resumen de la demo, objeciones, contexto..." />
            </div>
            <div className="crm-form-full">
              <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                <input type="checkbox" checked={form.followup_activo} onChange={e => f('followup_activo', e.target.checked)} style={{ width: 16, height: 16 }} />
                <span style={{ fontSize: 13 }}>🔄 Follow-up activo (secuencia n8n 3 días)</span>
              </label>
            </div>
          </div>
        </div>

        <div className="crm-modal-footer">
          <button className="ak-btn ak-btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="ak-btn ak-btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Guardando...' : prospect ? 'Guardar cambios' : 'Crear prospecto'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Página principal ────────────────────────────────────────────────────────
export default function CRMPage() {
  const [prospects, setProspects] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [view, setView]           = useState('kanban'); // kanban | table
  const [search, setSearch]       = useState('');
  const [filterEtapa, setFilterEtapa] = useState('');
  const [filterPais, setFilterPais]   = useState('');
  const [filterCanal, setFilterCanal] = useState('');
  const [modal, setModal]         = useState(null); // null | 'new' | prospect_obj
  const [saving, setSaving]       = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      if (filterEtapa) params.etapa = filterEtapa;
      if (filterPais) params.pais = filterPais;
      if (filterCanal) params.canal = filterCanal;
      const res = await axios.get(`${API}/superadmin/clients/crm`, { params });
      setProspects(res.data);
    } catch { toast.error('Error cargando CRM'); }
    finally { setLoading(false); }
  }, [search, filterEtapa, filterPais, filterCanal]);

  useEffect(() => { fetch(); }, [fetch]);

  // ── CRUD ────────────────────────────────────────────────────────────────
  const handleSave = async (form) => {
    setSaving(true);
    try {
      const body = { ...form, mrr: form.mrr ? parseFloat(form.mrr) : null };
      if (modal && modal.prospect_id) {
        const res = await axios.put(`${API}/superadmin/clients/crm/${modal.prospect_id}`, body);
        setProspects(prev => prev.map(p => p.prospect_id === modal.prospect_id ? res.data : p));
        toast.success('Prospecto actualizado');
        if (form.etapa === 'demo_realizada') toast.info('🔄 Se disparó el follow-up en n8n');
      } else {
        const res = await axios.post(`${API}/superadmin/clients/crm`, body);
        setProspects(prev => [res.data, ...prev]);
        toast.success('Prospecto creado');
      }
    } catch { toast.error('Error guardando'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`¿Eliminás a ${p.nombre}?`)) return;
    try {
      await axios.delete(`${API}/superadmin/clients/crm/${p.prospect_id}`);
      setProspects(prev => prev.filter(x => x.prospect_id !== p.prospect_id));
      toast.success('Prospecto eliminado');
    } catch { toast.error('Error eliminando'); }
  };

  const handleMoveStage = async (p, newStage) => {
    try {
      const res = await axios.put(`${API}/superadmin/clients/crm/${p.prospect_id}`, { etapa: newStage });
      setProspects(prev => prev.map(x => x.prospect_id === p.prospect_id ? res.data : x));
      toast.success(`Movido a ${STAGE_MAP[newStage]?.label}`);
      if (newStage === 'demo_realizada') toast.info('🔄 Follow-up n8n disparado');
    } catch { toast.error('Error moviendo etapa'); }
  };

  // ── KPIs ────────────────────────────────────────────────────────────────
  const activos = prospects.filter(p => !['cerrado', 'perdido'].includes(p.etapa));
  const cerrados = prospects.filter(p => p.etapa === 'cerrado');
  const mrrTotal = cerrados.reduce((s, p) => s + (p.mrr || PLAN_MRR[p.plan] || 0), 0);
  const demos = prospects.filter(p => ['demo_realizada', 'propuesta_enviada', 'cerrado'].includes(p.etapa)).length;
  const tasaCierre = demos > 0 ? Math.round((cerrados.length / demos) * 100) : 0;
  const demosRealizadas = prospects.filter(p => ['demo_realizada', 'propuesta_enviada', 'cerrado'].includes(p.etapa)).length;
  const propuestas = prospects.filter(p => ['propuesta_enviada', 'cerrado'].includes(p.etapa)).length;
  const demoAPropuesta = demosRealizadas > 0 ? Math.round((propuestas / demosRealizadas) * 100) : 0;
  const propAcierre = propuestas > 0 ? Math.round((cerrados.length / propuestas) * 100) : 0;

  // ── Vista kanban ────────────────────────────────────────────────────────
  const renderKanban = () => (
    <div className="crm-kanban">
      {STAGES.map(stage => {
        const cards = prospects.filter(p => p.etapa === stage.id);
        return (
          <div key={stage.id} className="crm-column">
            <div className="crm-col-header" style={{ borderColor: stage.color }}>
              <span className="crm-col-title" style={{ color: stage.color }}>{stage.label}</span>
              <span className="crm-col-count" style={{ background: stage.color + '20', color: stage.color }}>{cards.length}</span>
            </div>
            <div className="crm-col-body">
              {cards.map(p => (
                <ProspectCard
                  key={p.prospect_id}
                  prospect={p}
                  onEdit={setModal}
                  onDelete={handleDelete}
                  onMoveStage={handleMoveStage}
                />
              ))}
              {cards.length === 0 && (
                <div className="crm-col-empty">Sin prospectos</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  // ── Vista tabla ─────────────────────────────────────────────────────────
  const renderTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--border-color)' }}>
            {['Nombre', 'Empresa', 'País', 'Canal', 'Etapa', 'Plan', 'Fecha entrada', 'Fecha demo', 'MRR', 'Próxima acción', ''].map(h => (
              <th key={h} style={{ padding: '8px 10px', fontWeight: 600, color: 'var(--text-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em', textAlign: 'left', whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {prospects.map(p => {
            const sm = STAGE_MAP[p.etapa] || STAGES[0];
            return (
              <tr key={p.prospect_id} style={{ borderBottom: '1px solid var(--border-color)', cursor: 'pointer' }} onClick={() => setModal(p)}>
                <td style={{ padding: '9px 10px', fontWeight: 600 }}>{p.nombre}</td>
                <td style={{ padding: '9px 10px', color: 'var(--text-secondary)' }}>{p.inmobiliaria || '—'}</td>
                <td style={{ padding: '9px 10px' }}>{p.pais}</td>
                <td style={{ padding: '9px 10px', color: 'var(--text-secondary)' }}>{CANALES.find(c => c.id === p.canal)?.label || p.canal}</td>
                <td style={{ padding: '9px 10px' }}>
                  <span style={{ background: sm.bg, color: sm.color, border: `1px solid ${sm.color}40`, padding: '2px 8px', borderRadius: 20, fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap' }}>{sm.label}</span>
                </td>
                <td style={{ padding: '9px 10px', color: '#6366f1', fontWeight: 600 }}>{PLANES.find(pl => pl.id === p.plan)?.label || '—'}</td>
                <td style={{ padding: '9px 10px', whiteSpace: 'nowrap' }}>{fmtDate(p.fecha_entrada)}</td>
                <td style={{ padding: '9px 10px', whiteSpace: 'nowrap' }}>{fmtDate(p.fecha_demo)}</td>
                <td style={{ padding: '9px 10px', color: '#10b981', fontWeight: 700 }}>{p.mrr ? `$${p.mrr}` : '—'}</td>
                <td style={{ padding: '9px 10px', color: 'var(--text-secondary)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.proxima_accion || '—'}</td>
                <td style={{ padding: '9px 10px' }} onClick={e => e.stopPropagation()}>
                  <button className="crm-icon-btn" style={{ color: '#dc2626' }} onClick={() => handleDelete(p)}><Trash2 size={12} /></button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="ak-dashboard">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>CRM Ventas</h1>
          <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0', fontSize: 14 }}>
            Pipeline de prospectos · Automatik Media
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`ak-btn ak-btn-sm ${view === 'kanban' ? 'ak-btn-primary' : 'ak-btn-ghost'}`} onClick={() => setView('kanban')}><LayoutGrid size={14} /> Kanban</button>
          <button className={`ak-btn ak-btn-sm ${view === 'table' ? 'ak-btn-primary' : 'ak-btn-ghost'}`} onClick={() => setView('table')}><List size={14} /> Tabla</button>
          <button className="ak-btn ak-btn-ghost ak-btn-sm" onClick={fetch}><RefreshCw size={14} className={loading ? 'spin' : ''} /></button>
          <button className="ak-btn ak-btn-primary ak-btn-sm" onClick={() => setModal('new')}>
            <Plus size={14} /> Nuevo prospecto
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        {[
          { label: 'Activos',          val: activos.length,         color: '#6366f1' },
          { label: 'MRR Cerrado',      val: `$${mrrTotal.toLocaleString()}`, color: '#10b981' },
          { label: 'Tasa cierre',      val: `${tasaCierre}%`,       color: '#f59e0b' },
          { label: 'Demo → Propuesta', val: `${demoAPropuesta}%`,   color: '#3b82f6' },
          { label: 'Propuesta → Cierre', val: `${propAcierre}%`,    color: '#f97316' },
        ].map(k => (
          <div key={k.label} className="ak-kpi-card" style={{ minWidth: 130 }}>
            <div className="ak-kpi-content">
              <span className="ak-kpi-label">{k.label}</span>
              <span className="ak-kpi-value" style={{ color: k.color }}>{k.val}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 18, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
          <input className="ak-input" style={{ paddingLeft: 30 }} placeholder="Buscar nombre, empresa..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="ak-input" style={{ width: 160 }} value={filterEtapa} onChange={e => setFilterEtapa(e.target.value)}>
          <option value="">Todas las etapas</option>
          {STAGES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <select className="ak-input" style={{ width: 120 }} value={filterPais} onChange={e => setFilterPais(e.target.value)}>
          <option value="">Todos los países</option>
          {PAISES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="ak-input" style={{ width: 160 }} value={filterCanal} onChange={e => setFilterCanal(e.target.value)}>
          <option value="">Todos los canales</option>
          {CANALES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
      </div>

      {/* Vista */}
      {loading ? (
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>Cargando...</div>
      ) : prospects.length === 0 ? (
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>
          <p style={{ fontSize: 40, marginBottom: 8 }}>🎯</p>
          <p>No hay prospectos todavía</p>
          <button className="ak-btn ak-btn-primary ak-btn-sm" style={{ marginTop: 12 }} onClick={() => setModal('new')}>+ Crear primer prospecto</button>
        </div>
      ) : view === 'kanban' ? renderKanban() : renderTable()}

      {/* Modal */}
      {modal && (
        <ProspectModal
          prospect={modal === 'new' ? null : modal}
          onClose={() => setModal(null)}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
