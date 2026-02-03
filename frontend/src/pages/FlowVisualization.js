import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function FlowVisualization() {
  const flowStages = [
    { id: 1, name: 'Welcome', description: 'Saludo inicial y presentación del bot', score: 0 },
    { id: 2, name: 'Intent', description: 'Clasificación: Comprar/Alquilar/Inversión', score: '+1 (compra)' },
    { id: 3, name: 'Zone', description: 'Zona o barrio de interés', score: '+2' },
    { id: 4, name: 'Budget', description: 'Presupuesto en USD', score: '+2' },
    { id: 5, name: 'Property Type', description: 'Tipo: Depto/Casa/PH/etc', score: '+1' },
    { id: 6, name: 'Bedrooms', description: 'Cantidad de dormitorios', score: '0' },
    { id: 7, name: 'Must Have', description: 'Requisitos obligatorios', score: '+1' },
    { id: 8, name: 'Urgency', description: 'Nivel de urgencia', score: '+0 a +3' },
    { id: 9, name: 'Financing', description: 'Tipo de financiamiento', score: '+1' },
    { id: 10, name: 'Scoring', description: 'Cálculo automático del score', score: 'Total' },
    { id: 11, name: 'Appointment', description: 'Oferta de agendar cita', score: '-' },
    { id: 12, name: 'Confirmation', description: 'Confirmación y handoff', score: '-' }
  ];
  
  return (
    <div className="page-container" data-testid="flow-page">
      <header className="page-header">
        <h1>Flujo Conversacional del Bot</h1>
        <p className="subtitle">Visualización paso a paso del proceso de calificación</p>
      </header>
      
      <Card className="scoring-info-card">
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
            </ul>
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
      
      <Card className="tech-info-card">
        <CardHeader>
          <CardTitle>Tecnologías Utilizadas</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="tech-list">
            <div className="tech-item">
              <div className="tech-icon">📱</div>
              <div>
                <h4>WhatsApp Cloud API</h4>
                <p>Comunicación directa con clientes vía WhatsApp Business</p>
              </div>
            </div>
            
            <div className="tech-item">
              <div className="tech-icon">🧠</div>
              <div>
                <h4>OpenAI GPT-4o</h4>
                <p>Procesamiento de lenguaje natural para entender respuestas libres</p>
              </div>
            </div>
            
            <div className="tech-item">
              <div className="tech-icon">📊</div>
              <div>
                <h4>Scoring Engine</h4>
                <p>Algoritmo propietario de calificación automática</p>
              </div>
            </div>
            
            <div className="tech-item">
              <div className="tech-icon">📅</div>
              <div>
                <h4>Google Calendar</h4>
                <p>Agendamiento automático de visitas y llamadas</p>
              </div>
            </div>
            
            <div className="tech-item">
              <div className="tech-icon">📋</div>
              <div>
                <h4>Google Sheets</h4>
                <p>CRM mínimo viable para gestión de leads</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}