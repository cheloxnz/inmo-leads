#!/usr/bin/env python3
"""
Script para generar la propuesta comercial de InmoBot en PDF
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

# Colores de marca InmoBot
PRIMARY_COLOR = HexColor('#1a365d')  # Azul oscuro
SECONDARY_COLOR = HexColor('#2d3748')  # Gris oscuro
ACCENT_COLOR = HexColor('#38a169')  # Verde
LIGHT_BG = HexColor('#f7fafc')  # Gris claro

def create_styles():
    """Crear estilos personalizados para el PDF"""
    styles = getSampleStyleSheet()
    
    # Título principal
    styles.add(ParagraphStyle(
        name='MainTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=PRIMARY_COLOR,
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))
    
    # Subtítulo
    styles.add(ParagraphStyle(
        name='SubTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=SECONDARY_COLOR,
        spaceAfter=15,
        alignment=TA_CENTER,
        fontName='Helvetica'
    ))
    
    # Encabezados de sección
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=PRIMARY_COLOR,
        spaceBefore=25,
        spaceAfter=12,
        fontName='Helvetica-Bold'
    ))
    
    # Texto normal
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        textColor=SECONDARY_COLOR,
        spaceAfter=8,
        alignment=TA_JUSTIFY,
        leading=14
    ))
    
    # Lista con viñetas
    styles.add(ParagraphStyle(
        name='BulletPoint',
        parent=styles['Normal'],
        fontSize=11,
        textColor=SECONDARY_COLOR,
        leftIndent=20,
        spaceAfter=6,
        leading=14
    ))
    
    # Precio destacado
    styles.add(ParagraphStyle(
        name='PriceHighlight',
        parent=styles['Normal'],
        fontSize=24,
        textColor=ACCENT_COLOR,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=10
    ))
    
    # Nombre del plan
    styles.add(ParagraphStyle(
        name='PlanName',
        parent=styles['Heading3'],
        fontSize=16,
        textColor=PRIMARY_COLOR,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceBefore=15,
        spaceAfter=8
    ))
    
    return styles

def create_table_style():
    """Estilo para las tablas"""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), LIGHT_BG),
        ('TEXTCOLOR', (0, 1), (-1, -1), SECONDARY_COLOR),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT_BG, colors.white]),
    ])

def build_pdf():
    """Construir el documento PDF"""
    
    # Asegurar que existe el directorio
    os.makedirs('/app/docs', exist_ok=True)
    
    doc = SimpleDocTemplate(
        '/app/docs/PROPUESTA_COMERCIAL.pdf',
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = create_styles()
    story = []
    
    # === PORTADA ===
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("InmoBot", styles['MainTitle']))
    story.append(Paragraph("Bot de WhatsApp con Inteligencia Artificial<br/>para Inmobiliarias", styles['SubTitle']))
    story.append(Spacer(1, 0.5*inch))
    story.append(HRFlowable(width="50%", thickness=2, color=ACCENT_COLOR, spaceBefore=20, spaceAfter=20))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("PROPUESTA COMERCIAL", styles['SectionHeader']))
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("hola@inmobot-ia.com", styles['CustomBody']))
    story.append(PageBreak())
    
    # === EL PROBLEMA ===
    story.append(Paragraph("El Problema", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    story.append(Paragraph(
        "Las inmobiliarias pierden <b>hasta el 40% de sus leads</b> porque:",
        styles['CustomBody']
    ))
    
    problems = [
        "No pueden responder fuera de horario laboral",
        "Los asesores tardan horas (o días) en responder consultas",
        "No hay seguimiento sistemático de cada contacto",
        "Se pierden oportunidades por falta de calificación"
    ]
    for p in problems:
        story.append(Paragraph(f"• {p}", styles['BulletPoint']))
    
    story.append(Spacer(1, 0.3*inch))
    
    # === LA SOLUCIÓN ===
    story.append(Paragraph("La Solución: InmoBot", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    story.append(Paragraph(
        "<b>InmoBot</b> es un asistente virtual inteligente que:",
        styles['CustomBody']
    ))
    
    solutions = [
        "<b>Responde en segundos</b>, 24/7, los 365 días del año",
        "<b>Califica automáticamente</b> cada lead (comprador, inquilino o vendedor)",
        "<b>Agenda visitas</b> directamente en el calendario",
        "<b>Notifica en tiempo real</b> cuando hay un lead caliente",
        "<b>Gestiona todo</b> desde un dashboard profesional"
    ]
    for s in solutions:
        story.append(Paragraph(f"✓ {s}", styles['BulletPoint']))
    
    story.append(Spacer(1, 0.3*inch))
    
    # === FUNCIONALIDADES DEL BOT ===
    story.append(Paragraph("Funcionalidades del Bot", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    bot_data = [
        ['Característica', 'Descripción'],
        ['Respuestas con IA', 'Usa GPT para entender y responder consultas complejas'],
        ['Calificación automática', 'Score de 0-12 según intención, presupuesto y urgencia'],
        ['Multi-intención', 'Maneja compradores, inquilinos, vendedores e inversores'],
        ['Agendamiento', 'Propone fechas y confirma citas automáticamente'],
        ['Seguimiento', 'Recordatorios automáticos y reactivación de leads tibios'],
    ]
    
    bot_table = Table(bot_data, colWidths=[2*inch, 4.5*inch])
    bot_table.setStyle(create_table_style())
    story.append(bot_table)
    
    story.append(Spacer(1, 0.3*inch))
    
    # === DASHBOARD ===
    story.append(Paragraph("Dashboard de Gestión", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    dashboard_data = [
        ['Característica', 'Descripción'],
        ['Vista Kanban', 'Pipeline visual de leads por estado'],
        ['Calendario', 'Todas las citas en un solo lugar'],
        ['Métricas', 'Conversión, respuesta, leads por día'],
        ['Historial', 'Conversaciones completas de cada lead'],
        ['Broadcast', 'Envío de mensajes masivos segmentados'],
        ['Reportes PDF', 'Exportación de informes'],
    ]
    
    dashboard_table = Table(dashboard_data, colWidths=[2*inch, 4.5*inch])
    dashboard_table.setStyle(create_table_style())
    story.append(dashboard_table)
    
    story.append(PageBreak())
    
    # === PLANES ===
    story.append(Paragraph("Planes Disponibles", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    # Plan Completo
    story.append(Paragraph("Plan Completo", styles['PlanName']))
    story.append(Paragraph("USD $10,000", styles['PriceHighlight']))
    story.append(Paragraph(
        "<b>Ideal para:</b> Inmobiliarias que quieren empezar a operar de inmediato con exclusividad total.",
        styles['CustomBody']
    ))
    
    plan_completo = [
        "Código fuente completo (React + Python + MongoDB)",
        "Dominio profesional (inmobot-ia.com o similar)",
        "Instalación y configuración en servidor",
        "Conexión con tu WhatsApp Business",
        "Configuración de integraciones (IA, email)",
        "Capacitación de uso (1 hora por videollamada)",
        "<b>30 días de soporte técnico incluido</b>",
        "Documentación técnica completa"
    ]
    for item in plan_completo:
        story.append(Paragraph(f"✓ {item}", styles['BulletPoint']))
    
    story.append(Paragraph("<b>Entrega:</b> 5-7 días hábiles", styles['CustomBody']))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Plan Premium
    story.append(Paragraph("Plan Premium", styles['PlanName']))
    story.append(Paragraph("USD $18,000", styles['PriceHighlight']))
    story.append(Paragraph(
        "<b>Ideal para:</b> Inmobiliarias que quieren una solución personalizada, soporte extendido y exclusividad garantizada.",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        "<b>Incluye todo lo del Plan Completo, más:</b>",
        styles['CustomBody']
    ))
    
    plan_premium = [
        "<b>Personalización de marca</b> (logo, colores, mensajes)",
        "<b>Flujos de conversación personalizados</b> según tu operación",
        "<b>Integración con tu CRM actual</b> (si aplica)",
        "<b>Landing page personalizada</b> para captar leads",
        "<b>90 días de soporte técnico prioritario</b>",
        "<b>2 horas de capacitación</b> para tu equipo",
        "<b>Actualizaciones gratuitas</b> durante 6 meses",
        "Asesoría en estrategia de captación digital"
    ]
    for item in plan_premium:
        story.append(Paragraph(f"✓ {item}", styles['BulletPoint']))
    
    story.append(Paragraph("<b>Entrega:</b> 10-15 días hábiles", styles['CustomBody']))
    
    story.append(Spacer(1, 0.3*inch))
    
    # === COMPARATIVA ===
    story.append(Paragraph("Comparativa de Planes", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    compare_data = [
        ['Característica', 'Completo', 'Premium'],
        ['Código fuente completo', '✓', '✓'],
        ['Dominio incluido', '✓', '✓'],
        ['Instalación y setup', '✓', '✓'],
        ['Conexión WhatsApp', '✓', '✓'],
        ['Capacitación', '1 hora', '2 horas'],
        ['Soporte técnico', '30 días', '90 días'],
        ['Personalización de marca', '—', '✓'],
        ['Flujos personalizados', '—', '✓'],
        ['Landing page', '—', '✓'],
        ['Actualizaciones', '—', '6 meses'],
        ['Precio', '$10,000', '$18,000'],
    ]
    
    compare_table = Table(compare_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    compare_style = create_table_style()
    compare_style.add('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')
    compare_table.setStyle(compare_style)
    story.append(compare_table)
    
    story.append(PageBreak())
    
    # === ROI ===
    story.append(Paragraph("Retorno de Inversión (ROI)", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    story.append(Paragraph("<b>Ejemplo con 100 leads/mes:</b>", styles['CustomBody']))
    
    roi_data = [
        ['Métrica', 'Sin InmoBot', 'Con InmoBot'],
        ['Tasa de respuesta', '60%', '100%'],
        ['Conversión a cita', '3.5%', '7%'],
        ['Ventas estimadas', '2.1/mes', '7/mes'],
        ['Comisión promedio', '$5,000', '$5,000'],
        ['Ingreso mensual', '$10,500', '$35,000'],
    ]
    
    roi_table = Table(roi_data, colWidths=[2*inch, 2*inch, 2*inch])
    roi_table.setStyle(create_table_style())
    story.append(roi_table)
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        "<b>Ganancia adicional:</b> $24,500/mes",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        "<b>Recuperás la inversión:</b> En menos de 2-3 semanas",
        styles['CustomBody']
    ))
    
    story.append(Spacer(1, 0.3*inch))
    
    # === PROCESO ===
    story.append(Paragraph("Proceso de Implementación", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    process = [
        "<b>Día 1 - Confirmación:</b> Firma de acuerdo y pago inicial (50%)",
        "<b>Día 2-3 - Setup:</b> Instalación en servidor y dominio",
        "<b>Día 4-5 - Configuración:</b> Conexión de WhatsApp, IA y personalizaciones",
        "<b>Día 6 - Capacitación:</b> Videollamada de entrenamiento",
        "<b>Día 7 - Go Live:</b> ¡Tu bot está operativo!"
    ]
    for p in process:
        story.append(Paragraph(f"• {p}", styles['BulletPoint']))
    
    story.append(Spacer(1, 0.3*inch))
    
    # === FORMAS DE PAGO ===
    story.append(Paragraph("Formas de Pago", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    pagos = [
        "Transferencia bancaria",
        "Tarjeta de crédito (Stripe)",
        "PayPal",
        "Crypto (USDT, USDC)"
    ]
    for p in pagos:
        story.append(Paragraph(f"• {p}", styles['BulletPoint']))
    
    story.append(Paragraph(
        "<b>Modalidad:</b> 50% al confirmar, 50% al entregar",
        styles['CustomBody']
    ))
    
    story.append(Spacer(1, 0.3*inch))
    
    # === GARANTÍA ===
    story.append(Paragraph("Garantía", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    story.append(Paragraph(
        "<b>7 días de garantía de satisfacción</b>",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        "Si el bot no funciona como se describió, te devolvemos el 100% de tu dinero.",
        styles['CustomBody']
    ))
    
    story.append(PageBreak())
    
    # === TÉRMINOS DE LICENCIA ===
    story.append(Paragraph("Términos de Licencia", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=15))
    
    story.append(Paragraph(
        "<b>Tipo de Licencia: Exclusiva</b>",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        "Esta es una licencia exclusiva de uso. Al adquirir InmoBot:",
        styles['CustomBody']
    ))
    
    licencia_data = [
        ['Aspecto', 'Detalle'],
        ['Propiedad del código', 'Transferencia completa al comprador'],
        ['Exclusividad', 'El comprador es el único autorizado a usar este sistema'],
        ['Modificaciones', 'Libertad total para modificar, personalizar y extender'],
        ['Sublicencia', 'El comprador puede revender o sublicenciar si lo desea'],
        ['Restricciones al vendedor', 'No venderé este mismo código a otras inmobiliarias'],
    ]
    
    licencia_table = Table(licencia_data, colWidths=[2.2*inch, 4.3*inch])
    licencia_table.setStyle(create_table_style())
    story.append(licencia_table)
    
    story.append(Spacer(1, 0.25*inch))
    
    # Qué incluye la entrega
    story.append(Paragraph("<b>¿Qué incluye la entrega?</b>", styles['CustomBody']))
    entrega_items = [
        "Código fuente completo (repositorio Git)",
        "Base de datos configurada",
        "Documentación técnica",
        "Manual de usuario",
        "Credenciales de todas las integraciones",
        "Acceso al servidor de producción"
    ]
    for item in entrega_items:
        story.append(Paragraph(f"✓ {item}", styles['BulletPoint']))
    
    story.append(Spacer(1, 0.25*inch))
    
    # Período de soporte
    story.append(Paragraph("<b>Período de Soporte</b>", styles['CustomBody']))
    
    soporte_data = [
        ['Plan', 'Soporte Incluido', 'Soporte Extendido'],
        ['Completo', '30 días', '+$300/mes adicional'],
        ['Premium', '90 días', '+$200/mes adicional'],
    ]
    
    soporte_table = Table(soporte_data, colWidths=[1.5*inch, 2*inch, 2.5*inch])
    soporte_table.setStyle(create_table_style())
    story.append(soporte_table)
    
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("<b>El soporte incluye:</b>", styles['CustomBody']))
    soporte_incluye = ["Corrección de bugs", "Asistencia técnica por WhatsApp/email", "Pequeños ajustes de configuración"]
    for item in soporte_incluye:
        story.append(Paragraph(f"• {item}", styles['BulletPoint']))
    
    story.append(Paragraph("<b>El soporte NO incluye:</b>", styles['CustomBody']))
    soporte_no_incluye = ["Nuevas funcionalidades (se cotizan aparte)", "Cambios mayores en el diseño", "Integraciones adicionales"]
    for item in soporte_no_incluye:
        story.append(Paragraph(f"• {item}", styles['BulletPoint']))
    
    story.append(Spacer(1, 0.25*inch))
    
    # Post-soporte
    story.append(Paragraph("<b>Post-Soporte</b>", styles['CustomBody']))
    story.append(Paragraph(
        "Una vez finalizado el período de soporte:",
        styles['CustomBody']
    ))
    post_soporte = [
        "El sistema sigue funcionando sin intervención",
        "Hosting: El comprador asume el costo (~$20-50/mes en DigitalOcean o similar)",
        "Mantenimiento futuro: El comprador puede contratar soporte adicional, su propio desarrollador, o dejar el sistema funcionando sin cambios"
    ]
    for i, item in enumerate(post_soporte, 1):
        story.append(Paragraph(f"{i}. {item}", styles['BulletPoint']))
    
    story.append(Spacer(1, 0.25*inch))
    
    # Costos recurrentes
    story.append(Paragraph("<b>Costos Recurrentes del Comprador (estimados)</b>", styles['CustomBody']))
    
    costos_data = [
        ['Servicio', 'Costo Mensual'],
        ['Hosting (VPS)', '$20-50 USD'],
        ['WhatsApp Business API', '$0-50 USD (según volumen)'],
        ['OpenAI (IA)', '$10-30 USD (según uso)'],
        ['Dominio', '~$15 USD/año'],
        ['Total estimado', '$30-130 USD/mes'],
    ]
    
    costos_table = Table(costos_data, colWidths=[3*inch, 2.5*inch])
    costos_style = create_table_style()
    costos_style.add('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')
    costos_table.setStyle(costos_style)
    story.append(costos_table)
    
    story.append(Spacer(1, 0.5*inch))
    
    # === CONTACTO ===
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY_COLOR, spaceAfter=20))
    story.append(Paragraph("Contacto", styles['SectionHeader']))
    
    story.append(Paragraph("Email: hola@inmobot-ia.com", styles['CustomBody']))
    story.append(Paragraph("Demo: https://app.inmobot-ia.com/demo", styles['CustomBody']))
    
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "<i>InmoBot - Convertí consultas en ventas, mientras dormís.</i>",
        styles['CustomBody']
    ))
    
    # Generar PDF
    doc.build(story)
    print("✅ PDF generado exitosamente en: /app/docs/PROPUESTA_COMERCIAL.pdf")
    return True

if __name__ == '__main__':
    build_pdf()
