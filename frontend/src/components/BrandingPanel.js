import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Palette, Globe, Image as ImageIcon, Loader2, CheckCircle2, XCircle, Lock } from 'lucide-react';

export default function BrandingPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    brand_name: '',
    logo_url: '',
    primary_color: '#6366f1',
    custom_subdomain: '',
  });
  const [subCheck, setSubCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [planLocked, setPlanLocked] = useState(false);

  useEffect(() => {
    axios.get(`${API}/branding`)
      .then(r => {
        setData(r.data);
        setForm({
          brand_name: r.data.brand_name || '',
          logo_url: r.data.logo_url || '',
          primary_color: r.data.primary_color || '#6366f1',
          custom_subdomain: r.data.custom_subdomain || '',
        });
      })
      .catch(err => {
        if (err.response?.status === 404) {
          toast.info('Configurá tu negocio primero');
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const checkSubdomain = async (sub) => {
    if (!sub || sub === data?.custom_subdomain) {
      setSubCheck(null);
      return;
    }
    setChecking(true);
    try {
      const res = await axios.get(`${API}/branding/check-subdomain/${sub}`);
      setSubCheck(res.data);
    } catch {
      setSubCheck({ available: false, reason: 'error' });
    } finally {
      setChecking(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/branding`, form);
      toast.success('Branding actualizado');
      const r = await axios.get(`${API}/branding`);
      setData(r.data);
    } catch (err) {
      if (err.response?.status === 403) {
        setPlanLocked(true);
        toast.error(err.response.data.detail);
      } else {
        toast.error(err.response?.data?.detail || 'Error guardando');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <Card><CardContent><div className="roi-loading">Cargando branding...</div></CardContent></Card>;
  }

  if (planLocked) {
    return (
      <Card className="branding-panel" data-testid="branding-locked">
        <CardContent className="branding-locked-content">
          <Lock className="w-10 h-10" />
          <h3>Whitelabel disponible en plan Pro+</h3>
          <p>Subdominio custom, logo propio y colores de marca están incluidos en los planes Pro y Enterprise.</p>
          <Button onClick={() => window.location.href = '/config'}>Ver planes</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="branding-panel" data-testid="branding-panel">
      <CardHeader>
        <CardTitle className="branding-title">
          <Palette className="w-5 h-5" /> Marca · Whitelabel
        </CardTitle>
        <p className="branding-sub">
          Personalizá cómo ven tus clientes al InmoBot: subdominio propio, logo y color de marca.
        </p>
      </CardHeader>
      <CardContent>
        <div className="branding-grid">
          <div className="branding-field">
            <label>
              <Globe className="w-3 h-3 inline" /> Subdominio custom
            </label>
            <div className="branding-subdomain-input">
              <input
                value={form.custom_subdomain}
                onChange={e => {
                  const v = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
                  setForm({ ...form, custom_subdomain: v });
                  if (v.length >= 2) checkSubdomain(v);
                  else setSubCheck(null);
                }}
                placeholder="miempresa"
                maxLength={32}
                data-testid="input-subdomain"
              />
              <span className="branding-subdomain-suffix">.inmobot.app</span>
            </div>
            {checking && <small><Loader2 className="w-3 h-3 inline animate-spin" /> Verificando...</small>}
            {subCheck && !checking && (
              subCheck.available ? (
                <small className="branding-ok" data-testid="subdomain-ok">
                  <CheckCircle2 className="w-3 h-3 inline" /> Disponible: {subCheck.url}
                </small>
              ) : (
                <small className="branding-err" data-testid="subdomain-err">
                  <XCircle className="w-3 h-3 inline" /> No disponible ({subCheck.reason})
                </small>
              )
            )}
          </div>

          <div className="branding-field">
            <label>
              <ImageIcon className="w-3 h-3 inline" /> URL del logo
            </label>
            <input
              value={form.logo_url}
              onChange={e => setForm({ ...form, logo_url: e.target.value })}
              placeholder="https://cdn.example.com/logo.png"
              maxLength={200}
              data-testid="input-logo-url"
            />
            {form.logo_url && (
              <img
                src={form.logo_url}
                alt="Logo preview"
                className="branding-logo-preview"
                onError={e => { e.target.style.display = 'none'; }}
              />
            )}
          </div>

          <div className="branding-field">
            <label>Nombre de marca</label>
            <input
              value={form.brand_name}
              onChange={e => setForm({ ...form, brand_name: e.target.value })}
              placeholder={data?.business_name || 'Mi Empresa'}
              maxLength={100}
              data-testid="input-brand-name"
            />
          </div>

          <div className="branding-field">
            <label>Color primario</label>
            <div className="branding-color-input">
              <input
                type="color"
                value={form.primary_color}
                onChange={e => setForm({ ...form, primary_color: e.target.value })}
                data-testid="input-primary-color"
              />
              <input
                type="text"
                value={form.primary_color}
                onChange={e => {
                  const v = e.target.value;
                  if (/^#[0-9a-fA-F]{0,6}$/.test(v) || v === '') {
                    setForm({ ...form, primary_color: v });
                  }
                }}
                placeholder="#6366f1"
                maxLength={7}
              />
            </div>
          </div>
        </div>

        <div className="branding-preview">
          <span className="branding-preview-label">Preview:</span>
          <div
            className="branding-preview-card"
            style={{ borderTopColor: form.primary_color }}
          >
            {form.logo_url && (
              <img src={form.logo_url} alt="" className="branding-preview-logo" onError={e => { e.target.style.display = 'none'; }} />
            )}
            <strong>{form.brand_name || data?.business_name || 'Tu Marca'}</strong>
            {form.custom_subdomain && (
              <small>{form.custom_subdomain}.inmobot.app</small>
            )}
          </div>
        </div>

        <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
          <Button
            onClick={handleSave}
            disabled={saving || (subCheck && !subCheck.available && form.custom_subdomain !== data?.custom_subdomain)}
            data-testid="btn-save-branding"
          >
            {saving ? <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Guardando...</> : 'Guardar cambios'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
