import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { toast } from 'sonner';
import {
  Search, Filter, X, Phone, Calendar, TrendingUp,
  Users, BarChart2, Briefcase, DollarSign, MessageSquare,
  ChevronRight, RefreshCw, AlertCircle, Lightbulb
} from 'lucide-react';
import '../styles/AutomatikDashboard.css';
import '../styles/AutomatikLeads.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

const BIZ_LABEL   = { inmobiliaria: 'Inmobiliaria', asesor: 'Asesor', desarrolladora: 'Desarrolladora' };
const BIZ_COLOR   = { inmobiliaria: '#6366f1', asesor: '#8b5cf6', desarrolladora: '#06b6d4' };
const TOOLS_LABEL = { nada: 'Sin herramientas', basico: 'Básico (Excel/WA)', crm: 'CRM activo' };
const ADS_LABEL   = { invierte: 'Invierte en ads', quiere: 'Quiere invertir', no: 'No invierte' };
const ADS_COLOR   = { invierte: '#10b981', quiere: '#f59e0b', no: '#9ca3af' };

const STATUS_META = {
  hot:      { label: 'HOT 🔥',  bg: '#fef2f2', color: '#dc2626', border: '#fca5a5' },
  warm:     { label: 'WARM ☀️', bg: '#fffbeb', color: '#d97706', border: '#fcd34d' },
  cold:     { label: 'COLD ❄️', bg: '#eff6ff', color: '#2563eb', border: '#93c5fd' },
  new:      { label: 'NUEVO',   bg: '#f0fdf4', color: '#16a34a', border: '#86efac' },
  handoff:  { label: 'HANDOFF', bg: '#fdf4ff', color: '#9333ea', border: '#d8b4fe' },
};

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function fmtTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

function getScore(lead) {
  const a = lead?.metadata?.automatik_answers || {};
  let s = 0;
  const bt = (a.biz_type || '').toLowerCase();
  if (bt.includes('inmob')) s += 3; else if (bt.includes('desa')) s += 2; else if (bt.includes('asesor')) s += 1;
  const ts = (a.team_size || '').toLowerCase();
  if (ts.includes('+15') || ts.includes('15')) s += 4;
  else if (ts.includes('6') || ts.includes('10')) s += 3;
  else if (ts.includes('2') || ts.includes('5')) s += 2;
  const ml = parseInt(a.monthly_leads) || 0;
  if (ml >= 100) s += 3; else if (ml >= 20) s += 2; else if (ml >= 5) s += 1;
  const mc = parseInt(a.monthly_closes) || 0;
  if (mc >= 5) s += 2; else if (mc >= 1) s += 1;
  const ct = (a.current_tools || '').toLowerCase();
  if (ct.includes('nada') || ct.includes('no')) s += 3;
  else if (ct.includes('excel') || ct.includes('básico') || ct.includes('basico') || ct.includes('whatsapp')) s += 2;
  else s += 1;
  const ai = (a.ads_invest || '').toLowerCase();
  if (ai.includes('s') && !ai.includes('no')) s += 3; else if (ai.includes('quiere')) s += 2;
  return s;
}

function getStatusFromScore(lead) {
  const explicit = (lead.status || '').toLowerCase();
  if (explicit === 'handoff') return 'handoff';
  const score = getScore(lead);
  if (score >= 11) return 'hot';
  if (score >= 6)  return 'warm';
  return 'cold';
}

// ── Card B2B ──────────────────────────────────────────────────────────────────

