import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Trash2, ExternalLink, Save, Eye, Sparkles, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { ALL_TEMPLATES } from '../data/landingTemplates';
import { evaluateColorContrast } from '../utils/colorContrast';

const ICON_OPTIONS = ['home', 'calendar', 'message', 'shield', 'bot'];

function ContrastHint({ result }) {
  if (!result) return null;
  const cls = `le-contrast le-contrast-${result.level}`;
  const Icon = result.level === 'fail' ? AlertTriangle : CheckCircle2;
  return (
    <div className={cls} data-testid={`contrast-${result.level}`}>
      <Icon className="w-3 h-3" />
      <span>{result.message}</span>
    </div>
  );
}

export default function LandingEditor() {
  const [data, setData] = useState({
    business_name: '',
    business_tagline: '',
    contact_phone: '',
    whatsapp_display_phone: '',
    template_id: 'servicios',
    logo_url: '',
    primary_color: '#3b82f6',
    accent_color: '#8b5cf6',
    custom_features: [],
    custom_steps: [],
    tenant_id: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [aiDescription, setAiDescription] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  const fetchBranding = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/auth/tenant/branding`);
      setData(prev => ({
        ...prev,
        ...res.data,
        primary_color: res.data.primary_color || '#3b82f6',
        accent_color: res.data.accent_color || '#8b5cf6',
        template_id: res.data.template_id || 'servicios',
        custom_features: res.data.custom_features || [],
        custom_steps: res.data.custom_steps || [],
      }));
    } catch (err) {
      toast.error('Error cargando branding');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchBranding(); }, [fetchBranding]);

  const update = (field, value) => setData(prev => ({ ...prev, [field]: value }));

  const updateFeature = (i, field, value) => {
    setData(prev => {
      const features = [...prev.custom_features];
      features[i] = { ...features[i], [field]: value };
      return { ...prev, custom_features: features };
    });
  };

  const addFeature = () => {
    if (data.custom_features.length >= 5) return;
    setData(prev => ({
      ...prev,
      custom_features: [...prev.custom_features, { icon: 'bot', title: 'Nuevo feature', desc: 'Descripción' }]
    }));
  };

  const removeFeature = (i) => {
    setData(prev => ({
      ...prev,
      custom_features: prev.custom_features.filter((_, idx) => idx !== i)
    }));
  };

  const useTemplateDefaults = () => {
    const tpl = ALL_TEMPLATES[data.template_id];
    if (!tpl) return;
    if (window.confirm('Esto reemplazará los features/pasos personalizados con los del template. ¿Continuar?')) {
      setData(prev => ({
        ...prev,
        custom_features: tpl.features.map(f => ({ ...f })),
        custom_steps: tpl.steps.map(s => ({ ...s })),
      }));
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        business_name: data.business_name,
        business_tagline: data.business_tagline,
        contact_phone: data.contact_phone,
        whatsapp_display_phone: data.whatsapp_display_phone,
        template_id: data.template_id,
        logo_url: data.logo_url,
        primary_color: data.primary_color,
        accent_color: data.accent_color,
        custom_features: data.custom_features,
        custom_steps: data.custom_steps,
      };
      await axios.put(`${API}/auth/tenant/branding`, payload);
      toast.success('Branding guardado');
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail?.validation_errors) {
        toast.error(detail.validation_errors.join(', '));
      } else {
        toast.error(detail || 'Error guardando');
      }
    } finally {
      setSaving(false);
    }
  };

  const generateWithAi = async () => {
    if (!aiDescription.trim()) {
      toast.error('Describí tu negocio en una línea');
      return;
    }
    setAiLoading(true);
    try {
      const res = await axios.post(`${API}/auth/tenant/branding/ai-generate`, { description: aiDescription });
      const r = res.data;
      if (!r.ai_enabled) {
        toast.warning('IA no configurada en este tenant. Configurá tu OpenAI API Key en /configuracion.');
        return;
      }
      setData(prev => ({
        ...prev,
        business_tagline: r.business_tagline || prev.business_tagline,
        custom_features: r.features?.length ? r.features : prev.custom_features,
        custom_steps: r.steps?.length ? r.steps : prev.custom_steps,
      }));
      toast.success('Copy generado por IA. Revisalo y ajustá lo que necesites.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error generando copy');
    } finally {
      setAiLoading(false);
    }
  };

  const primaryContrast = evaluateColorContrast(data.primary_color);
  const accentContrast = evaluateColorContrast(data.accent_color);

  const previewUrl = data.tenant_id ? `/inicio/${data.tenant_id}` : '';

  if (loading) return <div className="le-loading">Cargando editor...</div>;

  return (
    <div className="landing-editor" data-testid="landing-editor">
      <div className="le-header">
        <div>
          <h1>Editor de Landing</h1>
          <p>Personalizá la landing pública de tu negocio. Los cambios son inmediatos.</p>
        </div>
        <div className="le-header-actions">
          {previewUrl && (
            <Button variant="outline" asChild data-testid="le-preview-btn">
              <a href={previewUrl} target="_blank" rel="noopener noreferrer">
                <Eye className="w-4 h-4 mr-1" /> Preview
                <ExternalLink className="w-3 h-3 ml-1" />
              </a>
            </Button>
          )}
          <Button onClick={save} disabled={saving} data-testid="le-save-btn">
            <Save className="w-4 h-4 mr-1" />
            {saving ? 'Guardando...' : 'Guardar'}
          </Button>
        </div>
      </div>

      <div className="le-grid">
        {/* Form */}
        <div className="le-form">
          <Card className="le-ai-box">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-500" /> Generar con IA
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="le-ai-hint">Describí tu negocio en una línea y la IA genera tagline + features + pasos.</p>
              <div className="le-ai-input">
                <Input
                  value={aiDescription}
                  onChange={e => setAiDescription(e.target.value)}
                  placeholder="Soy una clínica odontológica en Buenos Aires especializada en implantes"
                  data-testid="le-ai-input"
                />
                <Button onClick={generateWithAi} disabled={aiLoading} data-testid="le-ai-generate">
                  <Sparkles className="w-4 h-4 mr-1" />
                  {aiLoading ? 'Generando...' : 'Generar'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-sm">Información del negocio</CardTitle></CardHeader>
            <CardContent className="le-fields">
              <div>
                <Label htmlFor="le-bn">Nombre del negocio</Label>
                <Input id="le-bn" value={data.business_name || ''} onChange={e => update('business_name', e.target.value)} data-testid="le-business-name" />
              </div>
              <div>
                <Label htmlFor="le-bt">Tagline</Label>
                <Input id="le-bt" value={data.business_tagline || ''} onChange={e => update('business_tagline', e.target.value)} placeholder="Ej: Tu salud, nuestra prioridad" data-testid="le-tagline" />
              </div>
              <div>
                <Label htmlFor="le-tel">WhatsApp principal (con código país)</Label>
                <Input id="le-tel" value={data.contact_phone || ''} onChange={e => update('contact_phone', e.target.value)} placeholder="5491133334444" data-testid="le-phone" />
                <small className="le-helper">Número que recibe los mensajes del bot.</small>
              </div>
              <div>
                <Label htmlFor="le-tel-display">WhatsApp para mostrar (opcional)</Label>
                <Input id="le-tel-display" value={data.whatsapp_display_phone || ''} onChange={e => update('whatsapp_display_phone', e.target.value)} placeholder="Igual que el principal si lo dejás vacío" data-testid="le-phone-display" />
                <small className="le-helper">Si querés que la landing muestre un número diferente al que opera el bot.</small>
              </div>
              <div>
                <Label htmlFor="le-tpl">Rubro / Template</Label>
                <select
                  id="le-tpl"
                  value={data.template_id}
                  onChange={e => update('template_id', e.target.value)}
                  className="le-select"
                  data-testid="le-template"
                >
                  {Object.entries(ALL_TEMPLATES).map(([id, t]) => (
                    <option key={id} value={id}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="le-logo">URL del logo</Label>
                <Input id="le-logo" value={data.logo_url || ''} onChange={e => update('logo_url', e.target.value)} placeholder="https://..." data-testid="le-logo-url" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-sm">Colores</CardTitle></CardHeader>
            <CardContent className="le-colors">
              <div>
                <Label>Color primario</Label>
                <div className="le-color-input">
                  <input type="color" value={data.primary_color} onChange={e => update('primary_color', e.target.value)} data-testid="le-primary-color" />
                  <Input value={data.primary_color} onChange={e => update('primary_color', e.target.value)} />
                </div>
                <ContrastHint result={primaryContrast} />
              </div>
              <div>
                <Label>Color de acento</Label>
                <div className="le-color-input">
                  <input type="color" value={data.accent_color} onChange={e => update('accent_color', e.target.value)} data-testid="le-accent-color" />
                  <Input value={data.accent_color} onChange={e => update('accent_color', e.target.value)} />
                </div>
                <ContrastHint result={accentContrast} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center justify-between">
                <span>Features personalizados ({data.custom_features.length}/5)</span>
                <button onClick={useTemplateDefaults} className="le-btn-link" data-testid="le-use-defaults">Usar default del template</button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.custom_features.length === 0 && (
                <p className="le-empty">Sin features personalizados. Se mostrarán los del template ({ALL_TEMPLATES[data.template_id]?.label}).</p>
              )}
              {data.custom_features.map((f, i) => (
                <div key={i} className="le-feature-row" data-testid={`le-feature-${i}`}>
                  <select value={f.icon || 'bot'} onChange={e => updateFeature(i, 'icon', e.target.value)} className="le-select-small">
                    {ICON_OPTIONS.map(ic => <option key={ic} value={ic}>{ic}</option>)}
                  </select>
                  <Input value={f.title || ''} onChange={e => updateFeature(i, 'title', e.target.value)} placeholder="Título" />
                  <Input value={f.desc || ''} onChange={e => updateFeature(i, 'desc', e.target.value)} placeholder="Descripción" />
                  <button onClick={() => removeFeature(i)} className="le-btn-icon" title="Eliminar">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              {data.custom_features.length < 5 && (
                <Button variant="outline" size="sm" onClick={addFeature} data-testid="le-add-feature">
                  <Plus className="w-4 h-4 mr-1" /> Agregar feature
                </Button>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Preview */}
        <div className="le-preview">
          <div className="le-preview-label">Vista previa</div>
          <div className="le-preview-frame" style={{ '--primary': data.primary_color, '--accent': data.accent_color }}>
            <div className="le-prev-nav">
              {data.logo_url
                ? <img src={data.logo_url} alt="logo" className="le-prev-logo" />
                : <div className="le-prev-logo-ph" style={{ background: data.primary_color }}>{(data.business_name || 'X').charAt(0)}</div>}
              <span>{data.business_name || 'Tu negocio'}</span>
            </div>
            <div className="le-prev-hero">
              <div className="le-prev-badge" style={{ background: data.primary_color }}>IA 24/7</div>
              <h2>{data.business_name || 'Tu negocio'}</h2>
              {data.business_tagline && <p>{data.business_tagline}</p>}
              <button className="le-prev-cta" style={{ background: `linear-gradient(135deg, ${data.primary_color}, ${data.accent_color})` }}>
                Escribinos por WhatsApp
              </button>
            </div>
            <div className="le-prev-features">
              {(data.custom_features.length > 0 ? data.custom_features : ALL_TEMPLATES[data.template_id]?.features || []).slice(0, 3).map((f, i) => (
                <div key={i} className="le-prev-feature">
                  <div className="le-prev-feature-icon" style={{ color: data.primary_color }}>•</div>
                  <strong>{f.title}</strong>
                  <p>{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
