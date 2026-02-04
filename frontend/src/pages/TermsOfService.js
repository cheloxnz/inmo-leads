import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function TermsOfService() {
  return (
    <div className="privacy-page">
      <div className="privacy-container">
        <Card>
          <CardHeader>
            <CardTitle>Términos y Condiciones del Servicio</CardTitle>
          </CardHeader>
          <CardContent className="privacy-content">
            <p className="last-updated">Última actualización: Febrero 2024</p>
            
            <section>
              <h2>1. Aceptación de los Términos</h2>
              <p>
                Al utilizar nuestro servicio de WhatsApp Bot para inmobiliarias ("InmoBot"), 
                aceptas estos términos y condiciones en su totalidad. Si no estás de acuerdo 
                con estos términos, no utilices el servicio.
              </p>
            </section>

            <section>
              <h2>2. Descripción del Servicio</h2>
              <p>
                InmoBot es un asistente virtual automatizado que ayuda a los usuarios a:
              </p>
              <ul>
                <li>Buscar propiedades inmobiliarias según sus preferencias</li>
                <li>Conectar con asesores inmobiliarios</li>
                <li>Agendar citas y visitas a propiedades</li>
                <li>Recibir información sobre el mercado inmobiliario</li>
              </ul>
            </section>

            <section>
              <h2>3. Uso del Servicio</h2>
              <p>Al usar nuestro servicio, te comprometes a:</p>
              <ul>
                <li>Proporcionar información veraz y actualizada</li>
                <li>No utilizar el servicio para fines ilegales</li>
                <li>No enviar contenido ofensivo, spam o malicioso</li>
                <li>Respetar a los asesores y personal de la inmobiliaria</li>
              </ul>
            </section>

            <section>
              <h2>4. Disponibilidad del Servicio</h2>
              <p>
                El servicio está disponible las 24 horas del día, los 7 días de la semana. 
                Sin embargo, no garantizamos disponibilidad ininterrumpida y podemos 
                realizar mantenimientos sin previo aviso.
              </p>
            </section>

            <section>
              <h2>5. Limitación de Responsabilidad</h2>
              <p>
                El bot proporciona información general sobre propiedades. No nos hacemos 
                responsables por:
              </p>
              <ul>
                <li>Decisiones tomadas basadas en la información del bot</li>
                <li>Inexactitudes en la información de propiedades</li>
                <li>Problemas técnicos o interrupciones del servicio</li>
                <li>Transacciones realizadas con terceros</li>
              </ul>
            </section>

            <section>
              <h2>6. Propiedad Intelectual</h2>
              <p>
                Todo el contenido, diseño y tecnología del servicio son propiedad de 
                la empresa y están protegidos por leyes de propiedad intelectual.
              </p>
            </section>

            <section>
              <h2>7. Privacidad</h2>
              <p>
                El uso de tus datos personales está regido por nuestra 
                <a href="/privacy"> Política de Privacidad</a>.
              </p>
            </section>

            <section>
              <h2>8. Modificaciones</h2>
              <p>
                Nos reservamos el derecho de modificar estos términos en cualquier momento. 
                Los cambios entrarán en vigor inmediatamente después de su publicación.
              </p>
            </section>

            <section>
              <h2>9. Contacto</h2>
              <p>
                Para consultas sobre estos términos, contáctanos a través de WhatsApp 
                o los canales de comunicación disponibles.
              </p>
            </section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
