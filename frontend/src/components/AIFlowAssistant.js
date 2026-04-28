import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  Sparkles, CheckCircle2, XCircle, Loader2, RotateCcw,
  Plus, Pencil, Trash2, ArrowUpDown, MessageSquare,
} from 'lucide-react';

const OP_LABELS = {
  add_step: { icon: Plus, label: 'Agregar paso', color: 'green' },
  update_step: { icon: Pencil, label: 'Modificar paso', color: 'blue' },
  remove_step: { icon: Trash2, label: 'Eliminar paso', color: 'red' },
  reorder_step: { icon: ArrowUpDown, label: 'Reordenar paso', color: 'amber' },
  update_welcome: { icon: MessageSquare, label: 'Mensaje bienvenida', color: 'purple' },
  update_completion: { icon: MessageSquare, label: 'Mensaje cierre', color: 'purple' },
  update_appointment: { icon: MessageSquare, label: 'Mensaje cita', color: 'purple' },
};

const COLOR_CLASSES = {
  green: 'bg-green-50 border-green-200 text-green-800',
  blue: 'bg-blue-50 border-blue-200 text-blue-800',
  red: 'bg-red-50 border-red-200 text-red-800',
  amber: 'bg-amber-50 border-amber-200 text-amber-800',
  purple: 'bg-purple-50 border-purple-200 text-purple-800',
};

const summarizeParams = (op, params) => {
  if (!params) return '';
  switch (op) {
    case 'add_step':
      return `"${params.question || ''}" (${params.type || 'text'})`;
    case 'update_step': {
      const parts = [];
      if (params.question) parts.push(`pregunta="${params.question}"`);
      if (params.type) parts.push(`tipo=${params.type}`);
      return `${params.step_id}: ${parts.join(', ') || '(sin cambios)'}`;
    }
    case 'remove_step':
      return `id=${params.step_id}`;
    case 'reorder_step':
      return `${params.step_id} → posición ${params.new_index}`;
    case 'update_welcome':
    case 'update_completion':
    case 'update_appointment':
      return `"${(params.text || '').slice(0, 80)}${(params.text || '').length > 80 ? '…' : ''}"`;
    default:
      return JSON.stringify(params).slice(0, 80);
  }
};

const parseRetrySeconds = (msg) => {
  const m = /Reintentar en (\d+)s/.exec(msg || '');
  return m ? parseInt(m[1], 10) : null;
};

