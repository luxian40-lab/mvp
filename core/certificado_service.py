"""
Servicio de Certificados
Maneja generación, envío y verificación de certificados digitales
"""

from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def generar_y_guardar_certificado(certificado, plantilla=None, force=False):
    """
    Genera el PDF del certificado y lo guarda en el modelo
    
    Args:
        certificado: Instancia de Certificado
        plantilla: PlantillaCertificado (opcional, usa la por defecto)
        force: Si es True, regenera aunque ya exista
    
    Returns:
        bool: True si se generó exitosamente
    """
    # Si ya tiene PDF y no es force, no regenerar
    if certificado.archivo_pdf and not force:
        logger.info(f"Certificado {certificado.codigo_verificacion} ya tiene PDF")
        return True
    
    try:
        from .generador_certificados import (
            generar_certificado_pdf, 
            generar_certificado_imagen,
            generar_certificado_desde_plantilla_pdf,
            generar_certificado_desde_plantilla_imagen,
        )
        from .models_certificados import PlantillaCertificado
        
        # Obtener plantilla
        if not plantilla:
            plantilla = PlantillaCertificado.objects.filter(
                por_defecto=True, 
                activa=True
            ).first()
        
        generado = False
        
        # PRIORIDAD 1: Plantilla imagen subida (archivo_plantilla_imagen)
        if not generado and plantilla and hasattr(plantilla, 'archivo_plantilla_imagen') and plantilla.archivo_plantilla_imagen:
            img_buffer = generar_certificado_desde_plantilla_imagen(certificado, plantilla)
            if img_buffer:
                filename = f"certificado_{certificado.codigo_verificacion}.jpg"
                certificado.archivo_pdf.save(
                    filename,
                    ContentFile(img_buffer.read()),
                    save=True
                )
                generado = True
                logger.info(f"✅ Certificado generado desde plantilla IMAGEN subida: {plantilla.nombre}")
        
        # PRIORIDAD 1B: URL de imagen externa (url_plantilla_imagen)
        if not generado and plantilla and hasattr(plantilla, 'url_plantilla_imagen') and plantilla.url_plantilla_imagen:
            try:
                import requests
                from io import BytesIO
                from PIL import Image as PILImage
                
                response = requests.get(plantilla.url_plantilla_imagen, timeout=15)
                response.raise_for_status()
                
                # Guardar imagen descargada temporalmente como archivo en la plantilla
                img_data = BytesIO(response.content)
                # Verificar que sea imagen válida
                PILImage.open(img_data).verify()
                img_data.seek(0)
                
                # Usar directamente con generar_certificado_desde_plantilla_imagen
                # Necesitamos pasar el buffer, así que guardamos temporalmente
                from django.core.files.uploadedfile import SimpleUploadedFile
                temp_img = SimpleUploadedFile(
                    name="plantilla_url_temp.jpg",
                    content=img_data.read(),
                    content_type='image/jpeg'
                )
                # Guardar temporalmente en la plantilla para que el generador lo use
                plantilla.archivo_plantilla_imagen.save(
                    f"plantilla_url_{plantilla.id}.jpg",
                    temp_img,
                    save=True
                )
                
                img_buffer = generar_certificado_desde_plantilla_imagen(certificado, plantilla)
                if img_buffer:
                    filename = f"certificado_{certificado.codigo_verificacion}.jpg"
                    certificado.archivo_pdf.save(
                        filename,
                        ContentFile(img_buffer.read()),
                        save=True
                    )
                    generado = True
                    logger.info(f"✅ Certificado generado desde URL de imagen: {plantilla.url_plantilla_imagen}")
            except Exception as e:
                logger.warning(f"⚠️ Error descargando imagen desde URL: {e}")
        
        # PRIORIDAD 2: Plantilla PDF subida (archivo_plantilla_pdf)
        if not generado and plantilla and plantilla.archivo_plantilla_pdf:
            pdf_buffer = generar_certificado_desde_plantilla_pdf(certificado, plantilla)
            if pdf_buffer:
                filename = f"certificado_{certificado.codigo_verificacion}.pdf"
                certificado.archivo_pdf.save(
                    filename,
                    ContentFile(pdf_buffer.read()),
                    save=True
                )
                generado = True
                logger.info(f"✅ Certificado generado desde plantilla PDF subida: {plantilla.nombre}")
        
        # PRIORIDAD 3: Imagen de fondo (imagen_fondo) → certificado imagen
        if not generado and plantilla and plantilla.imagen_fondo:
            img_buffer = generar_certificado_imagen(certificado, plantilla)
            if img_buffer:
                filename = f"certificado_{certificado.codigo_verificacion}.jpg"
                certificado.archivo_pdf.save(
                    filename,
                    ContentFile(img_buffer.read()),
                    save=True
                )
                generado = True
                logger.info(f"✅ Certificado imagen generado con imagen_fondo: {plantilla.nombre}")
        
        # PRIORIDAD 4: Generación PDF desde cero (sin plantilla o plantilla sin archivos)
        if not generado:
            pdf_buffer = generar_certificado_pdf(certificado, plantilla)
            filename = f"certificado_{certificado.codigo_verificacion}.pdf"
            certificado.archivo_pdf.save(
                filename,
                ContentFile(pdf_buffer.read()),
                save=True
            )
            generado = True
        
        # Marcar como emitido
        certificado.emitido = True
        certificado.fecha_emision = timezone.now()
        certificado.save()
        
        logger.info(f"✅ Certificado {certificado.codigo_verificacion} generado exitosamente")
        return True
        
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
    if not certificado.emitido or not certificado.archivo_pdf:
        logger.error(f"Certificado {certificado.codigo_verificacion} no está generado")
        return False
    
    try:
        from .utils import enviar_whatsapp_twilio
        
        estudiante = certificado.estudiante
        curso = certificado.curso
        
        # Construir URL del PDF
        if settings.DEBUG:
            base_url = "http://localhost:8000"
        else:
            base_url = getattr(settings, 'BASE_URL', 'https://eki.com')
        
        pdf_url = f"{base_url}{certificado.archivo_pdf.url}"
        verificacion_url = certificado.obtener_url_verificacion()
        
        # Construir mensaje
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
🔗 {pdf_url}

✅ Puedes verificar su autenticidad aquí:
{verificacion_url}

🔐 Código de verificación:
`{certificado.codigo_verificacion}`

¡Comparte tu logro con orgullo! 🌟"""
        
        # Enviar
        resultado = enviar_whatsapp_twilio(
            telefono=estudiante.telefono,
            texto=mensaje
        )
        
        if resultado['success']:
            # Marcar como enviado
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
        codigo_verificacion: Código del certificado (EKI-XXXX-YYYY-ZZZZ)
    
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
            'pdf_url': certificado.archivo_pdf.url if certificado.archivo_pdf else None
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
