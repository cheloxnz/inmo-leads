#!/usr/bin/env python3
"""
Script para generar el contrato de licencia de InmoBot en PDF
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, HRFlowable
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import os

# Colores
PRIMARY_COLOR = HexColor('#1a365d')
SECONDARY_COLOR = HexColor('#2d3748')
LIGHT_BG = HexColor('#f7fafc')

def create_styles():
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='ContractTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=PRIMARY_COLOR,
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))
    
    styles.add(ParagraphStyle(
        name='ContractSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=SECONDARY_COLOR,
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica'
    ))
    
    styles.add(ParagraphStyle(
        name='ClauseTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=PRIMARY_COLOR,
        spaceBefore=15,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    ))
    
    styles.add(ParagraphStyle(
        name='ContractBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor=SECONDARY_COLOR,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        leading=14
    ))
    
    styles.add(ParagraphStyle(
        name='ContractBullet',
        parent=styles['Normal'],
        fontSize=10,
        textColor=SECONDARY_COLOR,
        leftIndent=20,
        spaceAfter=4,
        leading=12
    ))
    
    styles.add(ParagraphStyle(
        name='FieldLine',
        parent=styles['Normal'],
        fontSize=10,
        textColor=SECONDARY_COLOR,
        spaceAfter=15,
        leading=20
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=PRIMARY_COLOR,
        spaceBefore=12,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    ))
    
    return styles

def create_table_style():
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), LIGHT_BG),
        ('TEXTCOLOR', (0, 1), (-1, -1), SECONDARY_COLOR),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
    ])

def build_contract_pdf():
    os.makedirs('/app/docs', exist_ok=True)
    
    doc = SimpleDocTemplate(
        '/app/docs/CONTRATO_LICENCIA.pdf',
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch
    )
    
    styles = create_styles()
    story = []
    
    # === ENCABEZADO ===
    story.append(Paragraph("CONTRATO DE LICENCIA DE SOFTWARE", styles['ContractTitle']))
    story.append(Paragraph("InmoBot - Bot de WhatsApp con Inteligencia Artificial", styles['ContractSubtitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY_COLOR, spaceAfter=15))
    
    # Número y fecha
    story.append(Paragraph("<b>Contrato N°:</b> _______________________  &nbsp;&nbsp;&nbsp;&nbsp; <b>Fecha:</b> _______________________", styles['ContractBody']))
    story.append(Spacer(1, 0.2*inch))
    
    # === PARTES ===
    story.append(Paragraph("PARTES", styles['ClauseTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_COLOR, spaceAfter=10))
    
    story.append(Paragraph("<b>EL LICENCIANTE (Vendedor):</b>", styles['ContractBody']))
    story.append(Paragraph("Nombre completo: _______________________________________________", styles['FieldLine']))
    story.append(Paragraph("DNI/CUIT: _______________________________________________", styles['FieldLine']))
    story.append(Paragraph("Domicilio: _______________________________________________", styles['FieldLine']))
    story.append(Paragraph("Email: _________________________ Teléfono: _________________________", styles['FieldLine']))
    
    story.append(Paragraph("<b>EL LICENCIATARIO (Comprador):</b>", styles['ContractBody']))
    story.append(Paragraph("Razón social / Nombre: _______________________________________________", styles['FieldLine']))
    story.append(Paragraph("DNI/CUIT: _______________________________________________", styles['FieldLine']))
    story.append(Paragraph("Domicilio: _______________________________________________", styles['FieldLine']))
    story.append(Paragraph("Email: _________________________ Teléfono: _________________________", styles['FieldLine']))
    story.append(Paragraph("Representante legal: _______________________________________________", styles['FieldLine']))
    
    # === CLÁUSULAS ===
    story.append(Paragraph("CLÁUSULAS", styles['ClauseTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_COLOR, spaceAfter=10))
    
    # Primera
    story.append(Paragraph("<b>PRIMERA: OBJETO DEL CONTRATO</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "El LICENCIANTE transfiere al LICENCIATARIO una <b>licencia exclusiva</b> de uso del software denominado \"InmoBot\", que incluye:",
        styles['ContractBody']
    ))
    items = [
        "a) Código fuente completo del sistema (frontend y backend)",
        "b) Base de datos configurada",
        "c) Documentación técnica y manuales de usuario",
        "d) Credenciales y accesos a integraciones configuradas",
        "e) Capacitación según el plan contratado"
    ]
    for item in items:
        story.append(Paragraph(item, styles['ContractBullet']))
    
    # Segunda
    story.append(Paragraph("<b>SEGUNDA: TIPO DE LICENCIA</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "La licencia otorgada es de tipo <b>EXCLUSIVA</b>, lo que implica:",
        styles['ContractBody']
    ))
    
    licencia_data = [
        ['Derecho', 'Descripción'],
        ['Propiedad', 'Transferencia completa del código fuente al LICENCIATARIO'],
        ['Exclusividad', 'El LICENCIANTE no venderá este software a terceros'],
        ['Uso', 'Sin restricciones de uso comercial o interno'],
        ['Modificación', 'Libertad total para modificar, adaptar y extender'],
        ['Sublicencia', 'Derecho a sublicenciar o revender el software'],
    ]
    t = Table(licencia_data, colWidths=[1.5*inch, 5*inch])
    t.setStyle(create_table_style())
    story.append(t)
    story.append(Spacer(1, 0.1*inch))
    
    # Tercera
    story.append(Paragraph("<b>TERCERA: PLAN CONTRATADO</b>", styles['SectionHeader']))
    story.append(Paragraph("<b>Plan:</b> [ ] Completo &nbsp;&nbsp; [ ] Premium", styles['ContractBody']))
    story.append(Paragraph("<b>Modalidad:</b> [ ] Con Soporte &nbsp;&nbsp; [ ] Sin Soporte", styles['ContractBody']))
    story.append(Spacer(1, 0.1*inch))
    
    precios_data = [
        ['Plan', 'Con Soporte', 'Sin Soporte'],
        ['Completo', 'USD $10,000', 'USD $7,500'],
        ['Premium', 'USD $18,000', 'USD $12,000'],
    ]
    t_precios = Table(precios_data, colWidths=[2*inch, 2*inch, 2*inch])
    t_precios.setStyle(create_table_style())
    story.append(t_precios)
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("<b>Precio acordado:</b> USD $_________________", styles['ContractBody']))
    story.append(Paragraph("Características adicionales: _______________________________________________", styles['FieldLine']))
    
    # Cuarta
    story.append(Paragraph("<b>CUARTA: FORMA DE PAGO</b>", styles['SectionHeader']))
    story.append(Paragraph("• Primer pago (50%): USD $_________ al momento de la firma", styles['ContractBullet']))
    story.append(Paragraph("• Segundo pago (50%): USD $_________ al momento de la entrega", styles['ContractBullet']))
    story.append(Paragraph("Métodos aceptados: Transferencia bancaria, Tarjeta de crédito, PayPal, Criptomonedas", styles['ContractBody']))
    
    # Quinta
    story.append(Paragraph("<b>QUINTA: PLAZO DE ENTREGA</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "Plan Completo: 5-7 días hábiles | Plan Premium: 10-15 días hábiles desde el primer pago.",
        styles['ContractBody']
    ))
    
    story.append(PageBreak())
    
    # Sexta
    story.append(Paragraph("<b>SEXTA: ENTREGABLES</b>", styles['SectionHeader']))
    entregables = [
        "[ ] Acceso al repositorio de código fuente (GitHub)",
        "[ ] Acceso a la base de datos (MongoDB Atlas)",
        "[ ] Acceso al servidor de producción",
        "[ ] Credenciales de todas las integraciones",
        "[ ] Documentación técnica completa",
        "[ ] Manual de usuario",
        "[ ] Capacitación por videollamada"
    ]
    for e in entregables:
        story.append(Paragraph(e, styles['ContractBullet']))
    
    # Séptima
    story.append(Paragraph("<b>SÉPTIMA: SOPORTE TÉCNICO</b>", styles['SectionHeader']))
    story.append(Paragraph("<b>Aplica solo si se contrató modalidad 'Con Soporte':</b>", styles['ContractBody']))
    soporte_data = [
        ['Plan', 'Duración', 'Extendido'],
        ['Completo', '30 días', '+$300 USD/mes'],
        ['Premium', '90 días', '+$200 USD/mes'],
    ]
    t = Table(soporte_data, colWidths=[2*inch, 2*inch, 2*inch])
    t.setStyle(create_table_style())
    story.append(t)
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>Incluye:</b> Corrección de bugs, asistencia técnica, ajustes de configuración.", styles['ContractBody']))
    story.append(Paragraph("<b>No incluye:</b> Nuevas funcionalidades, cambios mayores de diseño, integraciones adicionales.", styles['ContractBody']))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("<b>Modalidad 'Sin Soporte':</b> Entrega completa + 1 hora de handoff + documentación. Sin asistencia post-entrega.", styles['ContractBody']))
    
    # Octava
    story.append(Paragraph("<b>OCTAVA: ACTUALIZACIONES (Solo Plan Premium)</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "El LICENCIANTE proveerá actualizaciones gratuitas durante <b>6 meses</b> desde la entrega, incluyendo correcciones de seguridad y mejoras menores.",
        styles['ContractBody']
    ))
    
    # Novena
    story.append(Paragraph("<b>NOVENA: GARANTÍA</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "El LICENCIANTE garantiza el funcionamiento según especificaciones y código libre de malware. <b>Garantía de satisfacción: 7 días</b> desde la entrega para verificar funcionamiento, con devolución del 100% si no cumple lo acordado.",
        styles['ContractBody']
    ))
    
    # Décima
    story.append(Paragraph("<b>DÉCIMA: RESPONSABILIDADES DEL LICENCIATARIO</b>", styles['SectionHeader']))
    resp = [
        "a) Mantener confidencialidad de credenciales y accesos",
        "b) Asumir costos operativos post-entrega (hosting, APIs, dominio)",
        "c) No responsabilizar al LICENCIANTE por uso indebido o pérdidas de negocio"
    ]
    for r in resp:
        story.append(Paragraph(r, styles['ContractBullet']))
    
    # Décimo primera
    story.append(Paragraph("<b>DÉCIMO PRIMERA: LIMITACIÓN DE RESPONSABILIDAD</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "La responsabilidad total del LICENCIANTE no excederá el monto pagado. No será responsable por daños indirectos, pérdida de datos, o fallas en servicios de terceros.",
        styles['ContractBody']
    ))
    
    # Décimo segunda
    story.append(Paragraph("<b>DÉCIMO SEGUNDA: PROPIEDAD INTELECTUAL</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "Completado el pago total, el LICENCIATARIO adquiere todos los derechos sobre el código entregado. El LICENCIANTE renuncia a reclamos sobre el software vendido.",
        styles['ContractBody']
    ))
    
    story.append(PageBreak())
    
    # Décimo tercera
    story.append(Paragraph("<b>DÉCIMO TERCERA: CONFIDENCIALIDAD</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "Ambas partes mantendrán confidencialidad sobre términos económicos, información técnica sensible y datos de clientes. Esta obligación se extiende por <b>2 años</b> después de finalizado el contrato.",
        styles['ContractBody']
    ))
    
    # Décimo cuarta
    story.append(Paragraph("<b>DÉCIMO CUARTA: RESCISIÓN</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "El contrato podrá rescindirse por mutuo acuerdo, por incumplimiento con 15 días de notificación, o por el LICENCIATARIO dentro de los 7 días de garantía. En caso de rescisión por incumplimiento del LICENCIANTE antes de la entrega, se devolverá el 100% de los montos abonados.",
        styles['ContractBody']
    ))
    
    # Décimo quinta
    story.append(Paragraph("<b>DÉCIMO QUINTA: RESOLUCIÓN DE CONFLICTOS</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "Las partes intentarán resolver conflictos de manera amistosa. De no lograrse acuerdo en 30 días, se someterán a mediación. En última instancia, serán competentes los tribunales de: _______________________________",
        styles['ContractBody']
    ))
    
    # Décimo sexta
    story.append(Paragraph("<b>DÉCIMO SEXTA: NOTIFICACIONES</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "Las notificaciones se realizarán por escrito a las direcciones de email indicadas, considerándose válidas las enviadas por correo electrónico con confirmación de lectura.",
        styles['ContractBody']
    ))
    
    # Décimo séptima
    story.append(Paragraph("<b>DÉCIMO SÉPTIMA: INTEGRIDAD DEL CONTRATO</b>", styles['SectionHeader']))
    story.append(Paragraph(
        "Este contrato constituye el acuerdo completo entre las partes. Cualquier modificación deberá realizarse por escrito y firmada por ambas partes.",
        styles['ContractBody']
    ))
    
    story.append(Spacer(1, 0.3*inch))
    
    # === FIRMAS ===
    story.append(Paragraph("FIRMAS", styles['ClauseTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_COLOR, spaceAfter=15))
    
    story.append(Paragraph(
        "En conformidad con todas las cláusulas precedentes, las partes firman el presente contrato en dos ejemplares de un mismo tenor y a un solo efecto.",
        styles['ContractBody']
    ))
    
    story.append(Spacer(1, 0.4*inch))
    
    # Tabla de firmas
    firma_data = [
        ['EL LICENCIANTE', 'EL LICENCIATARIO'],
        ['', ''],
        ['Firma: _______________________', 'Firma: _______________________'],
        ['', ''],
        ['Aclaración: _______________________', 'Aclaración: _______________________'],
        ['', ''],
        ['DNI: _______________________', 'DNI/CUIT: _______________________'],
        ['', ''],
        ['Fecha: _______________________', 'Fecha: _______________________'],
    ]
    
    firma_table = Table(firma_data, colWidths=[3.25*inch, 3.25*inch])
    firma_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(firma_table)
    
    story.append(PageBreak())
    
    # === ANEXO A ===
    story.append(Paragraph("ANEXO A: ESPECIFICACIONES TÉCNICAS", styles['ClauseTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_COLOR, spaceAfter=10))
    
    story.append(Paragraph("<b>Funcionalidades incluidas en InmoBot:</b>", styles['ContractBody']))
    
    story.append(Paragraph("<b>Bot de WhatsApp:</b>", styles['SectionHeader']))
    bot_features = [
        "[ ] Respuestas automáticas 24/7 con IA (GPT-4)",
        "[ ] Calificación automática de leads (score 0-12)",
        "[ ] Manejo de intenciones: compra, alquiler, venta, inversión",
        "[ ] Agendamiento automático de citas",
        "[ ] Seguimiento de leads inactivos"
    ]
    for f in bot_features:
        story.append(Paragraph(f, styles['ContractBullet']))
    
    story.append(Paragraph("<b>Dashboard de Gestión:</b>", styles['SectionHeader']))
    dash_features = [
        "[ ] Panel de métricas y estadísticas",
        "[ ] Lista de leads con filtros avanzados",
        "[ ] Vista Kanban del pipeline",
        "[ ] Calendario de citas",
        "[ ] Generación de reportes PDF"
    ]
    for f in dash_features:
        story.append(Paragraph(f, styles['ContractBullet']))
    
    story.append(Paragraph("<b>Integraciones:</b>", styles['SectionHeader']))
    integ = ["[ ] WhatsApp Business API", "[ ] OpenAI GPT-4", "[ ] Stripe (pagos)", "[ ] Sistema de emails"]
    for i in integ:
        story.append(Paragraph(i, styles['ContractBullet']))
    
    story.append(Spacer(1, 0.2*inch))
    
    # === ANEXO B ===
    story.append(Paragraph("ANEXO B: COSTOS OPERATIVOS ESTIMADOS", styles['ClauseTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_COLOR, spaceAfter=10))
    
    story.append(Paragraph("El LICENCIATARIO reconoce los siguientes costos mensuales aproximados post-entrega:", styles['ContractBody']))
    
    costos_data = [
        ['Servicio', 'Costo mensual estimado'],
        ['Hosting (Railway/DigitalOcean)', '$20-50 USD'],
        ['WhatsApp Business API', '$0-50 USD'],
        ['OpenAI API', '$10-30 USD'],
        ['Dominio (anual)', '~$15 USD/año'],
        ['TOTAL ESTIMADO', '$30-130 USD/mes'],
    ]
    t = Table(costos_data, colWidths=[3.5*inch, 2.5*inch])
    costos_style = create_table_style()
    costos_style.add('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')
    t.setStyle(costos_style)
    story.append(t)
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("<i>Estos costos son estimaciones y pueden variar según uso y proveedores.</i>", styles['ContractBody']))
    
    story.append(Spacer(1, 0.5*inch))
    story.append(HRFlowable(width="50%", thickness=1, color=PRIMARY_COLOR, spaceAfter=10))
    story.append(Paragraph("<i>Contrato generado para InmoBot - Versión 1.0</i>", styles['ContractBody']))
    
    # Generar PDF
    doc.build(story)
    print("✅ Contrato PDF generado en: /app/docs/CONTRATO_LICENCIA.pdf")
    return True

if __name__ == '__main__':
    build_contract_pdf()
