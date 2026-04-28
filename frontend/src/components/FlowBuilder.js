import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  GripVertical, Plus, Trash2, ChevronDown, ChevronUp,
  MessageSquare, ListChecks, Type, Save, RotateCcw, Pencil,
  Sparkles, ArrowDown
} from 'lucide-react';
import AIFlowAssistant from './AIFlowAssistant';

export default function FlowBuilder() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedStep, setExpandedStep] = useState(null);

  useEffect(() => { fetchConfig(); }, []);

  const fetchConfig = async () => {
    try {
      const res = await axios.get(`${API}/flow/config`);
      setConfig(res.data);
    } catch (err) {
      toast.error('Error cargando flujo');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/flow/config`, {
        welcome_message: config.welcome_message,
        welcome_buttons: config.welcome_buttons,
        flow_steps: config.flow_steps,
        scoring: config.scoring,
        appointment_message: config.appointment_message,
        completion_message: config.completion_message,
        faq: config.faq,
        labels: config.labels
      });
      toast.success('Flujo guardado');
      fetchConfig();
    } catch (err) {
      toast.error('Error guardando flujo');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Esto va a restaurar el flujo al template original. Continuar?')) return;
    try {
      await axios.post(`${API}/flow/reset`);
      toast.success('Flujo reseteado al template base');
      fetchConfig();
    } catch (err) {
      toast.error('Error reseteando flujo');
    }
  };

  const updateStep = (index, field, value) => {
    const steps = [...config.flow_steps];
    steps[index] = { ...steps[index], [field]: value };
    setConfig({ ...config, flow_steps: steps });
  };

  const addStep = () => {
    const newStep = {
      id: `step_${Date.now()}`,
      question: 'Nueva pregunta',
      type: 'text',
      field: `custom_fields.campo_${config.flow_steps.length + 1}`,
    };
    setConfig({ ...config, flow_steps: [...config.flow_steps, newStep] });
    setExpandedStep(config.flow_steps.length);
  };

  const removeStep = (index) => {
    if (!window.confirm('Eliminar este paso?')) return;
    const steps = config.flow_steps.filter((_, i) => i !== index);
    setConfig({ ...config, flow_steps: steps });
    setExpandedStep(null);
  };

  const moveStep = (index, direction) => {
    const steps = [...config.flow_steps];
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= steps.length) return;
    [steps[index], steps[newIndex]] = [steps[newIndex], steps[index]];
    setConfig({ ...config, flow_steps: steps });
    setExpandedStep(newIndex);
  };

  const updateButton = (stepIndex, btnIndex, field, value) => {
    const steps = [...config.flow_steps];
    const buttons = [...(steps[stepIndex].buttons || [])];
    buttons[btnIndex] = { ...buttons[btnIndex], [field]: value };
    steps[stepIndex] = { ...steps[stepIndex], buttons };
    setConfig({ ...config, flow_steps: steps });
  };

  const addButton = (stepIndex) => {
    const steps = [...config.flow_steps];
    const buttons = [...(steps[stepIndex].buttons || [])];
    if (buttons.length >= 3) { toast.error('Maximo 3 botones por paso'); return; }
    buttons.push({ id: `btn_${Date.now()}`, title: 'Nuevo boton' });
    steps[stepIndex] = { ...steps[stepIndex], buttons };
    setConfig({ ...config, flow_steps: steps });
  };

  const removeButton = (stepIndex, btnIndex) => {
    const steps = [...config.flow_steps];
    const buttons = steps[stepIndex].buttons.filter((_, i) => i !== btnIndex);
    steps[stepIndex] = { ...steps[stepIndex], buttons };
    setConfig({ ...config, flow_steps: steps });
  };

  const updateScoring = (index, field, value) => {
    const scoring = { ...config.scoring };
    const criteria = [...(scoring.criteria || [])];
    criteria[index] = { ...criteria[index], [field]: value };
    scoring.criteria = criteria;
    setConfig({ ...config, scoring });
  };

  const addScoringRule = () => {
    const scoring = { ...config.scoring };
    const criteria = [...(scoring.criteria || [])];
    criteria.push({ field: 'custom_fields.', points: 1, condition: 'not_empty' });
    scoring.criteria = criteria;
    setConfig({ ...config, scoring });
  };

  const removeScoringRule = (index) => {
    const scoring = { ...config.scoring };
    scoring.criteria = scoring.criteria.filter((_, i) => i !== index);
    setConfig({ ...config, scoring });
  };

  if (loading) return <div className="fb-loading">Cargando editor de flujo...</div>;
  if (!config) return <div className="fb-error">Error cargando configuracion</div>;

  return (
    <div className="fb-container" data-testid="flow-builder">
      {/* Header */}
      <div className="fb-header">
        <div>
          <h2>Editor de Flujo</h2>
          <p>Template base: <strong>{config.template_name}</strong> {config.is_customized && <span className="fb-customized-badge">Personalizado</span>}</p>
        </div>
        <div className="fb-header-actions">
          <Button variant="outline" size="sm" onClick={handleReset} data-testid="btn-reset-flow">
            <RotateCcw className="w-3 h-3 mr-1" /> Restaurar template
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving} data-testid="btn-save-flow">
            <Save className="w-3 h-3 mr-1" /> {saving ? 'Guardando...' : 'Guardar'}
          </Button>
        </div>
      </div>

      {/* AI Flow Assistant */}
      <AIFlowAssistant onApplied={fetchConfig} />

      {/* Welcome Message */}
      <Card className="fb-section">
        <CardHeader><CardTitle className="text-sm">Mensaje de bienvenida</CardTitle></CardHeader>
        <CardContent>
          <textarea
            className="fb-textarea"
            value={config.welcome_message}
            onChange={e => setConfig({ ...config, welcome_message: e.target.value })}
            rows={2}
            data-testid="input-welcome-msg"
          />
          <div className="fb-welcome-btns">
            <span className="fb-label">Botones iniciales:</span>
            {(config.welcome_buttons || []).map((btn, i) => (
              <input
                key={i}
                className="fb-inline-input"
                value={btn.title}
                onChange={e => {
                  const btns = [...config.welcome_buttons];
                  btns[i] = { ...btns[i], title: e.target.value };
                  setConfig({ ...config, welcome_buttons: btns });
                }}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Flow Steps */}
      <div className="fb-steps-header">
        <h3><ListChecks className="w-4 h-4" /> Pasos del flujo ({config.flow_steps.length})</h3>
        <Button size="sm" variant="outline" onClick={addStep} data-testid="btn-add-step">
          <Plus className="w-3 h-3 mr-1" /> Agregar paso
        </Button>
      </div>

      <div className="fb-steps">
        {config.flow_steps.map((step, index) => (
          <div key={step.id || index}>
            <Card className={`fb-step-card ${expandedStep === index ? 'expanded' : ''}`}>
              <div className="fb-step-row" onClick={() => setExpandedStep(expandedStep === index ? null : index)}>
                <div className="fb-step-left">
                  <div className="fb-step-num">{index + 1}</div>
                  <div className="fb-step-info">
                    <span className="fb-step-question">{step.question}</span>
                    <span className="fb-step-meta">
                      {step.type === 'buttons' ? <ListChecks className="w-3 h-3" /> : <Type className="w-3 h-3" />}
                      {step.type === 'buttons' ? `${(step.buttons || []).length} opciones` : 'Texto libre'}
                      {step.use_ai && <><Sparkles className="w-3 h-3" /> IA</>}
                    </span>
                  </div>
                </div>
                <div className="fb-step-actions-mini">
                  <span className="fb-field-tag">{step.field}</span>
                  {expandedStep === index ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
              </div>

              {expandedStep === index && (
                <div className="fb-step-detail">
                  <div className="fb-field-row">
                    <label>Pregunta</label>
                    <input value={step.question} onChange={e => updateStep(index, 'question', e.target.value)} data-testid={`step-${index}-question`} />
                  </div>
                  <div className="fb-field-grid">
                    <div className="fb-field-row">
                      <label>Tipo</label>
                      <select value={step.type} onChange={e => updateStep(index, 'type', e.target.value)}>
                        <option value="text">Texto libre</option>
                        <option value="buttons">Botones</option>
                      </select>
                    </div>
                    <div className="fb-field-row">
                      <label>Campo (donde se guarda)</label>
                      <input value={step.field} onChange={e => updateStep(index, 'field', e.target.value)} />
                    </div>
                  </div>

                  <div className="fb-field-grid">
                    <div className="fb-field-row">
                      <label className="fb-checkbox-label">
                        <input type="checkbox" checked={!!step.use_ai} onChange={e => updateStep(index, 'use_ai', e.target.checked)} />
                        Usar IA para interpretar respuesta
                      </label>
                    </div>
                  </div>

                  {step.use_ai && (
                    <div className="fb-field-row">
                      <label>Prompt para IA</label>
                      <input value={step.ai_prompt || ''} onChange={e => updateStep(index, 'ai_prompt', e.target.value)} placeholder="Ej: Extrae la zona o barrio del mensaje" />
                    </div>
                  )}

                  {step.type === 'buttons' && (
                    <div className="fb-buttons-editor">
                      <label>Botones (max 3)</label>
                      {(step.buttons || []).map((btn, bi) => (
                        <div key={bi} className="fb-button-row">
                          <input value={btn.title} onChange={e => updateButton(index, bi, 'title', e.target.value)} placeholder="Texto del boton" />
                          <input value={btn.id} onChange={e => updateButton(index, bi, 'id', e.target.value)} placeholder="ID" className="fb-btn-id-input" />
                          <button className="fb-btn-remove" onClick={() => removeButton(index, bi)}><Trash2 className="w-3 h-3" /></button>
                        </div>
                      ))}
                      {(step.buttons || []).length < 3 && (
                        <Button size="sm" variant="outline" onClick={() => addButton(index)}>
                          <Plus className="w-3 h-3 mr-1" /> Boton
                        </Button>
                      )}
                    </div>
                  )}

                  <div className="fb-step-footer">
                    <div className="fb-move-btns">
                      <button onClick={() => moveStep(index, -1)} disabled={index === 0} className="fb-move-btn" title="Subir">
                        <ChevronUp className="w-4 h-4" />
                      </button>
                      <button onClick={() => moveStep(index, 1)} disabled={index === config.flow_steps.length - 1} className="fb-move-btn" title="Bajar">
                        <ChevronDown className="w-4 h-4" />
                      </button>
                    </div>
                    <Button size="sm" variant="destructive" onClick={() => removeStep(index)}>
                      <Trash2 className="w-3 h-3 mr-1" /> Eliminar paso
                    </Button>
                  </div>
                </div>
              )}
            </Card>
            {index < config.flow_steps.length - 1 && (
              <div className="fb-step-arrow"><ArrowDown className="w-4 h-4" /></div>
            )}
          </div>
        ))}
      </div>

      {/* Scoring */}
      <Card className="fb-section">
        <CardHeader><CardTitle className="text-sm">Reglas de puntuacion (Scoring)</CardTitle></CardHeader>
        <CardContent>
          <div className="fb-scoring-thresholds">
            <div className="fb-field-row">
              <label>Hot (lead caliente) desde</label>
              <input type="number" value={config.scoring?.hot_threshold || 7} onChange={e => setConfig({ ...config, scoring: { ...config.scoring, hot_threshold: parseInt(e.target.value) || 0 } })} />
            </div>
            <div className="fb-field-row">
              <label>Warm (lead tibio) desde</label>
              <input type="number" value={config.scoring?.warm_threshold || 4} onChange={e => setConfig({ ...config, scoring: { ...config.scoring, warm_threshold: parseInt(e.target.value) || 0 } })} />
            </div>
          </div>
          <div className="fb-scoring-rules">
            {(config.scoring?.criteria || []).map((rule, i) => (
              <div key={i} className="fb-scoring-rule">
                <input value={rule.field} onChange={e => updateScoring(i, 'field', e.target.value)} placeholder="Campo" className="fb-score-field" />
                <select value={rule.condition} onChange={e => updateScoring(i, 'condition', e.target.value)}>
                  <option value="not_empty">Tiene valor</option>
                  <option value="equals">Es igual a</option>
                  <option value="not_equals">No es igual a</option>
                </select>
                {(rule.condition === 'equals' || rule.condition === 'not_equals') && (
                  <input value={rule.value || ''} onChange={e => updateScoring(i, 'value', e.target.value)} placeholder="Valor" className="fb-score-value" />
                )}
                <input type="number" value={rule.points} onChange={e => updateScoring(i, 'points', parseInt(e.target.value) || 0)} className="fb-score-points" />
                <span className="fb-score-pts-label">pts</span>
                <button className="fb-btn-remove" onClick={() => removeScoringRule(i)}><Trash2 className="w-3 h-3" /></button>
              </div>
            ))}
            <Button size="sm" variant="outline" onClick={addScoringRule}>
              <Plus className="w-3 h-3 mr-1" /> Regla
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Messages */}
      <Card className="fb-section">
        <CardHeader><CardTitle className="text-sm">Mensajes</CardTitle></CardHeader>
        <CardContent>
          <div className="fb-field-row">
            <label>Mensaje al ofrecer cita</label>
            <input value={config.appointment_message} onChange={e => setConfig({ ...config, appointment_message: e.target.value })} />
          </div>
          <div className="fb-field-row">
            <label>Mensaje de confirmacion (usa: {'{name}'}, {'{appointment_date}'}, {'{appointment_type}'})</label>
            <textarea className="fb-textarea" value={config.completion_message} onChange={e => setConfig({ ...config, completion_message: e.target.value })} rows={2} />
          </div>
        </CardContent>
      </Card>

      {/* Labels */}
      <Card className="fb-section">
        <CardHeader><CardTitle className="text-sm">Labels del dashboard</CardTitle></CardHeader>
        <CardContent>
          <div className="fb-field-grid">
            {Object.entries(config.labels || {}).map(([key, val]) => (
              <div key={key} className="fb-field-row">
                <label>{key}</label>
                <input value={val} onChange={e => {
                  const labels = { ...config.labels, [key]: e.target.value };
                  setConfig({ ...config, labels });
                }} />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
