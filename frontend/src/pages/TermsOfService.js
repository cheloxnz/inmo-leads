import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function TermsOfService() {
  return (
    <div className="privacy-page" data-testid="terms-page">
      <div className="privacy-container">
        <Card>
          <CardHeader>
            <CardTitle>Términos y Condiciones — InmoBot</CardTitle>
          </CardHeader>
          <CardContent className="privacy-content">
            <p className="last-updated">Última actualización: Abril 2026</p>

            <section>
              <p>
                Bienvenido a <strong>InmoBot</strong>, plataforma SaaS que provee bots de
                WhatsApp con IA para negocios. Al registrarte y usar el servicio, aceptás
                estos Términos. Si no estás de acuerdo, no uses la plataforma.
              </p>
            </section>

            <section>
              <h2>1. Definiciones</h2>
              <ul>
                <li><strong>Plataforma</strong>: el software, infraestructura y servicios provistos por InmoBot.</li>
                <li><strong>Cliente</strong> o <strong>Tenant</strong>: la persona física o jurídica que contrata InmoBot.</li>
                <li><strong>Usuarios finales</strong>: las personas que interactúan con el bot del Cliente vía WhatsApp.</li>
                <li><strong>Plan</strong>: la suscripción mensual contratada (Basic, Pro, Enterprise, Trial).</li>
              </ul>
            </section>

            <section>
              <h2>2. Cuenta y elegibilidad</h2>
              <ul>
                <li>Debés ser mayor de 18 años y tener capacidad legal para contratar.</li>
                <li>La información que proveés debe ser veraz.</li>
                <li>Sos responsable de mantener la confidencialidad de tu contraseña.</li>
                <li>Una sola cuenta por persona o empresa, salvo autorización expresa.</li>
              </ul>
            </section>

            <section>
              <h2>3. Trial gratuito</h2>
              <p>
                Ofrecemos 14 días de prueba gratuita sin tarjeta de crédito. Al finalizar,
                podés contratar un plan pago o tu cuenta queda en modo lectura. Los datos
                se conservan 30 días adicionales antes de eliminarse, salvo que pagues.
              </p>
            </section>

            <section>
              <h2>4. Planes y facturación</h2>
              <ul>
                <li>Los precios están publicados en <a href="/pricing">/pricing</a> en USD/ARS.</li>
                <li>La facturación es mensual y se renueva automáticamente.</li>
                <li>Procesamos pagos vía Stripe; aceptamos tarjetas de crédito y débito.</li>
                <li>Si un pago falla, te notificamos por email. Tras 7 días sin regularizar suspendemos el servicio.</li>
                <li>Podés cancelar en cualquier momento desde Configuración → Facturación.
                  La cancelación se efectiviza al final del ciclo facturado.</li>
                <li>No reembolsamos meses parciales, salvo error nuestro o disposición legal.</li>
              </ul>
            </section>

            <section>
              <h2>5. Uso aceptable</h2>
              <p>Te comprometés a NO usar InmoBot para:</p>
              <ul>
                <li>Enviar spam, mensajes no solicitados o contenido fraudulento.</li>
                <li>Vulnerar la propiedad intelectual de terceros.</li>
                <li>Suplantar identidad de personas o empresas.</li>
                <li>Distribuir malware, phishing o contenido ilegal.</li>
                <li>Realizar ingeniería inversa, scraping abusivo o intentar romper la seguridad.</li>
                <li>Violar los Términos de Servicio de WhatsApp Business o las políticas de Meta.</li>
              </ul>
              <p>El incumplimiento puede derivar en suspensión inmediata sin reembolso.</p>
            </section>

            <section>
              <h2>6. Propiedad intelectual</h2>
              <ul>
                <li>InmoBot conserva la titularidad de su software, marca, código y documentación.</li>
                <li>Los datos del Cliente son <strong>de su propiedad</strong>. Nosotros sólo los
                  procesamos para proveer el servicio.</li>
                <li>Otorgás a InmoBot una licencia no exclusiva para procesar tu contenido en la medida necesaria para operar la plataforma.</li>
              </ul>
            </section>

            <section>
              <h2>7. Servicios de IA</h2>
              <p>
                La plataforma usa modelos de IA (OpenAI GPT-4 entre otros) para generar
                respuestas, resúmenes y configuraciones. Estos modelos pueden producir
                resultados imprecisos. <strong>Vos sos responsable de revisar las respuestas
                automáticas antes de tomar decisiones críticas.</strong>
              </p>
            </section>

            <section>
              <h2>8. Disponibilidad y SLA</h2>
              <ul>
                <li>Buscamos un uptime objetivo de 99,5% mensual, sin garantía contractual estricta para los planes Basic/Pro.</li>
                <li>El plan Enterprise puede incluir SLA escrito con créditos de servicio.</li>
                <li>Mantenimientos programados se notifican con al menos 48 hs de antelación cuando sea posible.</li>
              </ul>
            </section>

            <section>
              <h2>9. Limitación de responsabilidad</h2>
              <p>
                En la máxima medida permitida por la ley aplicable, InmoBot NO será responsable por:
              </p>
              <ul>
                <li>Daños indirectos, lucro cesante, pérdida de oportunidades comerciales o de datos.</li>
                <li>Acciones u omisiones de terceros (Meta, OpenAI, Stripe, proveedores de internet).</li>
                <li>Uso indebido del servicio por parte del Cliente o sus usuarios finales.</li>
              </ul>
              <p>
                La responsabilidad total agregada de InmoBot, en cualquier caso, no excederá
                el equivalente a los últimos 3 meses pagados por el Cliente.
              </p>
            </section>

            <section>
              <h2>10. Modificaciones</h2>
              <p>
                Podemos modificar estos Términos. Los cambios significativos se notifican por
                email con 15 días de antelación. El uso continuado tras la modificación
                implica aceptación.
              </p>
            </section>

            <section>
              <h2>11. Terminación</h2>
              <p>
                Podés cancelar tu cuenta en cualquier momento. InmoBot puede suspender o
                terminar el servicio en caso de incumplimiento de estos Términos, falta de
                pago o uso indebido, con notificación previa razonable salvo casos urgentes.
              </p>
            </section>

            <section>
              <h2>12. Ley aplicable y jurisdicción</h2>
              <p>
                Estos Términos se rigen por las leyes de la <strong>República Argentina</strong>.
                Cualquier disputa se someterá a los Tribunales Ordinarios de la Ciudad
                Autónoma de Buenos Aires, salvo derecho del consumidor que disponga otro fuero.
              </p>
            </section>

            <section>
              <h2>13. Contacto</h2>
              <p>
                Por cualquier consulta, escribinos a{' '}
                <a href="mailto:soporte@inmobot.com">soporte@inmobot.com</a>.
              </p>
            </section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
