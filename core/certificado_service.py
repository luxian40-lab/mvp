"""
Servicio de Certificados
Maneja generación, envío y verificación de certificados digitales
"""

from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# URL de plantilla por defecto en S3 (PNG con marcadores RGB)
DEFAULT_TEMPLATE_URL = "https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/certificadoeki.png"
# Fallback JPG si PNG no existe
DEFAULT_TEMPLATE_URL_JPG = "https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/certificadoeki.jpg"


def _generar_certificado_simple(plantilla_url, nombre_estudiante, cedula, org_nombre, url_verificacion):
    """
    FALLBACK BULLETPROOF: Descarga la plantilla de S3, escribe nombre/cédula/org
    en posiciones fijas (centro de la imagen), sin depender de marcadores RGB.
    Siempre devuelve un BytesIO con PNG.
    """
    import requests
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    import os
    
    logger.info(f"🔧 Generando certificado SIMPLE (sin marcadores) desde: {plantilla_url}")
    
    # Descargar plantilla
    resp = requests.get(plantilla_url, timeout=20)
    resp.raise_for_status()
    plantilla = Image.open(BytesIO(resp.content)).convert("RGB")
    ancho, alto = plantilla.size
    draw = ImageDraw.Draw(plantilla)
    
    # Cargar fuentes
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    try:
        fuente_nombre = ImageFont.truetype(os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 80)
        fuente_detalle = ImageFont.truetype(os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 40)
    except (IOError, OSError):
        logger.warning("⚠️ Fuente GreatVibes no encontrada, usando default")
        fuente_nombre = ImageFont.load_default()
        fuente_detalle = ImageFont.load_default()
    
    # Escribir NOMBRE centrado al 45% de la altura
    nombre_cap = nombre_estudiante.strip().title()
    bbox_n = draw.textbbox((0, 0), nombre_cap, font=fuente_nombre)
    w_n = bbox_n[2] - bbox_n[0]
    h_n = bbox_n[3] - bbox_n[1]
    draw.text(
        ((ancho - w_n) // 2, int(alto * 0.45) - h_n // 2),
        nombre_cap, font=fuente_nombre, fill="black"
    )
    
    # Escribir CÉDULA centrada al 55%
    if cedula:
        bbox_c = draw.textbbox((0, 0), str(cedula), font=fuente_detalle)
        w_c = bbox_c[2] - bbox_c[0]
        draw.text(
            ((ancho - w_c) // 2, int(alto * 0.55)),
            str(cedula), font=fuente_detalle, fill="black"
        )
    
    # Escribir ORGANIZACIÓN centrada al 62%
    if org_nombre:
        bbox_o = draw.textbbox((0, 0), org_nombre, font=fuente_detalle)
        w_o = bbox_o[2] - bbox_o[0]
        draw.text(
            ((ancho - w_o) // 2, int(alto * 0.62)),
            org_nombre, font=fuente_detalle, fill="black"
        )
    
    # QR en esquina inferior derecha
    try:
        import qrcode
        qr_img = qrcode.make(url_verificacion).resize((180, 180))
        plantilla.paste(qr_img, (ancho - 220, alto - 220))
    except Exception as qr_e:
        logger.warning(f"⚠️ No se pudo generar QR: {qr_e}")
    
    buf = BytesIO()
    plantilla.save(buf, format="PNG")
    buf.seek(0)
    logger.info(f"✅ Certificado SIMPLE generado para: {nombre_cap}")
    return buf


def generar_y_guardar_certificado(certificado, plantilla=None, force=False):
    """
    Genera el certificado y lo guarda como IMAGEN (siempre).
    
    Prioridades:
      0) Marcadores RGB + url_plantilla_imagen (PlantillaCertificado en DB)
      1) Marcadores RGB + plantilla eki por defecto (S3)
      2) FALLBACK SIMPLE: texto sobre imagen sin marcadores (SIEMPRE funciona)
    
    GARANTÍA: Siempre genera archivo_imagen (PNG). Nunca cae a PDF.
    """
    # Si ya tiene imagen y no es force, no regenerar
    if certificado.archivo_imagen and not force:
        logger.info(f"Certificado {certificado.codigo_verificacion} ya tiene imagen")
        return True
    
    try:
        from .models_certificados import PlantillaCertificado
        
        # === Buscar plantilla en DB: curso+cliente > curso > cliente > default ===
        if not plantilla:
            if hasattr(certificado, 'curso') and certificado.curso:
                if certificado.estudiante and certificado.estudiante.cliente:
                    plantilla = PlantillaCertificado.objects.filter(
                        curso=certificado.curso, cliente=certificado.estudiante.cliente, activa=True
                    ).first()
                if not plantilla:
                    plantilla = PlantillaCertificado.objects.filter(
                        curso=certificado.curso, activa=True
                    ).first()
            if not plantilla and certificado.estudiante and certificado.estudiante.cliente:
                plantilla = PlantillaCertificado.objects.filter(
                    cliente=certificado.estudiante.cliente, curso__isnull=True, activa=True
                ).first()
            if not plantilla:
                plantilla = PlantillaCertificado.objects.filter(por_defecto=True, activa=True).first()
            
            logger.info(f"📋 Plantilla encontrada: {plantilla.nombre if plantilla else 'NINGUNA - usará default eki'}")
        
        url_verificacion = certificado.obtener_url_verificacion()
        org_nombre = certificado.estudiante.cliente.nombre if (certificado.estudiante and certificado.estudiante.cliente) else 'eki'
        nombre_est = certificado.estudiante.nombre
        cedula_est = certificado.estudiante.cedula or ''
        
        generado = False
        
        # =====================================================
        # PRIORIDAD 0: Marcadores RGB con plantilla de DB
        # =====================================================
        if not generado and plantilla and plantilla.url_plantilla_imagen:
            try:
                from .utils_certificados import generar_certificado_marcadores
                img_buffer = generar_certificado_marcadores(
                    plantilla_url_o_path=plantilla.url_plantilla_imagen,
                    nombre_estudiante=nombre_est,
                    cedula_estudiante=cedula_est,
                    url_verificacion=url_verificacion,
                    organizacion_nombre=org_nombre,
                )
                if img_buffer:
                    filename = f"certificado_{certificado.codigo_verificacion}.png"
                    certificado.archivo_imagen.save(filename, ContentFile(img_buffer.read()), save=True)
                    generado = True
                    logger.info(f"✅ P0: Certificado con marcadores RGB desde plantilla DB: {plantilla.url_plantilla_imagen}")
            except Exception as e:
                logger.warning(f"⚠️ P0 falló ({e}), continuando...")
        
        # =====================================================
        # PRIORIDAD 1: Marcadores RGB con plantilla eki default (S3)
        # =====================================================
        if not generado:
            for url_template in [DEFAULT_TEMPLATE_URL, DEFAULT_TEMPLATE_URL_JPG]:
                try:
                    from .utils_certificados import generar_certificado_marcadores
                    img_buffer = generar_certificado_marcadores(
                        plantilla_url_o_path=url_template,
                        nombre_estudiante=nombre_est,
                        cedula_estudiante=cedula_est,
                        url_verificacion=url_verificacion,
                        organizacion_nombre=org_nombre,
                    )
                    if img_buffer:
                        filename = f"certificado_{certificado.codigo_verificacion}.png"
                        certificado.archivo_imagen.save(filename, ContentFile(img_buffer.read()), save=True)
                        generado = True
                        logger.info(f"✅ P1: Certificado con marcadores RGB desde default: {url_template}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ P1 falló con {url_template}: {e}")
        
        # =====================================================
        # PRIORIDAD 2: FALLBACK SIMPLE (texto sobre imagen, sin marcadores)
        # Esto SIEMPRE funciona si la imagen existe en S3
        # =====================================================
        if not generado:
            template_url = (plantilla.url_plantilla_imagen if plantilla and plantilla.url_plantilla_imagen else None)
            for url_try in [u for u in [template_url, DEFAULT_TEMPLATE_URL, DEFAULT_TEMPLATE_URL_JPG] if u]:
                try:
                    img_buffer = _generar_certificado_simple(
                        plantilla_url=url_try,
                        nombre_estudiante=nombre_est,
                        cedula=cedula_est,
                        org_nombre=org_nombre,
                        url_verificacion=url_verificacion,
                    )
                    if img_buffer:
                        filename = f"certificado_{certificado.codigo_verificacion}.png"
                        certificado.archivo_imagen.save(filename, ContentFile(img_buffer.read()), save=True)
                        generado = True
                        logger.info(f"✅ P2: Certificado SIMPLE (sin marcadores) desde: {url_try}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ P2 falló con {url_try}: {e}")
        
        # =====================================================
        # PRIORIDAD 3: Generar imagen desde cero con Pillow (sin plantilla de S3)
        # Último recurso absoluto — crea una imagen blanca con texto
        # =====================================================
        if not generado:
            try:
                from PIL import Image, ImageDraw, ImageFont
                from io import BytesIO
                import os
                
                logger.info("🔧 P3: Generando certificado desde CERO (imagen blanca)")
                img = Image.new('RGB', (1200, 800), color='white')
                draw = ImageDraw.Draw(img)
                
                fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
                try:
                    font_big = ImageFont.truetype(os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 60)
                    font_sm = ImageFont.truetype(os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 30)
                except (IOError, OSError):
                    font_big = ImageFont.load_default()
                    font_sm = ImageFont.load_default()
                
                # Título
                draw.text((200, 80), "CERTIFICADO DE FINALIZACIÓN", font=font_sm, fill="black")
                draw.text((200, 180), "Se otorga a:", font=font_sm, fill="gray")
                # Nombre
                bbox = draw.textbbox((0, 0), nombre_est.title(), font=font_big)
                w = bbox[2] - bbox[0]
                draw.text(((1200 - w) // 2, 250), nombre_est.title(), font=font_big, fill="black")
                # Cédula
                draw.text((200, 400), f"Cédula: {cedula_est}", font=font_sm, fill="gray")
                # Org
                draw.text((200, 460), f"Organización: {org_nombre}", font=font_sm, fill="gray")
                # Curso
                curso_nombre = certificado.curso.nombre if certificado.curso else ''
                draw.text((200, 520), f"Curso: {curso_nombre}", font=font_sm, fill="gray")
                # Fecha
                draw.text((200, 600), f"Fecha: {timezone.now().strftime('%d/%m/%Y')}", font=font_sm, fill="gray")
                # Código
                draw.text((200, 660), f"Código: {certificado.codigo_verificacion}", font=font_sm, fill="gray")
                
                buf = BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                
                filename = f"certificado_{certificado.codigo_verificacion}.png"
                certificado.archivo_imagen.save(filename, ContentFile(buf.read()), save=True)
                generado = True
                logger.info(f"✅ P3: Certificado generado DESDE CERO (imagen blanca)")
            except Exception as e:
                logger.error(f"❌ P3 falló: {e}")
        
        if generado:
            certificado.emitido = True
            certificado.fecha_emision = timezone.now()
            certificado.save()
            logger.info(f"✅ Certificado {certificado.codigo_verificacion} GUARDADO - archivo_imagen={bool(certificado.archivo_imagen)}")
        else:
            logger.error(f"❌ TODAS las prioridades fallaron para certificado {certificado.codigo_verificacion}")
        
        return generado
        
    except Exception as e:
        logger.error(f"❌ Error generando certificado {certificado.codigo_verificacion}: {e}", exc_info=True)
        return False


def enviar_certificado_whatsapp(certificado):
    """
    Envía el certificado por WhatsApp al estudiante
    
    Args:
        certificado: Instancia de Certificado
    
    Returns:
        bool: True si se envió exitosamente
    """
    if not certificado.emitido or (not certificado.archivo_pdf and not certificado.archivo_imagen):
        logger.error(f"Certificado {certificado.codigo_verificacion} no está generado")
        return False

    try:
        from .utils import enviar_whatsapp_twilio
        from .models_certificados import PlantillaCertificado

        estudiante = certificado.estudiante
        curso = certificado.curso

        # Determinar si el certificado fue generado desde plantilla imagen
        plantilla = None
        if hasattr(certificado, 'plantilla_certificado'):
            plantilla = certificado.plantilla_certificado
        else:
            # Si no hay relación directa, intentar buscar por curso o lógica de tu sistema
            from .models_certificados import PlantillaCertificado as PC
            plantilla = PC.objects.filter(por_defecto=True, activa=True).first()

        usar_imagen = False
        media_url = None
        
        # Preferir imagen sobre PDF — usar URL pública directa (AWS_DEFAULT_ACL=public-read)
        if certificado.archivo_imagen:
            usar_imagen = True
            media_url = certificado.archivo_imagen.url

        # Si no hay imagen, usar PDF
        if not usar_imagen:
            if certificado.archivo_pdf:
                media_url = certificado.archivo_pdf.url
            else:
                logger.error(f"Certificado {certificado.codigo_verificacion} no tiene archivo")
                return False

        verificacion_url = certificado.obtener_url_verificacion()
        mencion = certificado.obtener_mencion()
        calificacion = float(certificado.calificacion_final)

        mensaje = f"""🎓 *¡FELICITACIONES {estudiante.nombre.upper()}!* 🎉

Has completado exitosamente el curso:
📚 *{curso.nombre}*

📊 *Calificación Final:* {calificacion}%"""
        if mencion:
            mensaje += f"\n🏆 *{mencion}*"

        mensaje += f"""

📜 Tu certificado digital está listo:
🔗 {media_url}

✅ Puedes verificar su autenticidad aquí:
{verificacion_url}

🔐 Código de verificación:
`{certificado.codigo_verificacion}`

¡Comparte tu logro con orgullo! 🌟"""

        # Enviar con media_url (imagen o PDF)
        resultado = enviar_whatsapp_twilio(
            telefono=estudiante.telefono,
            texto=mensaje,
            media_url=media_url
        )

        if resultado['success']:
            certificado.enviado_whatsapp = True
            certificado.fecha_envio = timezone.now()
            certificado.save()
            logger.info(f"✅ Certificado {certificado.codigo_verificacion} enviado a {estudiante.telefono}")
            return True
        else:
            logger.error(f"❌ Error enviando certificado: {resultado.get('error')}")
            return False

    except Exception as e:
        logger.error(f"❌ Error enviando certificado {certificado.codigo_verificacion}: {e}", exc_info=True)
        return False


def calcular_calificacion_curso(estudiante, curso):
    """
    Calcula la calificación final del estudiante en un curso
    Basado en preguntas de módulos respondidas correctamente
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso
    
    Returns:
        float: Calificación de 0-100
    """
    from .models import ModuloCompletado
    
    # Obtener todos los módulos completados del curso con pregunta respondida
    modulos_completados = ModuloCompletado.objects.filter(
        progreso__estudiante=estudiante,
        progreso__curso=curso,
        pregunta_respondida__isnull=False  # Solo contar los que tienen pregunta
    )
    
    if not modulos_completados.exists():
        # Si no hay preguntas, dar calificación por defecto de 100
        return 100.0
    
    # Calcular porcentaje de respuestas correctas
    total_preguntas = modulos_completados.count()
    respuestas_correctas = modulos_completados.filter(respuesta_correcta=True).count()
    
    calificacion = (respuestas_correctas / total_preguntas) * 100
    return round(calificacion, 2)


def crear_certificado_automatico(estudiante, curso):
    """
    Crea automáticamente un certificado cuando el estudiante completa el curso
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso
    
    Returns:
        Certificado o None si falla
    """
    from .models_certificados import Certificado
    from .models import ProgresoEstudiante
    
    # Verificar que el curso esté completo
    progreso = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        curso=curso
    ).first()
    
    if not progreso or not progreso.completado:
        logger.warning(f"Curso {curso.nombre} no completado para {estudiante.nombre}")
        return None
    
    # Verificar si ya existe certificado
    certificado_existente = Certificado.objects.filter(
        estudiante=estudiante,
        curso=curso
    ).first()
    
    if certificado_existente:
        logger.info(f"Ya existe certificado para {estudiante.nombre} - {curso.nombre}")
        return certificado_existente
    
    try:
        # Calcular calificación
        calificacion = calcular_calificacion_curso(estudiante, curso)
        
        # Obtener fecha de inicio (primer módulo completado)
        from .models import ModuloCompletado
        primer_modulo = ModuloCompletado.objects.filter(
            progreso=progreso
        ).order_by('fecha_completado').first()
        
        fecha_inicio = primer_modulo.fecha_completado.date() if primer_modulo else progreso.fecha_inicio.date()
        fecha_completado = progreso.fecha_completado.date() if progreso.fecha_completado else timezone.now().date()
        
        # Crear certificado
        certificado = Certificado.objects.create(
            estudiante=estudiante,
            curso=curso,
            calificacion_final=calificacion,
            fecha_inicio=fecha_inicio,
            fecha_completado=fecha_completado,
        )
        
        # Generar PDF automáticamente
        generar_y_guardar_certificado(certificado)
        
        logger.info(f"✅ Certificado creado para {estudiante.nombre} - {curso.nombre} ({calificacion}%)")
        return certificado
        
    except Exception as e:
        logger.error(f"❌ Error creando certificado: {e}", exc_info=True)
        return None


def verificar_certificado_publico(codigo_verificacion):
    """
    Verifica un certificado por su código
    
    Args:
        codigo_verificacion: Código del certificado (eki-XXXX-YYYY-ZZZZ)
    
    Returns:
        dict con información del certificado o None si no existe
    """
    from .models_certificados import Certificado
    
    try:
        certificado = Certificado.objects.select_related(
            'estudiante', 
            'curso'
        ).get(
            codigo_verificacion=codigo_verificacion.upper(),
            emitido=True
        )
        
        return {
            'valido': True,
            'codigo': certificado.codigo_verificacion,
            'estudiante': certificado.estudiante.nombre,
            'curso': certificado.curso.nombre,
            'calificacion': float(certificado.calificacion_final),
            'mencion': certificado.obtener_mencion(),
            'fecha_inicio': certificado.fecha_inicio,
            'fecha_completado': certificado.fecha_completado,
            'fecha_emision': certificado.fecha_emision,
            'duracion_dias': certificado.duracion_curso(),
            'pdf_url': certificado.archivo_pdf.url if certificado.archivo_pdf else None,
            'imagen_url': certificado.archivo_imagen.url if certificado.archivo_imagen else None
        }
        
    except Certificado.DoesNotExist:
        return {
            'valido': False,
            'error': 'Certificado no encontrado o no válido'
        }
    except Exception as e:
        logger.error(f"Error verificando certificado {codigo_verificacion}: {e}")
        return {
            'valido': False,
            'error': 'Error al verificar el certificado'
        }
