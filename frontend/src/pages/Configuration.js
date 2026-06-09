import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import BillingSection from '../components/BillingSection';  // eslint-disable-line no-unused-vars
import ReferralProgramSection from '../components/ReferralProgramSection';  // eslint-disable-line no-unused-vars
import AIBotConfigAssistant from '../components/AIBotConfigAssistant';
import BrandingPanel from '../components/BrandingPanel';
import WhatsAppConfigSection from '../components/WhatsAppConfigSection';
import BusinessProfileSection from '../components/BusinessProfileSection';
import BotLearningPanel from '../components/BotLearningPanel';
import CoachingOpportunitiesPanel from '../components/CoachingOpportunitiesPanel';
import GoogleCalendarSection from '../components/GoogleCalendarSection';
import { useAuth } from '../context/AuthContext';

export default function Configuration() {
  const { isSuperAdmin } = useAuth();
  const [config, setConfig] = useState(null);
  const [welcomeButtons, setWelcomeButtons] = useState([
    { id: 'opt_1', title: '' },
    { id: 'opt_2', title: '' },
    { id: 'opt_3', title: '' },
  ]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  
  useEffect(() => {
    fetchConfig();
  }, []);
  
  const fetchConfig = async () => {
    try {
      const [cfgRes, flowRes] = await Promise.all([
        axios.get(`${API}/config`),
        axios.get(`${API}/flow/config`).catch(() => ({ data: { welcome_buttons: [] } })),
      ]);
      setConfig(cfgRes.data);
      const btns = flowRes.data.welcome_buttons || [];
      // Garantizamos siempre 3 slots de botones
      const padded = [0, 1, 2].map(i => btns[i] || { id: `opt_${i + 1}`, title: '' });
      setWelcomeButtons(padded);
    } catch (error) {
      console.error('Error fetching config:', error);
      toast.error('Error cargando configuración');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSave = async () => {
    setSaving(true);
    try {
      // Filtramos botones vacíos antes de guardar (mínimo 1 visible).
      // Conservamos media adjunta si existe.
      const cleanButtons = welcomeButtons
        .map((b, i) => ({
          id: b.id || `opt_${i + 1}`,
          title: (b.title || '').trim(),
          ...(b.media_url ? {
            media_url: b.media_url,
            media_type: b.media_type || 'image',
            media_filename: b.media_filename || '',
            media_caption: b.media_caption || '',
          } : {}),
        }))
        .filter(b => b.title.length > 0);

      await Promise.all([
        axios.put(`${API}/config`, config),
        axios.put(`${API}/flow/config`, {
          welcome_message: config?.welcome_message || '',
          welcome_buttons: cleanButtons,
        }),
      ]);
      toast.success('Configuración guardada exitosamente');
    } catch (error) {
      console.error('Error saving config:', error);
      toast.error('Error guardando configuración');
    } finally {
      setSaving(false);
    }
  };

  const handleButtonFileUpload = async (idx, file) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Archivo demasiado grande (máx 5 MB)');
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await axios.post(`${API}/uploads/media`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const next = [...welcomeButtons];
      next[idx] = {
        ...next[idx],
        media_url: res.data.url,
        media_type: res.data.media_type,
        media_filename: res.data.original_filename,
      };
      setWelcomeButtons(next);
      toast.success('Archivo subido. Acordate de "Guardar configuración" para aplicar.');
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Error subiendo archivo';
      toast.error(detail);
    }
  };

  const handleButtonFileRemove = (idx) => {
    const next = [...welcomeButtons];
    next[idx] = {
      ...next[idx],
      media_url: undefined,
      media_type: undefined,
      media_filename: undefined,
    };
    setWelcomeButtons(next);
  };
  
  const handleChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };
  
  const handleTestEmail = async () => {
    setTestingEmail(true);
    try {
      const response = await axios.post(`${API}/test-email`);
      toast.success('Email de prueba enviado! Revisa tu bandeja de entrada');
    } catch (error) {
      console.error('Error sending test email:', error);
      toast.error('Error enviando email de prueba');
    } finally {
      setTestingEmail(false);
    }
  };
  
  if (loading) {
    return <div className="loading-container">Cargando...</div>;
  }
  
  return (
    <div className="page-container" data-testid="config-page">
      <header className="page-header">
        <h1>Configuración</h1>
        <p className="subtitle">Parámetros del bot y horarios de atención</p>
      </header>

      <AIBotConfigAssistant onApplied={fetchConfig} />

      <div className="config-grid">
        <Card>
          <CardHeader>
            <CardTitle>Horarios de Atención</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="form-group">
              <label>Hora inicio (Lun-Vie)</label>
              <Input 
                type="number" 
                min="0" 
                max="23"
                value={config?.business_hours_start || 9}
                onChange={(e) => handleChange('business_hours_start', parseInt(e.target.value))}
                data-testid="input-business-hours-start"
              />
            </div>
            
            <div className="form-group">
              <label>Hora fin (Lun-Vie)</label>
              <Input 
                type="number" 
                min="0" 
                max="23"
                value={config?.business_hours_end || 20}
                onChange={(e) => handleChange('business_hours_end', parseInt(e.target.value))}
                data-testid="input-business-hours-end"
              />
            </div>
            
            <div className="form-group">
              <label>Hora inicio (Sábado)</label>
              <Input 
                type="number" 
                min="0" 
                max="23"
                value={config?.saturday_hours_start || 10}
                onChange={(e) => handleChange('saturday_hours_start', parseInt(e.target.value))}
                data-testid="input-saturday-hours-start"
              />
            </div>
            
            <div className="form-group">
              <label>Hora fin (Sábado)</label>
              <Input 
                type="number" 
                min="0" 
                max="23"
                value={config?.saturday_hours_end || 14}
                onChange={(e) => handleChange('saturday_hours_end', parseInt(e.target.value))}
                data-testid="input-saturday-hours-end"
              />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Scoring y Handoff</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="form-group">
              <label>Score mínimo para handoff automático</label>
              <Input 
                type="number" 
                min="1" 
                max="12"
                value={config?.auto_handoff_score || 7}
                onChange={(e) => handleChange('auto_handoff_score', parseInt(e.target.value))}
                data-testid="input-auto-handoff-score"
              />
              <p className="help-text">Leads con este score o mayor pasan automáticamente a asesor</p>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Mensaje de Bienvenida</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="form-group">
              <label>Texto de bienvenida</label>
              <textarea 
                className="textarea-input"
                rows="4"
                value={config?.welcome_message || ''}
                onChange={(e) => handleChange('welcome_message', e.target.value)}
                data-testid="input-welcome-message"
              />
            </div>

            <div className="form-group" style={{ marginTop: 16 }}>
              <label>Opciones que verá el cliente (botones)</label>
              <p className="help-text" style={{ marginBottom: 8 }}>
                Hasta 3 botones. Si dejás uno vacío, no se muestra. Máximo 20 caracteres por botón (recomendación: usá un emoji al inicio). Podés adjuntar una imagen o PDF a cada botón: cuando el cliente lo seleccione, el bot envía el archivo automáticamente (ideal para menú, catálogo, lista de precios, presupuesto, etc.).
              </p>
              {welcomeButtons.map((btn, idx) => (
                <div
                  key={idx}
                  style={{
                    border: '1px solid #e5e7eb',
                    borderRadius: 8,
                    padding: 10,
                    marginBottom: 8,
                    background: '#fafafa',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ minWidth: 80, fontSize: 13, color: '#6b7280' }}>Opción {idx + 1}</span>
                    <Input
                      placeholder={
                        idx === 0 ? 'ej: 💰 Presupuesto' :
                        idx === 1 ? 'ej: 🍕 Ver menú' :
                        'ej: 📅 Reservar mesa'
                      }
                      maxLength={20}
                      value={btn.title}
                      onChange={(e) => {
                        const next = [...welcomeButtons];
                        next[idx] = { ...next[idx], title: e.target.value };
                        setWelcomeButtons(next);
                      }}
                      data-testid={`input-welcome-button-${idx + 1}`}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ minWidth: 80, fontSize: 12, color: '#9ca3af' }}>📎 Archivo</span>
                    {btn.media_url ? (
                      <>
                        <span
                          style={{
                            fontSize: 12,
                            color: '#059669',
                            fontWeight: 500,
                            background: '#ecfdf5',
                            padding: '2px 8px',
                            borderRadius: 4,
                          }}
                          title={btn.media_url}
                        >
                          {btn.media_type === 'document' ? '📄' : '🖼️'} {btn.media_filename || 'archivo'}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleButtonFileRemove(idx)}
                          style={{
                            fontSize: 12,
                            color: '#dc2626',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                          }}
                          data-testid={`btn-remove-file-${idx + 1}`}
                        >
                          quitar
                        </button>
                      </>
                    ) : (
                      <>
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,application/pdf"
                          id={`btn-file-${idx}`}
                          style={{ display: 'none' }}
                          onChange={(e) => handleButtonFileUpload(idx, e.target.files?.[0])}
                          data-testid={`input-file-${idx + 1}`}
                        />
                        <label
                          htmlFor={`btn-file-${idx}`}
                          style={{
                            fontSize: 12,
                            color: '#2563eb',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                          }}
                        >
                          subir imagen o PDF
                        </label>
                        <span style={{ fontSize: 11, color: '#9ca3af' }}>(máx 5 MB)</span>
                      </>
                    )}
                  </div>

                  {btn.media_url && (
                    <div style={{ marginTop: 8 }}>
                      <Input
                        placeholder="Texto que acompaña al archivo (opcional)"
                        maxLength={1024}
                        value={btn.media_caption || ''}
                        onChange={(e) => {
                          const next = [...welcomeButtons];
                          next[idx] = { ...next[idx], media_caption: e.target.value };
                          setWelcomeButtons(next);
                        }}
                        data-testid={`input-caption-${idx + 1}`}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        
        <Card data-testid="whatsapp-section-legacy" style={{ display: 'none' }}>
          <CardHeader>
            <CardTitle>Integraciones WhatsApp</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="integration-status">
              <div className="status-item">
                <span>Phone Number ID:</span>
                <span className="value">{process.env.REACT_APP_WHATSAPP_PHONE_NUMBER_ID ? '✅ Configurado' : '❌ No configurado'}</span>
              </div>
              <div className="status-item">
                <span>Access Token:</span>
                <span className="value">{process.env.REACT_APP_WHATSAPP_ACCESS_TOKEN ? '✅ Configurado' : '❌ No configurado'}</span>
              </div>
              <p className="help-text">Configura las credenciales de WhatsApp en el archivo .env del backend</p>
            </div>
          </CardContent>
        </Card>

        {/* WhatsApp Business config (per-tenant editable) */}
        <WhatsAppConfigSection />

        {/* Business Profile - data del negocio que el bot usa para responder sin inventar */}
        <BusinessProfileSection />

        {/* Cerebro del Bot - respuestas aprendidas de asesores humanos */}
        <BotLearningPanel />

        {/* Oportunidades de coaching - clusters semánticos de preguntas sin cubrir */}
        <CoachingOpportunitiesPanel />

        {/* Google Calendar - integración OAuth per-tenant */}
        <GoogleCalendarSection />
        
        <Card>
          <CardHeader>
            <CardTitle>Notificaciones por Email</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="integration-status">
              <div className="status-item">
                <span>SMTP Gmail:</span>
                <span className="value">✅ Configurado</span>
              </div>
              <div className="status-item">
                <span>Email destino:</span>
                <span className="value">Configurado en .env</span>
              </div>
              <p className="help-text">Los emails se envían automáticamente cuando hay leads calientes (Score ≥ 7)</p>
              <Button 
                onClick={handleTestEmail} 
                disabled={testingEmail}
                variant="outline"
                className="mt-4"
                data-testid="btn-test-email"
              >
                {testingEmail ? '📧 Enviando...' : '📧 Enviar Email de Prueba'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
      
      <div className="actions-bar">
        <Button 
          onClick={handleSave} 
          disabled={saving}
          data-testid="btn-save-config"
        >
          {saving ? 'Guardando...' : 'Guardar Configuración'}
        </Button>
      </div>

      {!isSuperAdmin && (
        <div style={{ marginTop: 24 }}>
          <BrandingPanel />
        </div>
      )}
    </div>
  );
}