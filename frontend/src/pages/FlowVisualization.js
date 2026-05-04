import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

/**
 * Visualización genérica del flujo conversacional del bot.
 * Aplica a cualquier vertical (inmobiliaria, e-commerce, servicios, etc.):
 * el bot saluda → detecta intención → recolecta requisitos → califica →
 * agenda cita o handoff a humano. Las "etiquetas" concretas (zona, presupuesto,
 * etc.) se configuran por tenant en Configuración → Perfil del negocio.
 */
export default function FlowVisualization() {
  const flowStages = [
    {
      id: 1, name: 'Saludo',
      description: 'El bot saluda al cliente, se presenta como asistente del negocio y abre la conversación.',
      score: '0',
    },
    {
      id: 2, name: 'Intención',
      description: 'Detecta qué quiere el cliente (consulta, compra, soporte, alquiler, agendar, etc.) según el rubro configurado.',
      score: '+1',
    },
    {
      id: 3, name: 'Datos clave',
      description: 'Recolecta los datos que importan a tu negocio: zona, producto, servicio, presupuesto, ubicación, tipo de consulta.',
      score: '+2',
    },
    {
      id: 4, name: 'Presupuesto / valor',
      description: 'Si aplica, pregunta rango de presupuesto o monto que el cliente está dispuesto a pagar.',
      score: '+2',
    },
    {
      id: 5, name: 'Categoría / producto',
      description: 'Identifica qué producto o servicio específico le interesa (ítem del catálogo, modelo, plan, etc.).',
      score: '+1',
    },
    {
      id: 6, name: 'Detalles',
      description: 'Profundiza en requisitos: cantidad, tamaño, características obligatorias, disponibilidad esperada.',
      score: '+1',
    },
    {
      id: 7, name: 'Urgencia',
      description: 'Mide cuán pronto necesita el cliente la solución (hoy, esta semana, sin apuro).',
      score: '+0 a +3',
    },
    {
      id: 8, name: 'Forma de pago',
      description: 'Si aplica, consulta forma de pago, financiación, contado, transferencia, etc.',
      score: '+1',
    },
    {
      id: 9, name: 'Score automático',
      description: 'Suma los puntos según las respuestas y calcula la temperatura del lead (frío / tibio / caliente).',
      score: 'Total',
    },
    {
      id: 10, name: 'Agendar cita',
      description: 'Si el cliente está caliente, le ofrece agendar una visita / llamada / reunión. Chequea disponibilidad en Google Calendar si está conectado.',
      score: '-',
    },
    {
      id: 11, name: 'Confirmación',
      description: 'Confirma la cita y deriva al asesor humano. El asesor recibe la conversación completa con score y datos del cliente.',
      score: '-',
    },
  ];

  return (
    <div className="page-container" data-testid="flow-page">
      <header className="page-header">
        <h1>Flujo Conversacional del Bot</h1>
        <p className="subtitle">
          Visualización paso a paso del proceso de calificación. Cada negocio puede personalizar
          los textos exactos desde <strong>Configuración → Perfil del negocio</strong>.
        </p>
      </header>

      <Card className="scoring-info-card" data-testid="scoring-info">
        <CardHeader>
          <CardTitle>Sistema de Scoring</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="scoring-rules">
            <div className="rule-item">
              <span className="badge-hot score-badge">🔥 Caliente</span>
              <span>Score ≥ 7 puntos</span>
            </div>
            <div className="rule-item">
              <span className="badge-warm score-badge">🟡 Tibio</span>
              <span>Score 4-6 puntos</span>
            </div>
            <div className="rule-item">
              <span className="badge-cold score-badge">❄️ Frío</span>
              <span>Score ≤ 3 puntos</span>
            </div>
          </div>

          <div className="handoff-rules">
            <h4>Reglas de Handoff a Humano:</h4>
            <ul>
              <li>✅ Score ≥ 7 (Lead caliente)</li>
              <li>✅ Cita agendada confirmada</li>
              <li>✅ Solicitud explícita de hablar con asesor</li>
              <li>✅ Flujo completado exitosamente</li>
              <li>✅ Sentimiento negativo detectado (cliente frustrado)</li>
            </ul>
          </div>

          <div className="ai-tip" style={{
            marginTop: 16, padding: 12, background: '#faf5ff',
            borderLeft: '3px solid #8b5cf6', borderRadius: 6, fontSize: 13,
          }}>
            <strong>💡 Inteligencia activa:</strong> en cada paso el bot
            consulta <em>respuestas aprendidas</em> + <em>embeddings semánticos</em> +
            <em> perfil del negocio</em> antes de responder. Si tu equipo guarda
            una respuesta nueva, el bot la usa en consultas similares de
            otros clientes (ver <strong>Configuración → Cerebro del Bot</strong>).
          </div>
        </CardContent>
      </Card>

      <div className="flow-visualization">
        {flowStages.map((stage, index) => (
          <div key={stage.id} className="flow-stage" data-testid={`flow-stage-${stage.id}`}>
            <div className="stage-number">{stage.id}</div>
            <div className="stage-content">
              <h3>{stage.name}</h3>
              <p>{stage.description}</p>
              {stage.score !== '-' && stage.score !== '0' && (
                <div className="stage-score">Score: {stage.score}</div>
              )}
            </div>
            {index < flowStages.length - 1 && (
              <div className="stage-arrow">↓</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
