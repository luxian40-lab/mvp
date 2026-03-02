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
    Genera el certificado y lo guarda en el modelo.
    
    Prioridades:
      0) Marcadores RGB + url_plantilla_imagen (S3→S3) → archivo_imagen
      1) archivo_plantilla_imagen (subido local) → archivo_pdf
      1B) url_plantilla_imagen sin marcadores → archivo_pdf  
      2) archivo_plantilla_pdf → archivo_pdf
      3) imagen_fondo → archivo_pdf
      4) Generación PDF desde cero
    
    Args:
        certificado: Instancia de Certificado
        plantilla: PlantillaCertificado (opcional, usa la por defecto)
        force: Si es True, regenera aunque ya exista
    
    Returns:
        bool: True si se generó exitosamente
    """
    # Si ya tiene archivo y no es force, no regenerar
    if (certificado.archivo_pdf or certificado.archivo_imagen) and not force:
        logger.info(f"Certificado {certificado.codigo_verificacion} ya generado")
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
        
        # =====================================================
        # PRIORIDAD 0: MARCADORES RGB desde URL S3 → archivo_imagen
        # Lee plantilla de S3, detecta marcadores, genera PNG, guarda en archivo_imagen (→ S3)
        # =====================================================
        if not generado and plantilla and hasattr(plantilla, 'url_plantilla_imagen') and plantilla.url_plantilla_imagen:
            try:
                from .utils_certificados import generar_certificado_marcadores
                
                url_verificacion = certificado.obtener_url_verificacion()
                org_nombre = None
                if certificado.estudiante and hasattr(certificado.estudiante, 'cliente') and certificado.estudiante.cliente:
                    org_nombre = certificado.estudiante.cliente.nombre
                
                img_buffer = generar_certificado_marcadores(
                    plantilla_url_o_path=plantilla.url_plantilla_imagen,
                    nombre_estudiante=certificado.estudiante.nombre,
                    cedula_estudiante=certificado.estudiante.cedula or '',
                    url_verificacion=url_verificacion,
                    organizacion_nombre=org_nombre,
                )
                
                if img_buffer:
                    filename = f"certificado_{certificado.codigo_verificacion}.png"
                    certificado.archivo_imagen.save(
                        filename,
                        ContentFile(img_buffer.read()),
                        save=True
                    )
                    generado = True
                    logger.info(f"✅ Certificado generado con MARCADORES RGB desde S3: {plantilla.url_plantilla_imagen}")
            except ValueError as ve:
                # Marcadores no encontrados → caer a siguiente prioridad
                logger.info(f"ℹ️ Marcadores no detectados ({ve}), usando siguiente prioridad")
            except Exception as e:
                logger.warning(f"⚠️ Error con marcadores RGB: {e}, usando siguiente prioridad")
        
        # PRIORIDAD 1: Plantilla imagen subida (archivo_plantilla_imagen)
        if not generado and plantilla and hasattr(plantilla, 'archivo_plantilla_imagen') and plantilla.archivo_plantilla_imagen:
            img_buffer = generar_certificado_desde_plantilla_imagen(certificado, plantilla)
            if img_buffer:
                filename = f"certificado_{certificado.codigo_verificacion}.jpg"
                certificado.archivo_imagen.save(
                    filename,
                    ContentFile(img_buffer.read()),
                    save=True
                )
                generado = True
                logger.info(f"✅ Certificado generado desde plantilla IMAGEN subida: {plantilla.nombre}")
        
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
                certificado.archivo_imagen.save(
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
        if plantilla and (getattr(plantilla, 'archivo_plantilla_imagen', None) or getattr(plantilla, 'url_plantilla_imagen', None)):
            # Si el certificado tiene imagen generada
            if certificado.archivo_imagen:
                raw_url = certificado.archivo_imagen.url
                usar_imagen = True
                # Si ya es URL completa (S3), usarla directamente
                if raw_url.startswith('http'):
                    media_url = raw_url
                else:
                    if settings.DEBUG:
                        base_url = "http://localhost:8000"
                    else:
                        base_url = getattr(settings, 'BASE_URL', 'https://eki.com')
                    media_url = f"{base_url}{raw_url}"

        # Si no es plantilla imagen o no hay imagen generada, usar PDF como antes
        if not usar_imagen:
            raw_url = certificado.archivo_pdf.url
            if raw_url.startswith('http'):
                media_url = raw_url
            else:
                if settings.DEBUG:
                    base_url = "http://localhost:8000"
                else:
                    base_url = getattr(settings, 'BASE_URL', 'https://eki.com')
                media_url = f"{base_url}{raw_url}"

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
