import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import {
  CheckCircle2, AlertCircle, ExternalLink, Copy, Eye, EyeOff, Save, Zap,
} from 'lucide-react';

/**
 * Sección de configuración WhatsApp Cloud API por tenant.
 *
 * Lee y escribe en /api/config/whatsapp (sólo admin del tenant).
 * - Phone Number ID, Access Token, Business Account ID, Webhook Verify Token.
 * - Webhook URL es read-only (la pega el tenant en Meta).
 * - Incluye instrucciones paso a paso para registrar el negocio en Meta.
 */
export default function WhatsAppConfigSection() {
  const [data, setData] = useState({
    whatsapp_phone_number_id: '',
    whatsapp_access_token: '',
    whatsapp_business_account_id: '',
    webhook_verify_token: '',
    webhook_url: '',
    configured: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [showToken, setShowToken] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    fetch();
  }, []);

  const fetch = async () => {
    try {
      const res = await axios.get(`${API}/config/whatsapp`);
      setData(res.data);
      // Si el tenant ya tiene un test previo persistido, lo mostramos
      if (res.data.last_check) {
        setTestResult(res.data.last_check);
      }
    } catch (err) {
      console.error('Error fetching whatsapp config:', err);
      toast.error('Error cargando configuración WhatsApp');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setData((prev) => ({ ...prev, [field]: value }));
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        whatsapp_phone_number_id: data.whatsapp_phone_number_id || '',
        whatsapp_business_account_id: data.whatsapp_business_account_id || '',
        webhook_verify_token: data.webhook_verify_token || '',
      };
      // Solo mandamos el access_token si NO está enmascarado (ej: el user lo cambió)
      if (
        data.whatsapp_access_token &&
        !data.whatsapp_access_token.startsWith('***')
      ) {
        payload.whatsapp_access_token = data.whatsapp_access_token;
      }
      const res = await axios.put(`${API}/config/whatsapp`, payload);
      toast.success('Configuración WhatsApp guardada');
      // El backend dispara auto-test post-save y devuelve el resultado
      if (res.data?.test) {
        setTestResult(res.data.test);
        if (res.data.test.ok) {
          toast.success('Conexión a Meta verificada');
        } else if (res.data.test.status !== 'missing_credentials') {
          toast.warning('Conexión guardada pero el test falló — revisá los detalles');
        }
      }
      await fetch();
    } catch (err) {
      console.error('Error saving:', err);
      toast.error('Error guardando: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await axios.post(`${API}/config/whatsapp/test`);
      setTestResult(res.data);
      if (res.data.ok) {
        toast.success(res.data.message);
      } else {
        toast.error(res.data.message);
      }
    } catch (err) {
      console.error('Test error:', err);
      setTestResult({
        ok: false,
        status: 'api_error',
        message: 'Error: ' + (err.response?.data?.detail || err.message),
        details: {},
      });
      toast.error('Error probando conexión');
    } finally {
      setTesting(false);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copiado`);
  };

  if (loading) {
    return (
      <Card data-testid="whatsapp-section">
        <CardHeader>
          <CardTitle>Integración WhatsApp Business</CardTitle>
        </CardHeader>
        <CardContent>Cargando...</CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="whatsapp-section" className="whatsapp-config-card">
      <CardHeader>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Integración WhatsApp Business
            {data.configured ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#16a34a', background: '#dcfce7', padding: '2px 10px', borderRadius: 12, fontWeight: 600 }}>
                <CheckCircle2 className="w-3 h-3" /> Conectado
              </span>
            ) : (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#b45309', background: '#fef3c7', padding: '2px 10px', borderRadius: 12, fontWeight: 600 }}>
                <AlertCircle className="w-3 h-3" /> Pendiente
              </span>
            )}
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowHelp(!showHelp)}
            data-testid="btn-toggle-wa-help"
          >
            {showHelp ? 'Ocultar instrucciones' : '¿Cómo obtengo estos datos?'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {showHelp && (
          <div className="wa-help-box" style={{
            background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10,
            padding: '16px 20px', marginBottom: 20, fontSize: 13, color: '#1e3a8a', lineHeight: 1.7,
          }}>
            <strong style={{ fontSize: 14 }}>📱 Cómo conectar tu WhatsApp Business</strong>
            <p style={{ margin: '8px 0' }}>
              Necesitás registrar tu negocio en Meta Business antes de configurar acá. Es el paso 1, no se evita.
            </p>
            <ol style={{ margin: '10px 0 0 18px', padding: 0 }}>
              <li>
                Andá a <a href="https://business.facebook.com" target="_blank" rel="noreferrer" style={{ color: '#1d4ed8', textDecoration: 'underline' }}>business.facebook.com <ExternalLink className="w-3 h-3" style={{ display: 'inline' }} /></a> y creá una cuenta de <strong>Meta Business</strong> con tu empresa.
              </li>
              <li>
                Verificá tu negocio (DNI/CUIT, dirección). Esto puede tardar 1-3 días.
              </li>
              <li>
                Andá a <a href="https://developers.facebook.com" target="_blank" rel="noreferrer" style={{ color: '#1d4ed8', textDecoration: 'underline' }}>developers.facebook.com <ExternalLink className="w-3 h-3" style={{ display: 'inline' }} /></a> → Mis Apps → Crear App → "Business" → agregar producto <strong>WhatsApp</strong>.
              </li>
              <li>
                Agregá tu número de teléfono comercial (no podés usar uno que ya esté en WhatsApp normal). Meta te enviará código por SMS o llamada.
              </li>
              <li>
                Copiá el <strong>Phone Number ID</strong>, <strong>Business Account ID</strong> y generá un <strong>Access Token permanente</strong> (System User → Tokens).
              </li>
              <li>
                En la sección "Webhooks", configurá:
                <ul style={{ margin: '4px 0 4px 16px' }}>
                  <li>URL de callback: <code style={{ background: '#fff', padding: '1px 6px', borderRadius: 4 }}>{data.webhook_url}</code></li>
                  <li>Verify Token: el que pegues abajo (inventalo, ej. <code>mi_secret_2026</code>).</li>
                  <li>Suscribite a los eventos: <code>messages</code>, <code>messaging_postbacks</code>.</li>
                </ul>
              </li>
              <li>
                Pegá los 4 valores acá abajo y guardá. Tu bot empieza a responder en segundos.
              </li>
            </ol>
            <p style={{ margin: '12px 0 0', fontSize: 12, color: '#475569' }}>
              💡 Si todo esto te suena complicado, escribinos por soporte y te lo configuramos nosotros.
            </p>
          </div>
        )}

        <div className="wa-form-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
              Phone Number ID
            </label>
            <Input
              value={data.whatsapp_phone_number_id || ''}
              onChange={(e) => handleChange('whatsapp_phone_number_id', e.target.value)}
              placeholder="Ej: 123456789012345"
              data-testid="input-wa-phone-number-id"
            />
          </div>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
              Business Account ID
            </label>
            <Input
              value={data.whatsapp_business_account_id || ''}
              onChange={(e) => handleChange('whatsapp_business_account_id', e.target.value)}
              placeholder="Ej: 987654321012345"
              data-testid="input-wa-business-account-id"
            />
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
              Access Token (permanente)
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <Input
                type={showToken ? 'text' : 'password'}
                value={data.whatsapp_access_token || ''}
                onChange={(e) => handleChange('whatsapp_access_token', e.target.value)}
                placeholder="EAAxxxxxx..."
                data-testid="input-wa-access-token"
                style={{ flex: 1 }}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setShowToken(!showToken)}
                title={showToken ? 'Ocultar' : 'Mostrar'}
              >
                {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </Button>
            </div>
            <p style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
              Si ya está guardado, vas a ver los últimos 10 caracteres. Pegá uno nuevo para reemplazarlo.
            </p>
          </div>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
              Webhook Verify Token
            </label>
            <Input
              value={data.webhook_verify_token || ''}
              onChange={(e) => handleChange('webhook_verify_token', e.target.value)}
              placeholder="Inventalo, ej: mi_secret_2026"
              data-testid="input-wa-verify-token"
            />
          </div>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
              Webhook URL (pegá esto en Meta)
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <Input
                value={data.webhook_url || ''}
                readOnly
                style={{ flex: 1, background: '#f9fafb', color: '#475569', fontFamily: 'monospace', fontSize: 12 }}
                data-testid="input-wa-webhook-url"
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => copyToClipboard(data.webhook_url, 'Webhook URL')}
                title="Copiar"
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap' }}>
          <Button
            variant="outline"
            onClick={testConnection}
            disabled={testing || saving}
            data-testid="btn-test-wa-connection"
          >
            <Zap className="w-4 h-4 mr-2" />
            {testing ? 'Probando...' : 'Probar conexión'}
          </Button>
          <Button
            onClick={save}
            disabled={saving || testing}
            data-testid="btn-save-wa-config"
            style={{ background: '#16a34a', color: '#fff' }}
          >
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Guardando...' : 'Guardar configuración'}
          </Button>
        </div>

        {testResult && (
          <div
            data-testid="wa-test-result"
            style={{
              marginTop: 16,
              padding: '14px 18px',
              borderRadius: 10,
              border: `1px solid ${testResult.ok ? '#a7f3d0' : '#fecaca'}`,
              background: testResult.ok ? '#f0fdf4' : '#fef2f2',
              color: testResult.ok ? '#065f46' : '#7f1d1d',
              fontSize: 13,
              lineHeight: 1.6,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              {testResult.ok ? (
                <CheckCircle2 className="w-5 h-5 flex-shrink-0" style={{ color: '#059669', marginTop: 2 }} />
              ) : (
                <AlertCircle className="w-5 h-5 flex-shrink-0" style={{ color: '#dc2626', marginTop: 2 }} />
              )}
              <div style={{ flex: 1 }}>
                <strong style={{ display: 'block', marginBottom: 4 }}>
                  {testResult.ok ? 'Conexión exitosa' : 'No se pudo conectar'}
                </strong>
                <div>{testResult.message}</div>
                {testResult.details && Object.values(testResult.details).some(v => v) && (
                  <div style={{
                    marginTop: 10, padding: '10px 12px', background: '#fff',
                    borderRadius: 6, fontSize: 12, color: '#374151',
                    border: '1px solid #e5e7eb',
                  }}>
                    <div><strong>Diagnóstico Meta:</strong></div>
                    <ul style={{ margin: '6px 0 0 16px', padding: 0 }}>
                      {testResult.details.display_phone_number && (
                        <li>Número: <code>{testResult.details.display_phone_number}</code></li>
                      )}
                      {testResult.details.verified_name && (
                        <li>Nombre verificado: <strong>{testResult.details.verified_name}</strong></li>
                      )}
                      {testResult.details.code_verification_status && (
                        <li>Verificación SMS/voz: <strong>{testResult.details.code_verification_status}</strong></li>
                      )}
                      {testResult.details.quality_rating && (
                        <li>Quality rating: <strong style={{
                          color: testResult.details.quality_rating === 'GREEN' ? '#059669'
                                : testResult.details.quality_rating === 'YELLOW' ? '#b45309' : '#dc2626'
                        }}>{testResult.details.quality_rating}</strong></li>
                      )}
                      {testResult.details.messaging_limit_tier && (
                        <li>Tier de mensajes: <code>{testResult.details.messaging_limit_tier}</code></li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
