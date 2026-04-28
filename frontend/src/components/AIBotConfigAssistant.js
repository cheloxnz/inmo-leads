import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Sparkles, CheckCircle2, XCircle, Loader2, RotateCcw } from 'lucide-react';

const FIELD_LABELS = {
  business_hours_start: 'Hora inicio (Lun-Vie)',
  business_hours_end: 'Hora fin (Lun-Vie)',
  business_days: 'Dias laborales',
  saturday_hours_start: 'Hora inicio (Sabado)',
  saturday_hours_end: 'Hora fin (Sabado)',
  auto_handoff_score: 'Score handoff humano',
  warm_lead_reactivation_days: 'Dias reactivacion lead tibio',
  appointment_reminder_hours: 'Recordatorio cita (horas antes)',
  welcome_message: 'Mensaje de bienvenida',
};

const formatValue = (v) => {
  if (Array.isArray(v)) return v.join(', ');
  if (v === undefined || v === null) return '—';
  return String(v);
};

export default function AIBotConfigAssistant({ onApplied }) {
  const [instruction, setInstruction] = useState('');
  const [examples, setExamples] = useState([]);
  const [rateLimit, setRateLimit] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API}/bot-config/ai-edit/info`)
      .then(r => {
        setExamples(r.data.examples || []);
        setRateLimit(r.data.rate_limit);
      })
      .catch(() => { /* silencioso */ });
  }, []);

  const reset = () => {
    setPreview(null);
    setError('');
  };

  const requestPreview = async () => {
    if (!instruction.trim()) {
      toast.error('Escribi una instruccion primero');
      return;
    }
    setLoadingPreview(true);
    setError('');
    setPreview(null);
    try {
      const r = await axios.post(`${API}/bot-config/ai-edit`, {
        instruction: instruction.trim(),
        confirm: false,
      });
      setPreview(r.data.preview);
      if (r.data.rate_limit) {
        setRateLimit(prev => ({ ...(prev || {}), ...r.data.rate_limit }));
      }
      const validCount = (r.data.preview?.actions || []).length;
      if (validCount === 0) {
        toast.warning('La IA no encontro cambios validos para aplicar');
      } else {
        toast.success(`${validCount} cambio(s) listos para revisar`);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error generando preview';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoadingPreview(false);
    }
  };

  const applyChanges = async () => {
    if (!preview || !preview.actions?.length) return;
    setApplying(true);
    try {
      // Mandamos las acciones validadas del preview, NO la instruction de nuevo.
      // Asi evitamos que un edit del textarea entre preview y apply cambie lo aplicado.
      const r = await axios.post(`${API}/bot-config/ai-edit`, {
        instruction: instruction.trim(),
        confirm: true,
        confirmed_actions: preview.actions.map(a => ({
          field: a.field,
          value: a.value,
        })),
      });
      if (r.data.applied) {
        toast.success(`Aplicados ${r.data.applied_fields?.length || 0} cambio(s)`);
        setPreview(null);
        setInstruction('');
        if (onApplied) onApplied();
      } else {
        toast.error('No se pudieron aplicar los cambios');
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error aplicando cambios';
      toast.error(msg);
    } finally {
      setApplying(false);
    }
  };

  return (
    <Card data-testid="ai-bot-config-assistant" className="border-purple-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-500" />
          Asistente IA de Configuracion
          <Badge variant="outline" className="ml-auto text-xs">Beta</Badge>
        </CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Modificá la configuración del bot escribiendo en lenguaje natural.
          La IA propone los cambios y vos los confirmás antes de aplicar.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            Instrucción
          </label>
          <textarea
            data-testid="ai-bot-config-instruction"
            className="w-full min-h-[80px] rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
            placeholder='Ej: "Cambia el horario a 9 a 19hs de lunes a viernes y los sabados de 10 a 13hs"'
            value={instruction}
            maxLength={500}
            onChange={(e) => setInstruction(e.target.value)}
            disabled={loadingPreview || applying}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{instruction.length}/500</span>
            {rateLimit && (
              <span data-testid="ai-bot-config-rate-limit">
                {rateLimit.remaining ?? rateLimit.max} de {rateLimit.max} req/hora restantes
              </span>
            )}
          </div>
        </div>

        {examples.length > 0 && !preview && (
          <div>
            <p className="text-xs text-gray-500 mb-2">Ejemplos:</p>
            <div className="flex flex-wrap gap-2">
              {examples.map((ex, i) => (
                <button
                  key={i}
                  data-testid={`ai-bot-config-example-${i}`}
                  type="button"
                  className="text-xs px-3 py-1 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-full border border-purple-200 transition-colors"
                  onClick={() => setInstruction(ex)}
                  disabled={loadingPreview || applying}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <Button
            data-testid="ai-bot-config-preview-btn"
            onClick={requestPreview}
            disabled={loadingPreview || applying || !instruction.trim()}
          >
            {loadingPreview ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Generando…</>
            ) : (
              <><Sparkles className="w-4 h-4 mr-2" />Previsualizar cambios</>
            )}
          </Button>
          {preview && (
            <Button
              data-testid="ai-bot-config-reset-btn"
              variant="outline"
              onClick={reset}
              disabled={applying}
            >
              <RotateCcw className="w-4 h-4 mr-2" />Reiniciar
            </Button>
          )}
        </div>

        {error && (
          <div data-testid="ai-bot-config-error" className="p-3 bg-red-50 border border-red-200 text-sm text-red-700 rounded-md">
            {error}
          </div>
        )}

        {preview && (
          <div data-testid="ai-bot-config-preview" className="space-y-3 mt-4 border-t pt-4">
            {preview.summary && (
              <div className="text-sm italic text-gray-600">
                <strong>Resumen:</strong> {preview.summary}
              </div>
            )}

            {preview.actions?.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />
                  {preview.actions.length} cambio(s) válido(s)
                </p>
                <div className="space-y-2">
                  {preview.actions.map((a, i) => (
                    <div
                      key={i}
                      data-testid={`ai-bot-config-action-${i}`}
                      className="p-3 bg-green-50 border border-green-200 rounded-md text-sm"
                    >
                      <div className="font-medium">
                        {FIELD_LABELS[a.field] || a.field}
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        <span className="line-through text-gray-400">
                          {formatValue(a.previous)}
                        </span>
                        {' → '}
                        <span className="text-green-700 font-mono">
                          {formatValue(a.value)}
                        </span>
                      </div>
                      {a.explanation && (
                        <div className="text-xs text-gray-500 mt-1">{a.explanation}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {preview.invalid?.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-1">
                  <XCircle className="w-4 h-4" />
                  {preview.invalid.length} cambio(s) rechazado(s)
                </p>
                <div className="space-y-1">
                  {preview.invalid.map((inv, i) => (
                    <div
                      key={i}
                      data-testid={`ai-bot-config-invalid-${i}`}
                      className="p-2 bg-red-50 border border-red-200 rounded-md text-xs text-red-700"
                    >
                      <strong>{inv.field || '?'}:</strong> {inv.reason}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {preview.actions?.length === 0 && preview.invalid?.length === 0 && (
              <div className="text-sm text-gray-500">
                La IA no propuso ningún cambio. Probá con una instrucción más específica.
              </div>
            )}

            {preview.actions?.length > 0 && (
              <Button
                data-testid="ai-bot-config-apply-btn"
                onClick={applyChanges}
                disabled={applying}
                className="bg-green-600 hover:bg-green-700"
              >
                {applying ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Aplicando…</>
                ) : (
                  <><CheckCircle2 className="w-4 h-4 mr-2" />Aplicar {preview.actions.length} cambio(s)</>
                )}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
