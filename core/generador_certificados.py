"""
Generador de Certificados PDF para EKI
Usa ReportLab para crear certificados profesionales
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import qrcode
from PIL import Image
import os


def generar_certificado_pdf(certificado, plantilla=None):
    """
    Genera un certificado PDF profesional
    
    Args:
        certificado: Instancia de Certificado
        plantilla: Instancia de PlantillaCertificado (opcional)
    
    Returns:
        BytesIO: Buffer con el PDF generado
    """
    # Crear buffer
    buffer = BytesIO()
    
    # Crear canvas (A4 horizontal)
    c = canvas.Canvas(buffer, pagesize=(A4[1], A4[0]))  # A4 landscape
    width, height = A4[1], A4[0]
    
    # Cargar plantilla o usar valores por defecto
    if plantilla:
        color_primario = plantilla.color_primario
        color_secundario = plantilla.color_secundario
        texto_superior = plantilla.texto_superior
        texto_certificado = plantilla.texto_certificado
    else:
        color_primario = '#2C3E50'
        color_secundario = '#3498DB'
        texto_superior = "EKI - Educación Agrícola para el Campo Colombiano"
        texto_certificado = "CERTIFICADO DE FINALIZACIÓN"
    
    # === DISEÑO DEL CERTIFICADO ===
    
    # 1. Borde decorativo
    c.setStrokeColor(colors.HexColor(color_primario))
    c.setLineWidth(3)
    c.rect(0.5*inch, 0.5*inch, width - inch, height - inch)
    
    c.setLineWidth(1)
    c.rect(0.6*inch, 0.6*inch, width - 1.2*inch, height - 1.2*inch)
    
    # 2. Encabezado - Logo y texto superior
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.HexColor(color_primario))
    c.drawCentredString(width/2, height - 1.5*inch, texto_superior)
    
    # 3. Título del certificado
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(colors.HexColor(color_secundario))
    c.drawCentredString(width/2, height - 2.5*inch, texto_certificado)
    
    # 4. Línea decorativa
    c.setStrokeColor(colors.HexColor(color_secundario))
    c.setLineWidth(2)
    c.line(width/2 - 3*inch, height - 2.8*inch, width/2 + 3*inch, height - 2.8*inch)
    
    # 5. Texto principal
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height - 3.5*inch, "Se otorga el presente certificado a")
    
    # 6. Nombre del estudiante (destacado)
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.HexColor(color_primario))
    c.drawCentredString(width/2, height - 4.2*inch, certificado.estudiante.nombre.upper())
    
    # 7. Texto del curso
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height - 4.8*inch, "Por haber completado satisfactoriamente el curso")
    
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.HexColor(color_secundario))
    c.drawCentredString(width/2, height - 5.4*inch, certificado.curso.nombre)
    
    # 8. Calificación y mención
    mencion = certificado.obtener_mencion()
    if mencion:
        c.setFont("Helvetica-BoldOblique", 16)
        c.setFillColor(colors.HexColor('#27AE60'))  # Verde
        c.drawCentredString(width/2, height - 6.0*inch, mencion)
    
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.black)
    calificacion_texto = f"Calificación Final: {certificado.calificacion_final}%"
    c.drawCentredString(width/2, height - 6.5*inch, calificacion_texto)
    
    # 9. Fechas
    c.setFont("Helvetica", 12)
    fecha_inicio_str = certificado.fecha_inicio.strftime("%d de %B de %Y")
    fecha_fin_str = certificado.fecha_completado.strftime("%d de %B de %Y")
    duracion = certificado.duracion_curso()
    
    c.drawCentredString(
        width/2, 
        height - 7.0*inch, 
        f"Período: {fecha_inicio_str} - {fecha_fin_str} ({duracion} días)"
    )
    
    # 10. Firma y fecha de emisión
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*inch, 1.5*inch, "_" * 30)
    c.drawString(width - 5*inch, 1.5*inch, "_" * 30)
    
    c.setFont("Helvetica", 10)
    c.drawString(2*inch, 1.2*inch, "Director EKI")
    c.drawString(width - 5*inch, 1.2*inch, f"Fecha de Emisión: {certificado.fecha_emision.strftime('%d/%m/%Y')}")
    
    # 11. Código de verificación y QR
    c.setFont("Courier-Bold", 10)
    c.setFillColor(colors.grey)
    c.drawString(
        1*inch,
        0.8*inch,
        f"Código de Verificación: {certificado.codigo_verificacion}"
    )
    
    # Generar QR code
    url_verificacion = certificado.obtener_url_verificacion()
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(url_verificacion)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Guardar QR temporalmente
    qr_path = f"/tmp/qr_{certificado.codigo_verificacion}.png"
    qr_img.save(qr_path)
    
    # Insertar QR en el PDF
    c.drawImage(qr_path, width - 2*inch, 0.5*inch, width=1*inch, height=1*inch)
    
    # Eliminar QR temporal
    try:
        os.remove(qr_path)
    except:
        pass
    
    c.setFont("Helvetica", 8)
    c.drawString(width - 2*inch, 0.3*inch, "Escanea para verificar")
    
    # 12. Pie de página
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawCentredString(
        width/2,
        0.5*inch,
        "Este certificado es válido y puede ser verificado en línea usando el código o QR"
    )
    
    # Finalizar y guardar
    c.showPage()
    c.save()
    
    # Retornar buffer
    buffer.seek(0)
    return buffer


def generar_certificado_simple(certificado):
    """
    Genera un certificado simple sin plantilla
    Útil para pruebas rápidas
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Título
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height - 2*inch, "CERTIFICADO DE FINALIZACIÓN")
    
    # Nombre
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 3*inch, certificado.estudiante.nombre)
    
    # Curso
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height - 4*inch, f"Curso: {certificado.curso.nombre}")
    
    # Calificación
    c.drawCentredString(width/2, height - 5*inch, f"Calificación: {certificado.calificacion_final}%")
    
    # Código
    c.setFont("Courier", 12)
    c.drawCentredString(width/2, height - 6*inch, certificado.codigo_verificacion)
    
    c.showPage()
    c.save()
    
    buffer.seek(0)
    return buffer
