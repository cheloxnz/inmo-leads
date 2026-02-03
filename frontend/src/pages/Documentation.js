import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';

export default function Documentation() {
  const [activeTab, setActiveTab] = useState('arquitectura');
  
  return (
    <div className="page-container docs-page" data-testid="docs-page">
      <header className="page-header">
        <h1>Documentación Técnica</h1>
        <p className="subtitle">Guía completa de implementación y arquitectura</p>
      </header>
      
      <Tabs value={activeTab} onValueChange={setActiveTab} className="docs-tabs">
        <TabsList>
          <TabsTrigger value="arquitectura">Arquitectura</TabsTrigger>
          <TabsTrigger value="n8n">n8n Blueprint</TabsTrigger>
          <TabsTrigger value="sheets">Google Sheets</TabsTrigger>
          <TabsTrigger value="implementacion">Implementación</TabsTrigger>
        </TabsList>
        
        <TabsContent value="arquitectura">
          <Card>
            <CardHeader>
              <CardTitle>Arquitectura del Sistema</CardTitle>
            </CardHeader>
            <CardContent className="docs-content">
              <h3>Stack Tecnológico</h3>
              <ul>
                <li><strong>WhatsApp Business Platform (Cloud API)</strong>: Canal de comunicación principal</li>
                <li><strong>n8n (Cloud)</strong>: Orquestador de workflows y automatizaciones</li>
                <li><strong>OpenAI GPT-4o</strong>: Procesamiento de lenguaje natural</li>
                <li><strong>Google Sheets</strong>: CRM mínimo viable</li>
                <li><strong>Google Calendar</strong>: Sistema de agendamiento</li>
                <li><strong>MongoDB</strong>: Base de datos para tracking interno</li>
                <li><strong>FastAPI + React</strong>: Backend y frontend del dashboard</li>
              </ul>
              
              <h3>Flujo de Datos</h3>
              <ol>
                <li>Cliente envía mensaje por WhatsApp</li>
                <li>WhatsApp Cloud API recibe el mensaje y envía webhook</li>
                <li>Backend recibe webhook y procesa mensaje</li>
                <li>LLM (GPT-4o) analiza el mensaje si es texto libre</li>
                <li>Bot Flow Manager determina siguiente paso del flujo</li>
                <li>Se envía respuesta vía WhatsApp API</li>
                <li>Lead se actualiza en MongoDB y Google Sheets</li>
                <li>Si aplica handoff, se notifica a asesor</li>
              </ol>
              
              <h3>Componentes Principales</h3>
              <Accordion type="single" collapsible>
                <AccordionItem value="webhook">
                  <AccordionTrigger>Webhook Receiver</AccordionTrigger>
                  <AccordionContent>
                    <p>Recibe notificaciones de WhatsApp cuando llegan mensajes. Valida firma HMAC-SHA256 para seguridad.</p>
                    <pre><code>{`POST /api/webhook
Headers:
  x-hub-signature-256: sha256=...
  Content-Type: application/json`}</code></pre>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="flow">
                  <AccordionTrigger>Bot Flow Manager</AccordionTrigger>
                  <AccordionContent>
                    <p>Gestiona el estado del flujo conversacional. Cada lead tiene un flow_stage que determina qué pregunta hacer siguiente.</p>
                    <p>Etapas: welcome → intent → zone → budget → property_type → bedrooms → must_have → urgency → financing → scoring → appointment → confirmation</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="scoring">
                  <AccordionTrigger>Scoring Engine</AccordionTrigger>
                  <AccordionContent>
                    <p>Calcula puntuación del lead basado en sus respuestas:</p>
                    <ul>
                      <li>Presupuesto definido: +2</li>
                      <li>Zona definida: +2</li>
                      <li>Tipo de propiedad: +1</li>
                      <li>Urgencia alta: +3, media: +2, baja: +1</li>
                      <li>Financiamiento definido: +1</li>
                      <li>Intención compra: +1</li>
                      <li>Requisitos específicos: +1</li>
                    </ul>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="llm">
                  <AccordionTrigger>LLM Service</AccordionTrigger>
                  <AccordionContent>
                    <p>Integra con OpenAI GPT-4o para:</p>
                    <ul>
                      <li>Clasificar intención (comprar/alquilar/inversión)</li>
                      <li>Extraer zona/barrio del texto libre</li>
                      <li>Extraer presupuesto del texto libre</li>
                      <li>Validar respuestas del usuario</li>
                    </ul>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="n8n">
          <Card>
            <CardHeader>
              <CardTitle>Blueprint de Workflow n8n</CardTitle>
            </CardHeader>
            <CardContent className="docs-content">
              <h3>Configuración de n8n Cloud</h3>
              <ol>
                <li>Crear cuenta en n8n.io</li>
                <li>Crear nuevo workflow "WhatsApp Lead Qualifier"</li>
                <li>Instalar credenciales de WhatsApp, Google Sheets y Google Calendar</li>
              </ol>
              
              <h3>Nodos del Workflow</h3>
              <Accordion type="single" collapsible>
                <AccordionItem value="nodo1">
                  <AccordionTrigger>1. Webhook Trigger</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Webhook</p>
                    <p><strong>Método:</strong> POST</p>
                    <p><strong>Path:</strong> /webhook/whatsapp</p>
                    <p><strong>Función:</strong> Recibe mensajes entrantes de WhatsApp</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo2">
                  <AccordionTrigger>2. Extract Message Data</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Function</p>
                    <p><strong>Código:</strong></p>
                    <pre><code>{`const phone = items[0].json.entry[0].changes[0].value.messages[0].from;
const text = items[0].json.entry[0].changes[0].value.messages[0].text.body;
return [{ json: { phone, text } }];`}</code></pre>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo3">
                  <AccordionTrigger>3. Lookup Lead in Google Sheets</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Google Sheets</p>
                    <p><strong>Operación:</strong> Lookup</p>
                    <p><strong>Lookup Column:</strong> Teléfono</p>
                    <p><strong>Lookup Value:</strong> {'{'}{'{'} $json.phone {'}'}{'}'}  </p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo4">
                  <AccordionTrigger>4. IF: Lead Exists?</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> IF</p>
                    <p><strong>Condición:</strong> Si el lead existe en Sheets</p>
                    <p><strong>True:</strong> Actualizar lead existente</p>
                    <p><strong>False:</strong> Crear nuevo lead</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo5">
                  <AccordionTrigger>5. Switch: Flow Stage</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Switch</p>
                    <p><strong>Función:</strong> Rutear según etapa del flujo (welcome, intent, zone, etc.)</p>
                    <p>Cada rama procesa una etapa diferente del flujo conversacional</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo6">
                  <AccordionTrigger>6. OpenAI GPT-4o (opcional)</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> OpenAI</p>
                    <p><strong>Uso:</strong> Clasificar intenciones y extraer entidades de texto libre</p>
                    <p>Solo se usa cuando el usuario responde en lenguaje natural en vez de opciones numéricas</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo7">
                  <AccordionTrigger>7. Calculate Score</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Function</p>
                    <p>Implementa lógica de scoring basada en las respuestas del lead</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo8">
                  <AccordionTrigger>8. Update Google Sheets</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Google Sheets</p>
                    <p><strong>Operación:</strong> Update o Append</p>
                    <p>Guarda toda la información del lead</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo9">
                  <AccordionTrigger>9. Send WhatsApp Message</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> HTTP Request</p>
                    <p><strong>URL:</strong> https://graph.facebook.com/v18.0/{'{'}PHONE_NUMBER_ID{'}'}/messages</p>
                    <p><strong>Method:</strong> POST</p>
                    <p>Envía la respuesta del bot al usuario</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo10">
                  <AccordionTrigger>10. IF: Should Handoff?</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Condiciones:</strong></p>
                    <ul>
                      <li>Score ≥ 7</li>
                      <li>Cita agendada</li>
                      <li>Flujo completado</li>
                    </ul>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo11">
                  <AccordionTrigger>11. Create Google Calendar Event</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Google Calendar</p>
                    <p><strong>Operación:</strong> Create Event</p>
                    <p>Crea evento cuando el lead acepta agendar cita</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="nodo12">
                  <AccordionTrigger>12. Notify Agent (WhatsApp/Email)</AccordionTrigger>
                  <AccordionContent>
                    <p><strong>Tipo:</strong> Send Message</p>
                    <p>Envía notificación al asesor cuando hay handoff</p>
                    <p><strong>Formato:</strong></p>
                    <pre><code>{`🔥 LEAD CALIENTE

Nombre: {name}
Tel: {phone}
Intención: {intent}
Zona: {zone}
Presupuesto: {budget}
Score: {score}/12

Cita agendada: {datetime}`}</code></pre>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
              
              <h3>Manejo de Errores</h3>
              <ul>
                <li>Agregar nodo "Error Trigger" para capturar fallos</li>
                <li>Implementar reintentos automáticos con delay</li>
                <li>Logging de errores en Google Sheets separada</li>
              </ul>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="sheets">
          <Card>
            <CardHeader>
              <CardTitle>Estructura de Google Sheets (CRM)</CardTitle>
            </CardHeader>
            <CardContent className="docs-content">
              <h3>Hoja: Leads</h3>
              <table className="docs-table">
                <thead>
                  <tr>
                    <th>Columna</th>
                    <th>Tipo</th>
                    <th>Descripción</th>
                    <th>Ejemplo</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Teléfono</td>
                    <td>Texto</td>
                    <td>Número WhatsApp (clave única)</td>
                    <td>5491134567890</td>
                  </tr>
                  <tr>
                    <td>Nombre</td>
                    <td>Texto</td>
                    <td>Nombre del lead</td>
                    <td>Juan Pérez</td>
                  </tr>
                  <tr>
                    <td>Estado Flujo</td>
                    <td>Texto</td>
                    <td>Etapa actual del flujo</td>
                    <td>budget</td>
                  </tr>
                  <tr>
                    <td>Intención</td>
                    <td>Lista</td>
                    <td>comprar / alquilar / inversion</td>
                    <td>comprar</td>
                  </tr>
                  <tr>
                    <td>Zona</td>
                    <td>Texto</td>
                    <td>Barrio o zona de interés</td>
                    <td>Palermo</td>
                  </tr>
                  <tr>
                    <td>Presupuesto</td>
                    <td>Texto</td>
                    <td>Presupuesto en USD</td>
                    <td>USD 150.000</td>
                  </tr>
                  <tr>
                    <td>Tipo Propiedad</td>
                    <td>Lista</td>
                    <td>departamento / casa / ph / etc</td>
                    <td>departamento</td>
                  </tr>
                  <tr>
                    <td>Dormitorios</td>
                    <td>Número</td>
                    <td>Cantidad de ambientes</td>
                    <td>2</td>
                  </tr>
                  <tr>
                    <td>Requisitos</td>
                    <td>Texto</td>
                    <td>Lista separada por comas</td>
                    <td>balcón, cochera</td>
                  </tr>
                  <tr>
                    <td>Urgencia</td>
                    <td>Lista</td>
                    <td>urgente / proximo_mes / meses / solo_mirando</td>
                    <td>urgente</td>
                  </tr>
                  <tr>
                    <td>Financiamiento</td>
                    <td>Lista</td>
                    <td>efectivo / credito / uva / procrear / mixto</td>
                    <td>efectivo</td>
                  </tr>
                  <tr>
                    <td>Score</td>
                    <td>Número</td>
                    <td>Puntuación 0-12</td>
                    <td>9</td>
                  </tr>
                  <tr>
                    <td>Clasificación</td>
                    <td>Lista</td>
                    <td>hot / warm / cold</td>
                    <td>hot</td>
                  </tr>
                  <tr>
                    <td>Fecha Cita</td>
                    <td>Fecha/Hora</td>
                    <td>Fecha y hora de cita agendada</td>
                    <td>15/02/2026 15:00</td>
                  </tr>
                  <tr>
                    <td>Asesor Asignado</td>
                    <td>Texto</td>
                    <td>Nombre del asesor</td>
                    <td>María Gómez</td>
                  </tr>
                  <tr>
                    <td>Fuente</td>
                    <td>Texto</td>
                    <td>Origen del lead</td>
                    <td>whatsapp</td>
                  </tr>
                  <tr>
                    <td>Fecha Creación</td>
                    <td>Fecha/Hora</td>
                    <td>Cuándo se creó el lead</td>
                    <td>10/02/2026 10:30</td>
                  </tr>
                  <tr>
                    <td>Notas</td>
                    <td>Texto largo</td>
                    <td>Observaciones del asesor</td>
                    <td>Cliente muy interesado...</td>
                  </tr>
                </tbody>
              </table>
              
              <h3>Formato Condicional Recomendado</h3>
              <ul>
                <li><strong>Clasificación "hot":</strong> Fondo rojo claro</li>
                <li><strong>Clasificación "warm":</strong> Fondo amarillo claro</li>
                <li><strong>Clasificación "cold":</strong> Fondo azul claro</li>
                <li><strong>Score ≥ 7:</strong> Texto en negrita</li>
              </ul>
              
              <h3>Permisos</h3>
              <p>La cuenta de servicio de Google debe tener permisos de Editor en la hoja de cálculo</p>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="implementacion">
          <Card>
            <CardHeader>
              <CardTitle>Checklist de Implementación</CardTitle>
            </CardHeader>
            <CardContent className="docs-content">
              <h3>Fase 1: Configuración Inicial</h3>
              <ol className="checklist">
                <li>☐ Crear cuenta en Meta for Developers</li>
                <li>☐ Crear WhatsApp Business Account</li>
                <li>☐ Obtener Phone Number ID y Access Token</li>
                <li>☐ Crear App Secret para validación de webhooks</li>
                <li>☐ Verificar número de teléfono WhatsApp Business</li>
              </ol>
              
              <h3>Fase 2: Integraciones Google</h3>
              <ol className="checklist">
                <li>☐ Crear proyecto en Google Cloud Console</li>
                <li>☐ Habilitar Google Sheets API</li>
                <li>☐ Habilitar Google Calendar API</li>
                <li>☐ Crear Service Account</li>
                <li>☐ Descargar JSON de credenciales</li>
                <li>☐ Crear Google Sheet con estructura de Leads</li>
                <li>☐ Compartir Sheet con email del Service Account</li>
              </ol>
              
              <h3>Fase 3: Setup Backend</h3>
              <ol className="checklist">
                <li>☐ Configurar variables de entorno en .env</li>
                <li>☐ Instalar dependencias: pip install -r requirements.txt</li>
                <li>☐ Configurar EMERGENT_LLM_KEY</li>
                <li>☐ Iniciar servidor FastAPI</li>
                <li>☐ Exponer endpoint público (ngrok para testing)</li>
                <li>☐ Configurar webhook en Meta Dashboard</li>
              </ol>
              
              <h3>Fase 4: Testing</h3>
              <ol className="checklist">
                <li>☐ Enviar mensaje de prueba por WhatsApp</li>
                <li>☐ Verificar recepción de webhook</li>
                <li>☐ Probar flujo completo de conversación</li>
                <li>☐ Verificar scoring y clasificación</li>
                <li>☐ Probar agendamiento de cita</li>
                <li>☐ Verificar creación en Google Calendar</li>
                <li>☐ Verificar sync con Google Sheets</li>
                <li>☐ Probar handoff a humano</li>
              </ol>
              
              <h3>Fase 5: Producción</h3>
              <ol className="checklist">
                <li>☐ Crear templates de WhatsApp y enviar a aprobación</li>
                <li>☐ Configurar dominio propio para webhooks</li>
                <li>☐ Configurar SSL/HTTPS</li>
                <li>☐ Deploy en servidor de producción</li>
                <li>☐ Configurar monitoreo y logs</li>
                <li>☐ Configurar alertas de errores</li>
                <li>☐ Entrenar equipo de asesores</li>
                <li>☐ Lanzamiento soft con grupo pequeño</li>
                <li>☐ Monitorear primeras 72 horas</li>
                <li>☐ Ajustar parámetros según feedback</li>
              </ol>
              
              <h3>Métricas a Monitorear</h3>
              <ul>
                <li>Número de conversaciones iniciadas / día</li>
                <li>Tasa de finalización del flujo</li>
                <li>Distribución de leads (hot/warm/cold)</li>
                <li>Tasa de agendamiento</li>
                <li>Tiempo promedio de conversación</li>
                <li>Score promedio de leads</li>
                <li>Tasa de conversión (leads calientes / total)</li>
                <li>Errores de API / webhooks</li>
              </ul>
              
              <h3>Problemas Comunes y Soluciones</h3>
              <Accordion type="single" collapsible>
                <AccordionItem value="prob1">
                  <AccordionTrigger>Webhook no recibe mensajes</AccordionTrigger>
                  <AccordionContent>
                    <ul>
                      <li>Verificar que URL sea pública y accesible</li>
                      <li>Verificar certificado SSL válido</li>
                      <li>Revisar configuración en Meta Dashboard</li>
                      <li>Verificar que WEBHOOK_VERIFY_TOKEN coincida</li>
                    </ul>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="prob2">
                  <AccordionTrigger>Error 131047 - Ventana 24h expirada</AccordionTrigger>
                  <AccordionContent>
                    <p>Solo se pueden enviar mensajes libres dentro de las 24h desde el último mensaje del cliente. Fuera de esta ventana, usar templates aprobados.</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="prob3">
                  <AccordionTrigger>LLM no extrae información correctamente</AccordionTrigger>
                  <AccordionContent>
                    <p>Ajustar system messages en llm_service.py para mejorar prompts. Agregar ejemplos específicos del contexto argentino.</p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="prob4">
                  <AccordionTrigger>Google Sheets no se actualiza</AccordionTrigger>
                  <AccordionContent>
                    <ul>
                      <li>Verificar permisos del Service Account</li>
                      <li>Verificar que GOOGLE_SHEETS_CREDENTIALS_JSON esté configurado</li>
                      <li>Revisar logs de error en backend</li>
                    </ul>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}