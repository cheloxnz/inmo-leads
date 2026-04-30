import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function PrivacyPolicy() {
  return (
    <div className="privacy-page" data-testid="privacy-page">
      <div className="privacy-container">
        <Card>
          <CardHeader>
            <CardTitle>Política de Privacidad — InmoBot</CardTitle>
          </CardHeader>
          <CardContent className="privacy-content">
            <p className="last-updated">Última actualización: Abril 2026</p>

            <section>
              <p>
                InmoBot es una plataforma SaaS que provee bots de WhatsApp con IA para
                negocios. Esta política describe cómo tratamos los datos personales de
                nuestros clientes (los <strong>tenants</strong>) y de los usuarios finales
                que interactúan con sus bots.
              </p>
              <p>
                Cumplimos con la Ley 25.326 de Protección de Datos Personales (Argentina)
                y, en lo aplicable, con el Reglamento General de Protección de Datos (UE).
              </p>
            </section>

            <section>
              <h2>1. Responsable del tratamiento</h2>
              <p>
                <strong>InmoBot</strong> (en adelante, "nosotros") opera la plataforma SaaS.
                Para consultas sobre datos personales:
                {' '}<a href="mailto:soporte@inmobot.com">soporte@inmobot.com</a>.
              </p>
            </section>

            <section>
              <h2>2. Información que recopilamos</h2>
              <p><strong>Datos del cliente (tenant)</strong>:</p>
              <ul>
                <li>Email, nombre del negocio y datos de facturación.</li>
                <li>Configuración del bot (mensajes, horarios, productos).</li>
                <li>Logs de uso, número de mensajes, métricas internas.</li>
              </ul>
              <p><strong>Datos de usuarios finales</strong> (los que escriben al bot):</p>
              <ul>
                <li>Número de teléfono de WhatsApp.</li>
                <li>Mensajes enviados al bot.</li>
                <li>Datos que el usuario provea voluntariamente (nombre, preferencias).</li>
              </ul>
              <p>
                <em>Nota</em>: el cliente (tenant) actúa como responsable del tratamiento
                de los datos de sus usuarios finales. InmoBot actúa como encargado del
                tratamiento (data processor).
              </p>
            </section>

            <section>
              <h2>3. Finalidad del tratamiento</h2>
              <ul>
                <li>Proveer la plataforma y sus funcionalidades (procesar mensajes, generar resúmenes IA, agendar citas).</li>
                <li>Facturar el servicio y gestionar la suscripción.</li>
                <li>Mejorar la calidad del producto (métricas agregadas y anonimizadas).</li>
                <li>Enviar comunicaciones operativas (bienvenida, fin de trial, resúmenes).</li>
              </ul>
              <p>No vendemos ni cedemos datos personales a terceros con fines publicitarios.</p>
            </section>

            <section>
              <h2>4. Compartir información</h2>
              <p>Los datos pueden compartirse con:</p>
              <ul>
                <li><strong>OpenAI</strong>: para procesar mensajes con GPT-4 (no se usan para entrenar modelos).</li>
                <li><strong>Meta (WhatsApp Business API)</strong>: para enviar y recibir mensajes.</li>
                <li><strong>Stripe</strong>: para procesar pagos. No almacenamos datos de tarjetas.</li>
                <li><strong>MongoDB Atlas</strong>: para almacenamiento (servidores en EE.UU. con encriptación en reposo).</li>
                <li><strong>Sentry</strong>: para monitoreo de errores (datos minimizados, sin PII).</li>
              </ul>
            </section>

            <section>
              <h2>5. Transferencia internacional</h2>
              <p>
                Algunos proveedores (OpenAI, Stripe, MongoDB Atlas, Sentry) están en EE.UU.
                Esta transferencia se ampara en cláusulas contractuales tipo y en el
                consentimiento que otorgás al aceptar nuestros Términos.
              </p>
            </section>

            <section>
              <h2>6. Seguridad</h2>
              <ul>
                <li>HTTPS/TLS en todas las conexiones.</li>
                <li>Encriptación en reposo en la base de datos.</li>
                <li>Hashing seguro de contraseñas (bcrypt).</li>
                <li>Aislamiento estricto entre tenants (no podés ver datos de otros clientes).</li>
                <li>Backups automáticos diarios.</li>
                <li>Monitoreo continuo de errores y tentativas de abuso (rate limiting).</li>
              </ul>
            </section>

            <section>
              <h2>7. Retención</h2>
              <p>
                Conservamos los datos mientras tengas una cuenta activa. Si cancelás,
                los datos se mantienen hasta 90 días por motivos contables/legales y luego
                se eliminan o anonimizan, salvo obligación legal de retención mayor.
              </p>
              <p>
                Logs de actividad: 90 días. Backups: 30 días. Datos de facturación:
                mínimo 5 años (obligación fiscal de AFIP).
              </p>
            </section>

            <section>
              <h2>8. Tus derechos</h2>
              <p>Podés ejercer en cualquier momento los derechos de:</p>
              <ul>
                <li><strong>Acceso</strong>: saber qué datos tenemos tuyos.</li>
                <li><strong>Rectificación</strong>: corregir datos inexactos.</li>
                <li><strong>Eliminación / olvido</strong>: solicitarnos eliminar tus datos
                  (ver <a href="/data-deletion">/data-deletion</a>).</li>
                <li><strong>Portabilidad</strong>: exportar tus datos en formato JSON.</li>
                <li><strong>Oposición</strong>: oponerte a tratamientos específicos.</li>
              </ul>
              <p>
                Escribinos a <a href="mailto:soporte@inmobot.com">soporte@inmobot.com</a>{' '}
                indicando "Solicitud de derechos ARCO" en el asunto. Respondemos en
                hasta 10 días hábiles. En Argentina podés también presentarte ante la
                <em> Agencia de Acceso a la Información Pública</em> (AAIP).
              </p>
            </section>

            <section>
              <h2>9. Cookies y tecnologías similares</h2>
              <p>
                Usamos cookies estrictamente necesarias para el funcionamiento (sesión,
                token de autenticación) y, opcionalmente, cookies analíticas anonimizadas.
                No usamos cookies de publicidad de terceros.
              </p>
            </section>

            <section>
              <h2>10. Menores</h2>
              <p>
                La plataforma no está dirigida a menores de 18 años. Si detectamos
                cuenta con datos de menores, la eliminamos.
              </p>
            </section>

            <section>
              <h2>11. Cambios a esta política</h2>
              <p>
                Podemos actualizar esta política. Si los cambios son significativos te
                avisaremos por email con al menos 15 días de antelación.
              </p>
            </section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