function LeadCard({ lead, onClick, selected }) {
  const answers  = lead?.metadata?.automatik_answers || {};
  const score    = getScore(lead);
  const statusKey = getStatusFromScore(lead);
  const sm        = STATUS_META[statusKey] || STATUS_META.new;
  const bizType   = answers.biz_type || '';
  const bizColor  = BIZ_COLOR[bizType] || '#9ca3af';

  return (
    <div
      className={`al-card${selected ? ' al-card--selected' : ''}`}
      onClick={() => onClick(lead)}
    >
      {/* Franja lateral de temperatura */}
      <div className="al-card-stripe" style={{ background: sm.color }} />

      <div className="al-card-body">
        {/* Fila 1: nombre + badge temperatura */}
        <div className="al-card-row al-card-row--top">
          <div className="al-card-name">{lead.name || lead.phone}</div>
          <span className="al-badge" style={{ background: sm.bg, color: sm.color, border: `1px solid ${sm.border}` }}>
            {sm.label}
          </span>
        </div>

        {/* Fila 2: tipo negocio + teléfono */}
        <div className="al-card-row">
          {bizType && (
            <span className="al-tag" style={{ background: bizColor + '18', color: bizColor }}>
              <Briefcase size={10} style={{ marginRight: 3 }} />
              {BIZ_LABEL[bizType] || bizType}
            </span>
          )}
          <span className="al-meta"><Phone size={10} /> {lead.phone}</span>
        </div>

        {/* Fila 3: métricas clave */}
        <div className="al-card-metrics">
          {answers.team_size && (
            <div className="al-metric">
              <Users size={11} />
              <span>{answers.team_size}</span>
            </div>
          )}
          {answers.monthly_leads && (
            <div className="al-metric">
              <TrendingUp size={11} />
              <span>{answers.monthly_leads} leads/mes</span>
            </div>
          )}
          {answers.monthly_closes && (
            <div className="al-metric">
              <BarChart2 size={11} />
              <span>{answers.monthly_closes} cierres</span>
            </div>
          )}
          {answers.ads_invest && (
            <div className="al-metric" style={{ color: ADS_COLOR[answers.ads_invest] || '#9ca3af' }}>
              <DollarSign size={11} />
              <span>{ADS_LABEL[answers.ads_invest] || answers.ads_invest}</span>
            </div>
          )}
        </div>

        {/* Fila 3b: problem tags */}
        {(answers.problem_tags?.length > 0) && (
          <div className="al-problem-tags">
            {answers.problem_tags.map((t, i) => (
              <span key={i} className="al-problem-tag">⚠️ {t}</span>
            ))}
          </div>
        )}

        {/* Fila 4: score bar + fecha */}
        <div className="al-card-row al-card-row--bottom">
          <div className="al-score-wrap">
            <div className="al-score-bar">
              <div
                className="al-score-fill"
                style={{
                  width: `${Math.round((score / 18) * 100)}%`,
                  background: score >= 11 ? '#dc2626' : score >= 6 ? '#d97706' : '#3b82f6',
                }}
              />
            </div>
            <span className="al-score-num">{score}/18</span>
          </div>
          <span className="al-date">{fmtDate(lead.created_at)} {fmtTime(lead.created_at)}</span>
        </div>
      </div>

      <ChevronRight size={14} className="al-card-arrow" />
    </div>
  );
}

// ── Panel de detalle ──────────────────────────────────────────────────────────

