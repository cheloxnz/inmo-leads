import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Sparkles, ArrowRight, CheckCircle2, Bot, Rocket, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function Signup() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Atribución persistente: si llega con ?ref=, lo guardamos en localStorage
  // para no perder atribución si el usuario navega/recarga antes de completar signup.
  const REF_STORAGE_KEY = 'inmobot_ref_attribution';
  const REF_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 días

  const queryRef = searchParams.get('ref') || '';
  const queryRefCelebration = searchParams.get('ref_celebration_id') || '';

  // Persistencia
  useEffect(() => {
    if (queryRef) {
      try {
        localStorage.setItem(REF_STORAGE_KEY, JSON.stringify({
          ref: queryRef,
          ref_celebration_id: queryRefCelebration || null,
          utm_source: searchParams.get('utm_source') || null,
          utm_medium: searchParams.get('utm_medium') || null,
          utm_campaign: searchParams.get('utm_campaign') || null,
          stored_at: Date.now(),
        }));
      } catch (e) { /* localStorage not available */ }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryRef, queryRefCelebration]);

  // Resolver ref efectivo: query param > localStorage (no expirado)
  const persistedRef = (() => {
    if (queryRef) return { ref: queryRef, ref_celebration_id: queryRefCelebration };
    try {
      const raw = localStorage.getItem(REF_STORAGE_KEY);
      if (!raw) return { ref: '', ref_celebration_id: '' };
      const parsed = JSON.parse(raw);
      if (!parsed.stored_at || Date.now() - parsed.stored_at > REF_TTL_MS) {
        localStorage.removeItem(REF_STORAGE_KEY);
        return { ref: '', ref_celebration_id: '' };
      }
      return { ref: parsed.ref || '', ref_celebration_id: parsed.ref_celebration_id || '' };
    } catch (e) {
      return { ref: '', ref_celebration_id: '' };
    }
  })();
  const refTenantId = persistedRef.ref;
  const refCelebrationId = persistedRef.ref_celebration_id;

  const [refBusiness, setRefBusiness] = useState('');
  const [step, setStep] = useState(1);
  const [data, setData] = useState({
    business_name: '',
    description: '',
    template_id: '',
    email: '',
    password: '',
  });
  const [tenantSuggested, setTenantSuggested] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  // Si vino con ?ref=, fetchear el business_name del referrer para el badge
  useEffect(() => {
    if (!refTenantId) return;
    axios.get(`${BACKEND}/api/public/catalog/${encodeURIComponent(refTenantId)}`)
      .then(r => setRefBusiness(r.data?.tenant?.business_name || r.data?.tenant?.name || ''))
      .catch(() => { /* ref invalido o tenant inactivo, ignorar */ });
  }, [refTenantId]);

  const update = (k, v) => setData(prev => ({ ...prev, [k]: v }));

  const suggestTenantId = async () => {
    if (!data.business_name.trim()) return;
    try {
      const res = await axios.post(`${BACKEND}/api/onboarding/suggest-tenant-id`, {
        business_name: data.business_name,
      });
      setTenantSuggested(res.data.tenant_id);
    } catch (err) {}
  };

  const goToStep2 = async () => {
    if (!data.business_name.trim() || !data.description.trim()) {
      toast.error('Completá nombre y descripción del negocio');
      return;
    }
    if (data.description.length < 20) {
      toast.error('Describí tu negocio con un poco más de detalle (mínimo 20 caracteres)');
      return;
    }
    await suggestTenantId();
    setStep(2);
  };

  const submit = async () => {
    if (!data.email.trim() || !data.password.trim()) {
      toast.error('Completá email y password');
      return;
    }
    if (data.password.length < 8) {
      toast.error('La contraseña debe tener al menos 8 caracteres');
      return;
    }
    setSubmitting(true);
    try {
      const payload = { ...data };
      if (refTenantId) payload.ref = refTenantId;
      if (refCelebrationId) payload.ref_celebration_id = refCelebrationId;
      const res = await axios.post(`${BACKEND}/api/onboarding/auto-setup`, payload);
      setResult(res.data);
      // Guardar token para auto-login
      localStorage.setItem('token', res.data.access_token);
      localStorage.setItem('user', JSON.stringify(res.data.user));
      // Limpiar atribución persistida tras conversión exitosa
      try { localStorage.removeItem(REF_STORAGE_KEY); } catch (e) { /* noop */ }
      setStep(3);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error en el registro');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="signup-wizard" data-testid="signup-wizard">
      <div className="sw-header">
        <Bot className="w-8 h-8 text-purple-500" />
        <h1>Empezá con InmoBot</h1>
        <p>Tu bot de WhatsApp con IA listo en 60 segundos.</p>
        {refBusiness && (
          <div
            data-testid="signup-ref-badge"
            className="inline-flex items-center gap-2 mt-2 px-3 py-1.5 bg-amber-50 border border-amber-300 rounded-full text-xs text-amber-800"
          >
            <UserPlus className="w-3 h-3" />
            Te trajo <strong>{refBusiness}</strong>
          </div>
        )}
        <div className="sw-stepper">
          <div className={`sw-step ${step > 1 ? 'completed' : step === 1 ? 'active' : ''}`}>1. Tu negocio</div>
          <div className={`sw-step ${step > 2 ? 'completed' : step === 2 ? 'active' : ''}`}>2. Tu cuenta</div>
          <div className={`sw-step ${step === 3 ? 'active' : ''}`}>3. ¡Listo!</div>
        </div>
      </div>

      <Card className="sw-card">
        {step === 1 && (
          <CardContent className="sw-step-content">
            <CardHeader className="px-0 pt-0">
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-500" />
                Contanos sobre tu negocio
              </CardTitle>
            </CardHeader>

            <div className="sw-field">
              <Label htmlFor="bn">Nombre del negocio</Label>
              <Input
                id="bn"
                value={data.business_name}
                onChange={e => update('business_name', e.target.value)}
                placeholder="Ej: Clínica Odontológica San Martín"
                data-testid="sw-business-name"
              />
            </div>

            <div className="sw-field">
              <Label htmlFor="desc">Describí tu negocio en una línea</Label>
              <textarea
                id="desc"
                className="sw-textarea"
                value={data.description}
                onChange={e => update('description', e.target.value)}
                placeholder="Soy una clínica odontológica en Buenos Aires especializada en implantes y limpieza dental"
                rows={3}
                maxLength={500}
                data-testid="sw-description"
              />
              <small className="sw-hint">La IA va a generar tu landing y catálogo demo desde acá. Sé específico: rubro, ubicación, especialidad.</small>
            </div>

            <div className="sw-field">
              <Label>Rubro (opcional - se detecta solo)</Label>
              <select
                className="sw-select"
                value={data.template_id}
                onChange={e => update('template_id', e.target.value)}
                data-testid="sw-template"
              >
                <option value="">🤖 Detectar automáticamente</option>
                <option value="inmobiliaria">🏠 Inmobiliaria</option>
                <option value="clinica">🏥 Clínica / Salud</option>
                <option value="restaurante">🍕 Restaurante</option>
                <option value="ecommerce">🛍️ E-commerce</option>
                <option value="servicios">💼 Servicios profesionales</option>
              </select>
            </div>

            <Button onClick={goToStep2} className="w-full sw-step1-btn" data-testid="sw-step1-next">
              Siguiente <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </CardContent>
        )}

        {step === 2 && (
          <CardContent className="sw-step-content">
            <CardHeader className="px-0 pt-0">
              <CardTitle>Crea tu cuenta de admin</CardTitle>
            </CardHeader>

            {tenantSuggested && (
              <div className="sw-tenant-info" data-testid="sw-tenant-suggested">
                Tu URL será: <strong>/inicio/{tenantSuggested}</strong>
              </div>
            )}

            <div className="sw-field">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={data.email} onChange={e => update('email', e.target.value)} placeholder="tu@email.com" data-testid="sw-email" />
            </div>

            <div className="sw-field">
              <Label htmlFor="pwd">Contraseña</Label>
              <Input id="pwd" type="password" value={data.password} onChange={e => update('password', e.target.value)} placeholder="Min 8 caracteres" data-testid="sw-password" />
            </div>

            <div className="sw-actions-row">
              <Button variant="outline" onClick={() => setStep(1)}>Atrás</Button>
              <Button onClick={submit} disabled={submitting} className="flex-1" data-testid="sw-submit">
                <Rocket className="w-4 h-4 mr-1" />
                {submitting ? 'Creando tu bot...' : 'Crear mi bot'}
              </Button>
            </div>
          </CardContent>
        )}

        {step === 3 && result && (
          <CardContent className="sw-step-content sw-success">
            <div className="sw-success-icon">
              <CheckCircle2 className="w-16 h-16 text-green-500" />
            </div>
            <h2>¡Tu bot está listo! 🎉</h2>
            <ul className="sw-result-list">
              <li>✅ Tenant: <code>{result.tenant_id}</code></li>
              <li>✅ Rubro detectado: <strong>{result.template_id}</strong></li>
              <li>✅ Catálogo demo: {result.products_seeded} productos</li>
              <li>{result.ai_enabled ? '✅' : '⚠️'} Landing {result.ai_enabled ? 'generada con IA' : 'creada con plantilla'}</li>
            </ul>
            <div className="sw-result-actions">
              <Button asChild variant="outline" data-testid="sw-view-landing">
                <a href={result.landing_url} target="_blank" rel="noopener noreferrer">Ver mi landing</a>
              </Button>
              <Button onClick={() => navigate('/dashboard')} data-testid="sw-go-dashboard">
                Ir al dashboard <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
