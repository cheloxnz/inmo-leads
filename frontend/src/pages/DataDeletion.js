import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function DataDeletion() {
  const [phone, setPhone] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="privacy-page">
      <div className="privacy-container">
        <Card>
          <CardHeader>
            <CardTitle>Eliminación de Datos de Usuario</CardTitle>
          </CardHeader>
          <CardContent className="privacy-content">
            <p className="last-updated">Última actualización: Febrero 2024</p>
            
            <section>
              <h2>Tu Derecho a Eliminar tus Datos</h2>
              <p>
                De acuerdo con las regulaciones de protección de datos, tienes derecho a 
                solicitar la eliminación de toda tu información personal de nuestros sistemas.
              </p>
            </section>

            <section>
              <h2>¿Qué datos eliminamos?</h2>
              <p>Al solicitar la eliminación, borraremos:</p>
              <ul>
                <li>Tu número de teléfono</li>
                <li>Tu nombre y datos de contacto</li>
                <li>Historial de conversaciones con el bot</li>
                <li>Preferencias de búsqueda de propiedades</li>
                <li>Información de citas agendadas</li>
                <li>Cualquier nota o registro asociado a tu perfil</li>
              </ul>
            </section>

            <section>
              <h2>Proceso de Eliminación</h2>
              <p>
                Una vez recibida tu solicitud, procesaremos la eliminación de tus datos 
                en un plazo máximo de <strong>30 días</strong>. Recibirás una confirmación 
                cuando el proceso se haya completado.
              </p>
            </section>

            <section>
              <h2>Solicitar Eliminación</h2>
              
              {!submitted ? (
                <form onSubmit={handleSubmit} className="deletion-form">
                  <p>Ingresa el número de teléfono asociado a tu cuenta:</p>
                  <div className="form-row">
                    <Input
                      type="tel"
                      placeholder="+54 9 11 1234-5678"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      required
                    />
                    <Button type="submit">Solicitar Eliminación</Button>
                  </div>
                  <p className="help-text">
                    Ingresa el número con el que interactuaste con nuestro bot de WhatsApp.
                  </p>
                </form>
              ) : (
                <div className="success-message">
                  <p>✅ <strong>Solicitud recibida</strong></p>
                  <p>
                    Hemos recibido tu solicitud de eliminación para el número: <strong>{phone}</strong>
                  </p>
                  <p>
                    Procesaremos tu solicitud en los próximos 30 días y te notificaremos 
                    cuando tus datos hayan sido eliminados.
                  </p>
                </div>
              )}
            </section>

            <section>
              <h2>Contacto Alternativo</h2>
              <p>
                También puedes solicitar la eliminación de tus datos enviando un mensaje 
                a nuestro WhatsApp con el texto "ELIMINAR MIS DATOS" o contactándonos 
                por email.
              </p>
            </section>

            <section>
              <h2>Información Importante</h2>
              <ul>
                <li>La eliminación es permanente e irreversible</li>
                <li>No podremos recuperar tus datos después de la eliminación</li>
                <li>Si vuelves a usar el servicio, se creará un nuevo registro</li>
              </ul>
            </section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
