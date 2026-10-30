"""
Generador de Certificados PDF para eki
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
import logging

logger = logging.getLogger(__name__)


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
        texto_superior = "eki - Soluciones Educativas"
        texto_certificado = "CERTIFICADO DE FINALIZACIÓN"
    
    # === IMAGEN DE FONDO ===
    # Si la plantilla tiene imagen_fondo, usarla como fondo completo del certificado
    usa_imagen_fondo = False
    if plantilla and hasattr(plantilla, 'imagen_fondo') and plantilla.imagen_fondo:
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            
            # Abrir imagen con Pillow para validar y convertir
            img = Image.open(plantilla.imagen_fondo.path)
            
            # Convertir a RGB si es necesario (ej: PNG con transparencia)
            if img.mode in ('RGBA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img)
                img = bg
            
            # Guardar como temporal para ReportLab
            bg_path = os.path.join(temp_dir, f"cert_bg_{certificado.codigo_verificacion}.jpg")
            img.save(bg_path, 'JPEG', quality=95)
            
            # Dibujar imagen como fondo completo
            c.drawImage(bg_path, 0, 0, width=width, height=height, preserveAspectRatio=False)
            
            # Limpiar temporal
            try:
                os.remove(bg_path)
            except:
                pass
            
            usa_imagen_fondo = True
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"⚠️ No se pudo cargar imagen de fondo: {e}")
            usa_imagen_fondo = False
    
    # === LOGO DE INSTITUCIÓN ===
    if plantilla and hasattr(plantilla, 'logo_institucion') and plantilla.logo_institucion:
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            logo_path = os.path.join(temp_dir, f"cert_logo_{certificado.codigo_verificacion}.png")
            
            logo_img = Image.open(plantilla.logo_institucion.path)
            # Mantener transparencia para logos PNG
            logo_img.save(logo_path, 'PNG')
            
            # Dibujar logo centrado en la parte superior
            logo_w = 1.5 * inch
            logo_h = 1.5 * inch
            c.drawImage(logo_path, width/2 - logo_w/2, height - 1.8*inch, 
                        width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')
            
            try:
                os.remove(logo_path)
            except:
                pass
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"⚠️ No se pudo cargar logo: {e}")
    
    # === DISEÑO DEL CERTIFICADO ===
    
    # Si NO hay imagen de fondo, dibujar bordes y diseño por defecto
    if not usa_imagen_fondo:
        # 1. Borde decorativo
        c.setStrokeColor(colors.HexColor(color_primario))
        c.setLineWidth(3)
        c.rect(0.5*inch, 0.5*inch, width - inch, height - inch)
        
        c.setLineWidth(1)
        c.rect(0.6*inch, 0.6*inch, width - 1.2*inch, height - 1.2*inch)
    
    # === TEXTO SUPERPUESTO (funciona tanto con imagen de fondo como sin ella) ===
    
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
    c.drawString(2*inch, 1.2*inch, "Director eki")
    
    # Usar fecha de emisión si existe, sino fecha de completado
    fecha_emision = certificado.fecha_emision if certificado.fecha_emision else certificado.fecha_completado
    if hasattr(fecha_emision, 'strftime'):
        fecha_emision_str = fecha_emision.strftime('%d/%m/%Y')
    else:
        from datetime import datetime
        fecha_emision_str = datetime.now().strftime('%d/%m/%Y')
    
    c.drawString(width - 5*inch, 1.2*inch, f"Fecha de Emisión: {fecha_emision_str}")
    
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
    
    # Guardar QR temporalmente (compatible con Windows/Linux)
    import tempfile
    temp_dir = tempfile.gettempdir()
    qr_path = os.path.join(temp_dir, f"qr_{certificado.codigo_verificacion}.png")
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


def generar_certificado_imagen(certificado, plantilla):
    """
    Genera un certificado como IMAGEN (PNG/JPG) usando la imagen de fondo
    de la plantilla y superponiendo el nombre del estudiante.
    
    Ideal para: plantillas diseñadas externamente donde solo se necesita
    escribir el nombre del estudiante encima.
    
    Args:
        certificado: Instancia de Certificado
        plantilla: Instancia de PlantillaCertificado con imagen_fondo
    
    Returns:
        BytesIO: Buffer con la imagen generada (JPEG)
        None: Si no hay imagen_fondo disponible
    """
    if not plantilla or not plantilla.imagen_fondo:
        return None
    
    try:
        from PIL import ImageDraw, ImageFont
        
        # Abrir imagen de fondo
        img = Image.open(plantilla.imagen_fondo.path).copy()
        
        # Convertir a RGB si es necesario
        if img.mode in ('RGBA', 'P', 'LA'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img)
            img = bg
        
        draw = ImageDraw.Draw(img)
        ancho_img, alto_img = img.size
        
        # Intentar cargar una fuente grande para el nombre
        nombre_estudiante = certificado.estudiante.nombre.upper()
        font_size_nombre = int(ancho_img * 0.04)  # 4% del ancho de la imagen
        font_size_curso = int(ancho_img * 0.025)   # 2.5% del ancho
        font_size_fecha = int(ancho_img * 0.018)    # 1.8% del ancho
        
        try:
            # Intentar fuente del sistema
            fuentes_posibles = [
                "arial.ttf", "Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "C:\\Windows\\Fonts\\arial.ttf",
                "C:\\Windows\\Fonts\\arialbd.ttf",
            ]
            font_nombre = None
            for fuente in fuentes_posibles:
                try:
                    font_nombre = ImageFont.truetype(fuente, font_size_nombre)
                    font_curso = ImageFont.truetype(fuente, font_size_curso)
                    font_fecha = ImageFont.truetype(fuente, font_size_fecha)
                    break
                except (IOError, OSError):
                    continue
            
            if not font_nombre:
                font_nombre = ImageFont.load_default()
                font_curso = font_nombre
                font_fecha = font_nombre
        except Exception:
            font_nombre = ImageFont.load_default()
            font_curso = font_nombre
            font_fecha = font_nombre
        
        # Determinar color del texto según el color primario de la plantilla
        try:
            hex_color = plantilla.color_primario.lstrip('#')
            text_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            text_color = (44, 62, 80)  # #2C3E50
        
        # === SUPERPONER TEXTOS ===
        
        # Nombre del estudiante — centrado verticalmente al 55% del alto
        pos_y_nombre = int(alto_img * 0.50)
        bbox = draw.textbbox((0, 0), nombre_estudiante, font=font_nombre)
        text_w = bbox[2] - bbox[0]
        pos_x_nombre = (ancho_img - text_w) // 2
        draw.text((pos_x_nombre, pos_y_nombre), nombre_estudiante, fill=text_color, font=font_nombre)
        
        # Nombre del curso — centrado al 62%
        nombre_curso = certificado.curso.nombre
        pos_y_curso = int(alto_img * 0.62)
        try:
            hex_sec = plantilla.color_secundario.lstrip('#')
            curso_color = tuple(int(hex_sec[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            curso_color = (52, 152, 219)  # #3498DB
        bbox_c = draw.textbbox((0, 0), nombre_curso, font=font_curso)
        text_w_c = bbox_c[2] - bbox_c[0]
        pos_x_curso = (ancho_img - text_w_c) // 2
        draw.text((pos_x_curso, pos_y_curso), nombre_curso, fill=curso_color, font=font_curso)
        
        # Fecha — centrado al 72%
        fecha_str = certificado.fecha_completado.strftime("%d de %B de %Y") if certificado.fecha_completado else ""
        if fecha_str:
            pos_y_fecha = int(alto_img * 0.72)
            bbox_f = draw.textbbox((0, 0), fecha_str, font=font_fecha)
            text_w_f = bbox_f[2] - bbox_f[0]
            pos_x_fecha = (ancho_img - text_w_f) // 2
            draw.text((pos_x_fecha, pos_y_fecha), fecha_str, fill=(100, 100, 100), font=font_fecha)
        
        # Código de verificación — esquina inferior izquierda
        codigo = certificado.codigo_verificacion
        font_size_cod = int(ancho_img * 0.012)
        try:
            font_codigo = ImageFont.truetype(fuentes_posibles[0], font_size_cod)
        except Exception:
            font_codigo = ImageFont.load_default()
        draw.text((int(ancho_img * 0.05), int(alto_img * 0.92)), codigo, fill=(150, 150, 150), font=font_codigo)
        
        # Guardar como JPEG
        buffer = BytesIO()
        img.save(buffer, 'JPEG', quality=95)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"❌ Error generando certificado imagen: {e}")
        return None


def generar_certificado_desde_plantilla_pdf(certificado, plantilla):
    """
    Genera un certificado usando un PDF subido como plantilla de fondo.
    Crea una capa transparente con ReportLab (nombre, curso, fecha, QR)
    y la superpone sobre la primera página del PDF plantilla usando PyPDF2.
    
    Args:
        certificado: Instancia de Certificado
        plantilla: Instancia de PlantillaCertificado con archivo_plantilla_pdf
    
    Returns:
        BytesIO: Buffer con el PDF resultante
        None: Si falla
    """
    if not plantilla or not plantilla.archivo_plantilla_pdf:
        return None
    
    try:
        from PyPDF2 import PdfReader, PdfWriter
        import tempfile
        
        # 1. Leer la plantilla PDF subida
        plantilla_pdf_path = plantilla.archivo_plantilla_pdf.path
        reader = PdfReader(plantilla_pdf_path)
        if len(reader.pages) == 0:
            logger.error("❌ Plantilla PDF sin páginas")
            return None
        
        page = reader.pages[0]
        page_box = page.mediabox
        page_width = float(page_box.width)
        page_height = float(page_box.height)
        
        # 2. Crear capa de texto con ReportLab (overlay transparente)
        overlay_buffer = BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        
        # Nombre del estudiante
        nombre_estudiante = certificado.estudiante.nombre.upper()
        try:
            hex_color = plantilla.color_primario.lstrip('#')
            r_val = int(hex_color[0:2], 16) / 255.0
            g_val = int(hex_color[2:4], 16) / 255.0
            b_val = int(hex_color[4:6], 16) / 255.0
            c.setFillColorRGB(r_val, g_val, b_val)
        except Exception:
            c.setFillColor(colors.HexColor('#2C3E50'))
        
        # Tamaño de fuente proporcional al ancho de la página
        font_size_nombre = max(24, int(page_width * 0.035))
        font_size_curso = max(16, int(page_width * 0.022))
        font_size_fecha = max(12, int(page_width * 0.016))
        
        c.setFont("Helvetica-Bold", font_size_nombre)
        c.drawCentredString(page_width / 2, page_height * 0.50, nombre_estudiante)
        
        # Nombre del curso
        try:
            hex_sec = plantilla.color_secundario.lstrip('#')
            r2 = int(hex_sec[0:2], 16) / 255.0
            g2 = int(hex_sec[2:4], 16) / 255.0
            b2 = int(hex_sec[4:6], 16) / 255.0
            c.setFillColorRGB(r2, g2, b2)
        except Exception:
            c.setFillColor(colors.HexColor('#3498DB'))
        
        c.setFont("Helvetica", font_size_curso)
        c.drawCentredString(page_width / 2, page_height * 0.42, certificado.curso.nombre)
        
        # Fecha
        c.setFillColor(colors.grey)
        c.setFont("Helvetica", font_size_fecha)
        if certificado.fecha_completado:
            fecha_str = certificado.fecha_completado.strftime("%d/%m/%Y")
            c.drawCentredString(page_width / 2, page_height * 0.35, f"Fecha: {fecha_str}")
        
        # Calificación
        calificacion = float(certificado.calificacion_final)
        c.drawCentredString(page_width / 2, page_height * 0.30, f"Calificación: {calificacion}%")
        
        # Código de verificación
        c.setFont("Courier-Bold", 9)
        c.setFillColor(colors.Color(0.5, 0.5, 0.5, alpha=0.7))
        c.drawString(page_width * 0.05, page_height * 0.08, 
                     f"Código: {certificado.codigo_verificacion}")
        
        # QR
        url_verificacion = certificado.obtener_url_verificacion()
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(url_verificacion)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        temp_dir = tempfile.gettempdir()
        qr_path = os.path.join(temp_dir, f"qr_{certificado.codigo_verificacion}.png")
        qr_img.save(qr_path)
        
        qr_size = min(page_width, page_height) * 0.1
        c.drawImage(qr_path, page_width - qr_size - 30, 20, 
                    width=qr_size, height=qr_size)
        
        try:
            os.remove(qr_path)
        except Exception:
            pass
        
        c.showPage()
        c.save()
        overlay_buffer.seek(0)
        
        # 3. Leer overlay y fusionar con plantilla
        overlay_reader = PdfReader(overlay_buffer)
        overlay_page = overlay_reader.pages[0]
        
        writer = PdfWriter()
        # Merge: plantilla de fondo + overlay de texto encima
        page.merge_page(overlay_page)
        writer.add_page(page)
        
        # Si la plantilla tiene más páginas, agregarlas tal cual
        for i in range(1, len(reader.pages)):
            writer.add_page(reader.pages[i])
        
        # 4. Guardar resultado
        result_buffer = BytesIO()
        writer.write(result_buffer)
        result_buffer.seek(0)
        
        logger.info(f"✅ Certificado generado desde plantilla PDF para {certificado.estudiante.nombre}")
        return result_buffer
        
    except Exception as e:
        logger.error(f"❌ Error generando certificado desde plantilla PDF: {e}", exc_info=True)
        return None


def generar_certificado_desde_plantilla_imagen(certificado, plantilla):
    """
    Genera un certificado usando una IMAGEN subida como plantilla,
    superponiendo el nombre del estudiante, curso, fecha y QR.
    
    Usa el campo archivo_plantilla_imagen de la plantilla.
    Similar a generar_certificado_imagen() pero con el campo nuevo.
    
    Args:
        certificado: Instancia de Certificado
        plantilla: Instancia de PlantillaCertificado con archivo_plantilla_imagen
    
    Returns:
        BytesIO: Buffer con la imagen JPEG generada
        None: Si falla
    """
    if not plantilla or not plantilla.archivo_plantilla_imagen:
        return None
    
    try:
        from PIL import ImageDraw, ImageFont
        
        img = Image.open(plantilla.archivo_plantilla_imagen.path).copy()
        
        # Convertir a RGB si es necesario
        if img.mode in ('RGBA', 'P', 'LA'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img)
            img = bg
        
        draw = ImageDraw.Draw(img)
        ancho_img, alto_img = img.size
        
        nombre_estudiante = certificado.estudiante.nombre.upper()
        font_size_nombre = int(ancho_img * 0.04)
        font_size_curso = int(ancho_img * 0.025)
        font_size_fecha = int(ancho_img * 0.018)
        
        # Buscar fuente del sistema
        fuentes_posibles = [
            "arial.ttf", "Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ]
        font_nombre = None
        for fuente in fuentes_posibles:
            try:
                font_nombre = ImageFont.truetype(fuente, font_size_nombre)
                font_curso = ImageFont.truetype(fuente, font_size_curso)
                font_fecha = ImageFont.truetype(fuente, font_size_fecha)
                break
            except (IOError, OSError):
                continue
        
        if not font_nombre:
            font_nombre = ImageFont.load_default()
            font_curso = font_nombre
            font_fecha = font_nombre
        
        # Colores
        try:
            hex_color = plantilla.color_primario.lstrip('#')
            text_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            text_color = (44, 62, 80)
        
        # Nombre del estudiante — centrado al 50%
        pos_y_nombre = int(alto_img * 0.50)
        bbox = draw.textbbox((0, 0), nombre_estudiante, font=font_nombre)
        text_w = bbox[2] - bbox[0]
        pos_x_nombre = (ancho_img - text_w) // 2
        draw.text((pos_x_nombre, pos_y_nombre), nombre_estudiante, fill=text_color, font=font_nombre)
        
        # Nombre del curso — centrado al 62%
        try:
            hex_sec = plantilla.color_secundario.lstrip('#')
            curso_color = tuple(int(hex_sec[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            curso_color = (52, 152, 219)
        pos_y_curso = int(alto_img * 0.62)
        bbox_c = draw.textbbox((0, 0), certificado.curso.nombre, font=font_curso)
        text_w_c = bbox_c[2] - bbox_c[0]
        pos_x_curso = (ancho_img - text_w_c) // 2
        draw.text((pos_x_curso, pos_y_curso), certificado.curso.nombre, fill=curso_color, font=font_curso)
        
        # Fecha — centrado al 72%
        if certificado.fecha_completado:
            fecha_str = certificado.fecha_completado.strftime("%d de %B de %Y")
            pos_y_fecha = int(alto_img * 0.72)
            bbox_f = draw.textbbox((0, 0), fecha_str, font=font_fecha)
            text_w_f = bbox_f[2] - bbox_f[0]
            pos_x_fecha = (ancho_img - text_w_f) // 2
            draw.text((pos_x_fecha, pos_y_fecha), fecha_str, fill=(100, 100, 100), font=font_fecha)
        
        # Código de verificación
        font_size_cod = int(ancho_img * 0.012)
        try:
            font_codigo = ImageFont.truetype(fuentes_posibles[0], font_size_cod)
        except Exception:
            font_codigo = ImageFont.load_default()
        draw.text((int(ancho_img * 0.05), int(alto_img * 0.92)), 
                  certificado.codigo_verificacion, fill=(150, 150, 150), font=font_codigo)
        
        # Guardar como JPEG
        buffer = BytesIO()
        img.save(buffer, 'JPEG', quality=95)
        buffer.seek(0)
        
        logger.info(f"✅ Certificado imagen generado desde plantilla imagen para {certificado.estudiante.nombre}")
        return buffer
        
    except Exception as e:
        logger.error(f"❌ Error generando certificado desde plantilla imagen: {e}", exc_info=True)
        return None
