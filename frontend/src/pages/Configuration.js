import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

export default function Configuration() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  useEffect(() => {
    fetchConfig();
  }, []);
  
  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      setConfig(response.data);
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
      await axios.put(`${API}/config`, config);
      toast.success('Configuración guardada exitosamente');
    } catch (error) {
      console.error('Error saving config:', error);
      toast.error('Error guardando configuración');
    } finally {
      setSaving(false);
    }
  };
  
  const handleChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
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
          </CardContent>
        </Card>
        
        <Card>
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
    </div>
  );
}