export default function AIFlowAssistant({ onApplied }) {
  const [instruction, setInstruction] = useState('');
  const [examples, setExamples] = useState([]);
  const [rateLimit, setRateLimit] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [retryIn, setRetryIn] = useState(0);
  const countdownRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/flow/ai-edit/info`)
      .then(r => {
        setExamples(r.data.examples || []);
        setRateLimit(r.data.rate_limit);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (retryIn <= 0) {
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
      return;
    }
    countdownRef.current = setInterval(() => {
      setRetryIn(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [retryIn]);

  const reset = () => {
    setPreview(null);
    setError('');
  };

  const requestPreview = async () => {
    if (!instruction.trim()) {
      toast.error('Escribi una instruccion primero');
      return;
    }
    if (retryIn > 0) {
      toast.error(`Esperá ${retryIn}s antes del siguiente intento`);
      return;
    }
    setLoadingPreview(true);
    setError('');
    setPreview(null);
    try {
      const r = await axios.post(`${API}/flow/ai-edit`, {
        instruction: instruction.trim(),
        confirm: false,
      });
      setPreview(r.data.preview);
      if (r.data.rate_limit) {
        setRateLimit(prev => ({ ...(prev || {}), ...r.data.rate_limit }));
      }
      const validCount = (r.data.preview?.operations || []).length;
      if (validCount === 0) {
        toast.warning('La IA no encontro operaciones validas');
      } else {
        toast.success(`${validCount} operacion(es) listas`);
      }
    } catch (err) {
      const status = err.response?.status;
      const msg = err.response?.data?.detail || 'Error generando preview';
      setError(msg);
      if (status === 429) {
        const sec = parseRetrySeconds(msg) || 60;
        setRetryIn(sec);
        toast.error(`Limite de IA alcanzado. Reintentar en ${sec}s`);
      } else {
        toast.error(msg);
      }
    } finally {
      setLoadingPreview(false);
    }
  };

  const applyChanges = async () => {
    if (!preview || !preview.operations?.length) return;
    setApplying(true);
    try {
      const r = await axios.post(`${API}/flow/ai-edit`, {
        instruction: instruction.trim(),
        confirm: true,
        confirmed_ops: preview.operations.map(o => ({ op: o.op, params: o.params })),
      });
      if (r.data.applied) {
        toast.success(`Aplicadas ${r.data.applied_count || 0} operacion(es)`);
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

  const previewBtnDisabled = loadingPreview || applying || !instruction.trim() || retryIn > 0;

  return (
    <Card data-testid="ai-flow-assistant" className="border-purple-200 mb-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-500" />
          Asistente IA del Flujo
          <Badge variant="outline" className="ml-auto text-xs">Beta</Badge>
        </CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Editá el árbol del bot conversando: agregar/quitar/mover pasos, cambiar mensajes. La IA propone, vos aplicás.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">Instrucción</label>
          <textarea
            data-testid="ai-flow-instruction"
            className="w-full min-h-[80px] rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
            placeholder='Ej: "Agrega un paso para preguntar el barrio donde busca y otro para el rango de precio"'
            value={instruction}
            maxLength={500}
            onChange={(e) => setInstruction(e.target.value)}
            disabled={loadingPreview || applying}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{instruction.length}/500</span>
            {rateLimit && (
              <span data-testid="ai-flow-rate-limit">
                {rateLimit.remaining ?? rateLimit.max} de {rateLimit.max} req/hora restantes
              </span>
            )}
          </div>
        </div>

        {retryIn > 0 && (
          <div
            data-testid="ai-flow-retry-countdown"
            className="p-3 bg-orange-50 border border-orange-200 rounded-md text-sm text-orange-800 flex items-center gap-2"
          >
            <Loader2 className="w-4 h-4 animate-spin" />
            Limite alcanzado. Disponible en <strong>{retryIn}s</strong>...
          </div>
        )}

        {examples.length > 0 && !preview && (
          <div>
            <p className="text-xs text-gray-500 mb-2">Ejemplos:</p>
            <div className="flex flex-wrap gap-2">
              {examples.map((ex, i) => (
                <button
                  key={i}
                  data-testid={`ai-flow-example-${i}`}
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
            data-testid="ai-flow-preview-btn"
            onClick={requestPreview}
            disabled={previewBtnDisabled}
          >
            {loadingPreview ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Generando…</>
            ) : (
              <><Sparkles className="w-4 h-4 mr-2" />Previsualizar operaciones</>
            )}
          </Button>
          {preview && (
            <Button
              data-testid="ai-flow-reset-btn"
              variant="outline"
              onClick={reset}
              disabled={applying}
            >
              <RotateCcw className="w-4 h-4 mr-2" />Reiniciar
            </Button>
          )}
        </div>

        {error && (
          <div data-testid="ai-flow-error" className="p-3 bg-red-50 border border-red-200 text-sm text-red-700 rounded-md">
            {error}
          </div>
        )}

        {preview && (
          <div data-testid="ai-flow-preview" className="space-y-3 mt-4 border-t pt-4">
            {preview.summary && (
              <div className="text-sm italic text-gray-600">
                <strong>Resumen:</strong> {preview.summary}
              </div>
            )}

            {(preview.current_step_count !== undefined && preview.preview_step_count !== undefined) && (
              <div className="text-xs text-gray-500">
                Pasos: <span className="font-mono">{preview.current_step_count}</span>
                {' → '}
                <span className="font-mono font-semibold text-purple-700">{preview.preview_step_count}</span>
              </div>
            )}

            {preview.operations?.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />
                  {preview.operations.length} operación(es) válida(s)
                </p>
                <div className="space-y-2">
                  {preview.operations.map((o, i) => {
                    const meta = OP_LABELS[o.op] || { icon: Pencil, label: o.op, color: 'blue' };
                    const Icon = meta.icon;
                    return (
                      <div
                        key={i}
                        data-testid={`ai-flow-op-${i}`}
                        className={`p-3 border rounded-md text-sm ${COLOR_CLASSES[meta.color]}`}
                      >
                        <div className="flex items-center gap-2 font-medium">
                          <Icon className="w-4 h-4" />
                          {meta.label}
                        </div>
                        <div className="text-xs mt-1 opacity-90 font-mono">
                          {summarizeParams(o.op, o.params)}
                        </div>
                        {o.explanation && (
                          <div className="text-xs mt-1 opacity-75 italic">{o.explanation}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {preview.invalid?.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-1">
                  <XCircle className="w-4 h-4" />
                  {preview.invalid.length} operación(es) rechazada(s)
                </p>
                <div className="space-y-1">
                  {preview.invalid.map((inv, i) => (
                    <div
                      key={i}
                      data-testid={`ai-flow-invalid-${i}`}
                      className="p-2 bg-red-50 border border-red-200 rounded-md text-xs text-red-700"
                    >
                      <strong>{inv.op || '?'}:</strong> {inv.reason}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {preview.operations?.length === 0 && preview.invalid?.length === 0 && (
              <div className="text-sm text-gray-500">
                La IA no propuso ninguna operación. Probá con una instrucción más específica.
              </div>
            )}

            {preview.operations?.length > 0 && (
              <Button
                data-testid="ai-flow-apply-btn"
                onClick={applyChanges}
                disabled={applying}
                className="bg-green-600 hover:bg-green-700"
              >
                {applying ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Aplicando…</>
                ) : (
                  <><CheckCircle2 className="w-4 h-4 mr-2" />Aplicar {preview.operations.length} operación(es)</>
                )}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
