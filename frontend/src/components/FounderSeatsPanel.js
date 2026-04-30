import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Crown, Users, Lock, Unlock, RefreshCw, Check, AlertTriangle } from 'lucide-react';

export default function FounderSeatsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState({ total: 50, boost: 8, closes_at: '2026-05-31', active: true });
  const [justSaved, setJustSaved] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const res = await axios.get(`${API}/superadmin/founder-seats/config`);
      setData(res.data);
      setDraft({
        total: res.data.config.total ?? 50,
        boost: res.data.config.boost ?? 0,
        closes_at: res.data.config.closes_at ?? '',
        active: res.data.config.active !== false,
      });
    } catch (err) {
      setError(err?.response?.data?.detail || 'Error al cargar config');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const save = async (overrides = {}) => {
    setSaving(true);
    setError('');
    try {
      const payload = { ...draft, ...overrides };
      const res = await axios.put(`${API}/superadmin/founder-seats/config`, payload);
      setData({
        ...data,
        config: res.data.config,
        public_state: res.data.public_state,
      });
      setDraft({
        total: res.data.config.total,
        boost: res.data.config.boost,
        closes_at: res.data.config.closes_at,
        active: res.data.config.active !== false,
      });
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2000);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const invalidate = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/superadmin/founder-seats/invalidate-cache`);
      await fetchData();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = (value) => {
    setDraft({ ...draft, active: value });
    save({ active: value });
  };

  if (loading) return <Card><CardContent>Cargando...</CardContent></Card>;

  const s = data?.public_state || {};
  const taken = s.taken ?? 0;
  const total = s.total ?? 50;
  const left = s.left ?? total;
  const pct = total > 0 ? Math.min(100, (taken / total) * 100) : 0;
  const isOpen = s.is_open !== false;

  return (
    <Card data-testid="founder-seats-panel">
      <CardHeader>
        <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Crown size={20} style={{ color: '#f59e0b' }} />
          Plan Fundador
          {isOpen ? (
            <span style={{ background: '#10b98122', color: '#10b981', padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 700 }}>
              <Unlock size={12} style={{ display: 'inline', marginRight: 4 }} /> ABIERTO
            </span>
          ) : (
            <span style={{ background: '#ef444422', color: '#ef4444', padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 700 }}>
              <Lock size={12} style={{ display: 'inline', marginRight: 4 }} /> CERRADO
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        {error && (
          <div data-testid="fs-error" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '10px 14px', borderRadius: 8, fontSize: 13, display: 'flex', gap: 8, alignItems: 'center' }}>
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {/* Progress */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#6b7280', marginBottom: 6 }}>
            <span><Users size={14} style={{ display: 'inline', marginRight: 4 }} /> Cupos tomados</span>
            <strong data-testid="fs-taken-display" style={{ color: '#111' }}>{taken} / {total}</strong>
          </div>
          <div style={{ background: '#e5e7eb', borderRadius: 999, height: 10, overflow: 'hidden' }}>
            <div data-testid="fs-progress-bar" style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg,#8b5cf6,#6366f1)', transition: 'width 0.5s', borderRadius: 999 }} />
          </div>
          <div style={{ marginTop: 6, fontSize: 12, color: '#6b7280' }}>
            Reales: <strong>{data?.real_founders_count ?? 0}</strong> · Boost manual: <strong>{data?.config?.boost ?? 0}</strong> · Quedan <strong style={{ color: left <= 5 ? '#ef4444' : '#111' }}>{left}</strong>
          </div>
        </div>

        {/* Switches */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#f9fafb', padding: '12px 16px', borderRadius: 12 }}>
          <div>
            <Label style={{ fontWeight: 700, display: 'block' }}>Plan abierto a nuevos clientes</Label>
            <span style={{ fontSize: 12, color: '#6b7280' }}>Si lo desactivás, la landing Shopify muestra "CUPOS AGOTADOS"</span>
          </div>
          <Switch
            data-testid="fs-active-switch"
            checked={draft.active}
            onCheckedChange={toggleActive}
            disabled={saving}
          />
        </div>

        {/* Editable fields */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
          <div>
            <Label>Total de cupos</Label>
            <Input
              data-testid="fs-total-input"
              type="number"
              min={1}
              max={10000}
              value={draft.total}
              onChange={(e) => setDraft({ ...draft, total: parseInt(e.target.value, 10) || 0 })}
            />
          </div>
          <div>
            <Label>Boost manual</Label>
            <Input
              data-testid="fs-boost-input"
              type="number"
              min={0}
              max={10000}
              value={draft.boost}
              onChange={(e) => setDraft({ ...draft, boost: parseInt(e.target.value, 10) || 0 })}
            />
          </div>
          <div>
            <Label>Cierre (YYYY-MM-DD)</Label>
            <Input
              data-testid="fs-closes-input"
              type="date"
              value={draft.closes_at || ''}
              onChange={(e) => setDraft({ ...draft, closes_at: e.target.value })}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Button
            data-testid="fs-save-btn"
            onClick={() => save()}
            disabled={saving}
            style={{ background: justSaved ? '#10b981' : undefined }}
          >
            {justSaved ? <><Check size={16} style={{ marginRight: 6 }} /> Guardado</> : (saving ? 'Guardando...' : 'Guardar cambios')}
          </Button>
          <Button
            data-testid="fs-refresh-btn"
            variant="outline"
            onClick={invalidate}
            disabled={saving}
            title="Recalcular cupos reales desde DB y limpiar cache"
          >
            <RefreshCw size={14} style={{ marginRight: 6 }} /> Recalcular
          </Button>
        </div>

        <details style={{ fontSize: 12, color: '#6b7280', background: '#f9fafb', padding: '8px 14px', borderRadius: 8 }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600 }}>💡 Cómo funciona</summary>
          <div style={{ marginTop: 8, lineHeight: 1.6 }}>
            <strong>Total</strong>: cupos del plan fundador. Cuando se alcanza, el plan se cierra automáticamente.<br/>
            <strong>Boost manual</strong>: número que se suma al conteo real para arrancar en ≠ 0 al lanzamiento (ej. "ya tenemos 8 clientes"). Ajustá manualmente a medida que cerrés ventas que no vinieron del flujo de signup.<br/>
            <strong>Cierre</strong>: fecha después de la cual el plan queda cerrado aunque queden cupos.<br/>
            <strong>Endpoint público</strong>: <code>GET /api/public/founder-seats</code> (no auth, cache 30s) consumido por la landing Shopify.
          </div>
        </details>
      </CardContent>
    </Card>
  );
}