function LeadDetail({ lead, onClose }) {
  if (!lead) return null;
  const answers   = lead?.metadata?.automatik_answers || {};
  const score     = getScore(lead);
  const statusKey = getStatusFromScore(lead);
  const sm        = STATUS_META[statusKey] || STATUS_META.new;

  const rows = [
    { icon: <Briefcase size={14} />, label: 'Tipo de negocio',   val: BIZ_LABEL[answers.biz_type] || answers.biz_type },
    { icon: <Users size={14} />,     label: 'Tamaño del equipo', val: answers.team_size },
    { icon: <TrendingUp size={14} />,label: 'Leads / mes',       val: answers.monthly_leads },
    { icon: <BarChart2 size={14} />, label: 'Cierres / mes',     val: answers.monthly_closes },
    { icon: <MessageSquare size={14}/>,label:'Herramientas actuales', val: TOOLS_LABEL[answers.current_tools] || answers.current_tools },
    { icon: <DollarSign size={14} />,label: 'Inversión en ads',  val: ADS_LABEL[answers.ads_invest] || answers.ads_invest },
  ];

  return (
    <div className="al-detail">
      <div className="al-detail-header">
        <div>
          <h3 className="al-detail-name">{lead.name || '(sin nombre)'}</h3>
          <span className="al-meta"><Phone size={11} /> {lead.phone}</span>
        </div>
        <button className="ak-btn ak-btn-ghost ak-btn-icon" onClick={onClose}><X size={15} /></button>
      </div>

      {/* Temperatura + score */}
      <div className="al-detail-score-box" style={{ borderColor: sm.border, background: sm.bg }}>
        <span style={{ color: sm.color, fontWeight: 700, fontSize: 18 }}>{sm.label}</span>
        <div className="al-score-wrap" style={{ marginTop: 8 }}>
          <div className="al-score-bar al-score-bar--lg">
            <div
              className="al-score-fill"
              style={{
                width: `${Math.round((score / 18) * 100)}%`,
                background: score >= 11 ? '#dc2626' : score >= 6 ? '#d97706' : '#3b82f6',
              }}
            />
          </div>
          <span style={{ fontWeight: 700, fontSize: 15 }}>{score}/18</span>
        </div>
        <p style={{ fontSize: 12, color: sm.color, marginTop: 6, opacity: 0.8 }}>
          {score >= 11 ? 'Lead altamente calificado — agendar reunión' :
           score >= 6  ? 'Lead calificado — nutrir y hacer seguimiento' :
                         'Lead frío — handoff para atención manual'}
        </p>
      </div>

      {/* Problema principal + tags + oportunidades */}
      {(answers.main_problem || answers.problem_tags?.length > 0 || answers.opportunities?.length > 0) && (
        <div className="al-detail-section al-problem-section">
          <h4 className="al-detail-section-title">
            <AlertCircle size={13} style={{ marginRight: 5 }} />
            Problema detectado
          </h4>

          {answers.main_problem && (
            <p className="al-problem-text">"{answers.main_problem}"</p>
          )}

          {answers.problem_tags?.length > 0 && (
            <div className="al-problem-tags al-problem-tags--detail">
              {answers.problem_tags.map((t, i) => (
                <span key={i} className="al-problem-tag">⚠️ {t}</span>
              ))}
            </div>
          )}

          {answers.opportunities?.length > 0 && (
            <div className="al-opportunities">
              <span className="al-opp-label">
                <Lightbulb size={12} style={{ marginRight: 4 }} />
                Qué podemos ofrecerle:
              </span>
              <ul className="al-opp-list">
                {answers.opportunities.map((o, i) => (
                  <li key={i}>🎯 {o}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Respuestas del formulario */}
      <div className="al-detail-section">
        <h4 className="al-detail-section-title">Respuestas del Bot</h4>
        <div className="al-detail-answers">
          {rows.map(r => r.val ? (
            <div key={r.label} className="al-answer-row">
              <span className="al-answer-icon">{r.icon}</span>
              <div>
                <span className="al-answer-label">{r.label}</span>
                <span className="al-answer-val">{r.val}</span>
              </div>
            </div>
          ) : null)}
        </div>
      </div>

      {/* Historial de conversación (últimos mensajes) */}
      {lead.conversation_history?.length > 0 && (
        <div className="al-detail-section">
          <h4 className="al-detail-section-title">Últimos mensajes</h4>
          <div className="al-chat">
            {lead.conversation_history.slice(-8).map((m, i) => (
              <div key={i} className={`al-bubble al-bubble--${m.role === 'user' ? 'user' : 'bot'}`}>
                <span className="al-bubble-role">{m.role === 'user' ? lead.name || 'Lead' : 'Bot'}</span>
                <p>{m.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="al-detail-footer">
        <span className="al-meta">
          <Calendar size={11} /> Creado: {fmtDate(lead.created_at)} {fmtTime(lead.created_at)}
        </span>
        {lead.last_message_at && (
          <span className="al-meta">
            · Último msj: {fmtDate(lead.last_message_at)} {fmtTime(lead.last_message_at)}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

const STATUS_FILTERS = [
  { val: '',         label: 'Todos' },
  { val: 'hot',      label: '🔥 HOT' },
  { val: 'warm',     label: '☀️ WARM' },
  { val: 'cold',     label: '❄️ COLD' },
  { val: 'handoff',  label: '🤝 Handoff' },
];

export default function AutomatikLeads() {
  const [leads, setLeads]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [search, setSearch]         = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [selected, setSelected]     = useState(null);

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      const res = await axios.get(`${API}/superadmin/clients/leads`, { params });
      setLeads(res.data);
    } catch {
      toast.error('Error cargando leads');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  // Filtro de temperatura en cliente (calculado del score)
  const filtered = leads.filter(l => {
    if (!filterStatus) return true;
    return getStatusFromScore(l) === filterStatus;
  });

  // KPIs
  const total  = leads.length;
  const hot    = leads.filter(l => getStatusFromScore(l) === 'hot').length;
  const warm   = leads.filter(l => getStatusFromScore(l) === 'warm').length;
  const cold   = leads.filter(l => getStatusFromScore(l) === 'cold').length;
  const handoff= leads.filter(l => getStatusFromScore(l) === 'handoff').length;

  return (
    <div className="ak-dashboard">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Leads del Bot</h1>
          <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0', fontSize: 14 }}>
            Prospectos B2B calificados · automatik-media
          </p>
        </div>
        <button className="ak-btn ak-btn-ghost" onClick={fetchLeads} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Actualizar
        </button>
      </div>

      {/* KPIs */}
      <div className="al-kpi-row">
        <div className="al-kpi" onClick={() => setFilterStatus('')} data-active={!filterStatus}>
          <span className="al-kpi-num">{total}</span>
          <span className="al-kpi-lbl">Total</span>
        </div>
        <div className="al-kpi al-kpi--hot" onClick={() => setFilterStatus(filterStatus === 'hot' ? '' : 'hot')} data-active={filterStatus === 'hot'}>
          <span className="al-kpi-num">{hot}</span>
          <span className="al-kpi-lbl">🔥 HOT</span>
        </div>
        <div className="al-kpi al-kpi--warm" onClick={() => setFilterStatus(filterStatus === 'warm' ? '' : 'warm')} data-active={filterStatus === 'warm'}>
          <span className="al-kpi-num">{warm}</span>
          <span className="al-kpi-lbl">☀️ WARM</span>
        </div>
        <div className="al-kpi al-kpi--cold" onClick={() => setFilterStatus(filterStatus === 'cold' ? '' : 'cold')} data-active={filterStatus === 'cold'}>
          <span className="al-kpi-num">{cold}</span>
          <span className="al-kpi-lbl">❄️ COLD</span>
        </div>
        <div className="al-kpi al-kpi--handoff" onClick={() => setFilterStatus(filterStatus === 'handoff' ? '' : 'handoff')} data-active={filterStatus === 'handoff'}>
          <span className="al-kpi-num">{handoff}</span>
          <span className="al-kpi-lbl">🤝 Handoff</span>
        </div>
      </div>

      {/* Layout split: lista + detalle */}
      <div className="al-split">
        {/* Columna izquierda: lista */}
        <div className="al-list-col">
          {/* Buscador */}
          <div style={{ position: 'relative', marginBottom: 12 }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input
              className="ak-input"
              style={{ paddingLeft: 32 }}
              placeholder="Buscar por nombre o teléfono..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>Cargando...</div>
          ) : filtered.length === 0 ? (
            <div className="al-empty">
              <TrendingUp size={36} style={{ opacity: 0.2, marginBottom: 10 }} />
              <p>No hay leads {filterStatus ? `con temperatura ${filterStatus}` : 'registrados aún'}</p>
            </div>
          ) : (
            <div className="al-cards">
              {filtered.map(l => (
                <LeadCard
                  key={l.phone}
                  lead={l}
                  selected={selected?.phone === l.phone}
                  onClick={setSelected}
                />
              ))}
            </div>
          )}
        </div>

        {/* Columna derecha: detalle */}
        <div className="al-detail-col">
          {selected ? (
            <LeadDetail lead={selected} onClose={() => setSelected(null)} />
          ) : (
            <div className="al-detail-placeholder">
              <MessageSquare size={40} style={{ opacity: 0.15, marginBottom: 12 }} />
              <p>Seleccioná un lead para ver el detalle</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
