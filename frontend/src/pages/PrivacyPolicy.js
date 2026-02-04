import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function PrivacyPolicy() {
  return (
    <div className="privacy-page">
      <div className="privacy-container">
        <Card>
          <CardHeader>
            <CardTitle>Política de Privacidad</CardTitle>
          </CardHeader>
          <CardContent className="privacy-content">
            <p className="last-updated">Última actualización: Febrero 2024</p>
            
            <section>
              <h2>1. Información que Recopilamos</h2>
              <p>
                Cuando utilizas nuestro servicio de WhatsApp Bot para inmobiliarias, recopilamos:
              </p>
              <ul>
                <li>Número de teléfono de WhatsApp</li>
                <li>Nombre proporcionado durante la conversación</li>
                <li>Preferencias de búsqueda de propiedades (zona, presupuesto, tipo de propiedad)</li>
                <li>Historial de conversaciones con el bot</li>
                <li>Información de citas agendadas</li>
              </ul>
            </section>

            <section>
              <h2>2. Uso de la Información</h2>
              <p>Utilizamos la información recopilada para:</p>
              <ul>
                <li>Proporcionar asistencia automatizada en la búsqueda de propiedades</li>
                <li>Conectarte con asesores inmobiliarios</li>
                <li>Agendar citas y visitas</li>
                <li>Enviar información relevante sobre propiedades</li>
                <li>Mejorar nuestros servicios</li>
              </ul>
            </section>

            <section>
              <h2>3. Compartir Información</h2>
              <p>
                Tu información puede ser compartida con:
              </p>
              <ul>
                <li>Asesores inmobiliarios de nuestra red para atender tu solicitud</li>
                <li>Proveedores de servicios tecnológicos (hosting, bases de datos)</li>
              </ul>
              <p>No vendemos tu información personal a terceros.</p>
            </section>

            <section>
              <h2>4. Seguridad</h2>
              <p>
                Implementamos medidas de seguridad para proteger tu información personal, 
                incluyendo encriptación de datos y acceso restringido.
              </p>
            </section>

            <section>
              <h2>5. Retención de Datos</h2>
              <p>
                Conservamos tu información mientras sea necesaria para proporcionarte 
                nuestros servicios o según lo requiera la ley.
              </p>
            </section>

            <section>
              <h2>6. Tus Derechos</h2>
              <p>Tienes derecho a:</p>
              <ul>
                <li>Acceder a tu información personal</li>
                <li>Solicitar la corrección de datos inexactos</li>
                <li>Solicitar la eliminación de tus datos</li>
                <li>Retirar tu consentimiento en cualquier momento</li>
              </ul>
            </section>

            <section>
              <h2>7. Contacto</h2>
              <p>
                Para consultas sobre esta política de privacidad o para ejercer tus derechos, 
                contáctanos a través de WhatsApp o email.
              </p>
            </section>

            <section>
              <h2>8. Cambios a esta Política</h2>
              <p>
                Podemos actualizar esta política periódicamente. Te notificaremos sobre 
                cambios significativos.
              </p>
            </section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
