"""
Servicio de Certificados
Maneja generación, envío y verificación de certificados digitales

NOTA CRÍTICA (Marzo 2026): El upload via Django S3Boto3Storage NO funcionaba 
correctamente — los archivos aparecían como guardados pero NO existían en S3 
(404). Se reemplazó por upload DIRECTO via boto3+presigned URLs.
"""

from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
import logging
import boto3
from botocore.config import Config as BotoConfig

logger = logging.getLogger(__name__)

# URL de plantilla por defecto en S3 (PNG con marcadores RGB)
DEFAULT_TEMPLATE_URL = "https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/certificadoeki.png"
# Fallback JPG si PNG no existe
DEFAULT_TEMPLATE_URL_JPG = "https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/certificadoeki.jpg"

# S3 constants
S3_CERT_PREFIX = "certificados/generados"
S3_REGION = "us-east-2"


def _get_s3_client():
    """Obtiene cliente boto3 S3 con signature v4"""
    return boto3.client(
        's3',
        aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
        aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
        config=BotoConfig(signature_version='s3v4', region_name=S3_REGION)
    )


def _subir_imagen_s3_directo(buffer, filename):
    """
    Sube imagen de certificado a S3 usando boto3 DIRECTAMENTE.
    NO usa Django S3Boto3Storage (que no guardaba bien).
    
    Returns:
        (s3_key, public_url) o (None, None) si falla
    """
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
    s3_key = f"{S3_CERT_PREFIX}/{filename}"
    
    try:
        s3_client = _get_s3_client()
        buffer.seek(0)
        
        s3_client.upload_fileobj(
            buffer,
            bucket,
            s3_key,
            ExtraArgs={
                'ContentType': 'image/png',
                'ContentDisposition': 'inline',
                'ACL': 'public-read',
            }
        )
        
        # Verificar que el archivo existe (HEAD)
        s3_client.head_object(Bucket=bucket, Key=s3_key)
        
        public_url = f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"✅ Certificado SUBIDO DIRECTO a S3: {s3_key} -> {public_url}")
        return s3_key, public_url
        
    except Exception as e:
        logger.error(f"❌ Error subiendo certificado a S3: {e}", exc_info=True)
        return None, None


def obtener_url_certificado_twilio(certificado):
    """
    Obtiene URL pública del certificado para enviar via Twilio.
    Twilio NECESITA poder hacer GET a la URL.
    
    Usa URL pública directa (ACL public-read) en lugar de presigned URLs
    para evitar URLs largas que podrían causar problemas con [MEDIA:] parsing.
    
    Prioridad:
    1. URL pública directa desde S3 key (verificado con HEAD)
    2. None
    """
    if not certificado.archivo_imagen:
        logger.warning(f"⚠️ obtener_url: Certificado sin archivo_imagen")
        return None
    
    try:
        s3_key = str(certificado.archivo_imagen.name)
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
        
        s3_client = _get_s3_client()
        
        # Verificar que existe en S3
        try:
            s3_client.head_object(Bucket=bucket, Key=s3_key)
        except Exception:
            logger.warning(f"⚠️ S3 key no existe: {s3_key}, intentando variantes...")
            variantes = [
                f"media/{s3_key}" if not s3_key.startswith("media/") else s3_key.replace("media/", "", 1),
                f"{S3_CERT_PREFIX}/{s3_key.split('/')[-1]}",
            ]
            found = False
            for v in variantes:
                try:
                    s3_client.head_object(Bucket=bucket, Key=v)
                    s3_key = v
                    found = True
                    logger.info(f"✅ Encontrado en variante: {v}")
                    break
                except Exception:
                    continue
            if not found:
                logger.error(f"❌ Certificado no encontrado en S3 en ninguna variante: {s3_key}")
                return None
        
        # URL pública directa (ACL public-read asegurado en upload)
        public_url = f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"✅ URL pública cert: {public_url}")
        return public_url
        
    except Exception as e:
        logger.error(f"❌ Error generando URL certificado: {e}")
        try:
            s3_key = str(certificado.archivo_imagen.name)
            bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
            return f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        except Exception:
            return None


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


def _guardar_cert_s3(certificado, img_buffer, label=""):
    """
    Sube el buffer de imagen a S3 via boto3 DIRECTO y actualiza el modelo.
    Retorna True si éxito.
    """
    filename = f"certificado_{certificado.codigo_verificacion}.png"
    img_buffer.seek(0)
    s3_key, public_url = _subir_imagen_s3_directo(img_buffer, filename)
    if s3_key:
        # Guardar el S3 key en el campo archivo_imagen (para referencia)
        certificado.archivo_imagen.name = s3_key
        logger.info(f"✅ {label}: S3 key={s3_key}, URL={public_url}")
        return True
    return False


def generar_y_guardar_certificado(certificado, plantilla=None, force=False):
    """
    Genera el certificado y lo sube a S3 via boto3 DIRECTO.
    
    NOTA: NO usa Django S3Boto3Storage.save() porque NO guardaba realmente
    los archivos (S3 devolvía 404). Usa boto3.upload_fileobj directamente.
    
    Prioridades:
      0) Marcadores RGB + url_plantilla_imagen (PlantillaCertificado en DB)
      1) Marcadores RGB + plantilla eki por defecto (S3)
      2) FALLBACK SIMPLE: texto sobre imagen sin marcadores (SIEMPRE funciona)
      3) Imagen blanca desde cero con Pillow
    
    GARANTÍA: Siempre genera archivo_imagen (PNG). Nunca cae a PDF.
    """
    # Si ya tiene imagen verificable en S3 y no es force, no regenerar
    if certificado.archivo_imagen and not force:
        # Verificar que realmente existe en S3
        try:
            s3_key = str(certificado.archivo_imagen.name)
            bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
            s3_client = _get_s3_client()
            s3_client.head_object(Bucket=bucket, Key=s3_key)
            logger.info(f"Certificado {certificado.codigo_verificacion} ya tiene imagen VERIFICADA en S3")
            return True
        except Exception:
            logger.warning(f"⚠️ Certificado {certificado.codigo_verificacion} tenía imagen pero NO EXISTE en S3, regenerando...")
    
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
        # EMPRESA marker = contacto_principal (representante), no nombre de empresa
        _cliente = certificado.estudiante.cliente if (certificado.estudiante and certificado.estudiante.cliente) else None
        org_nombre = getattr(_cliente, 'contacto_principal', '') or (getattr(_cliente, 'nombre', '') if _cliente else 'eki')
        nombre_est = certificado.estudiante.nombre
        cedula_est = certificado.estudiante.cedula or ''
        
        generado = False
        
        # =====================================================
        # PRIORIDAD 0: Marcadores RGB con plantilla de DB
        # =====================================================
        # Determinar URL de la plantilla: url_plantilla_imagen > archivo_plantilla_imagen.url
        plantilla_url_db = None
        if plantilla:
            if plantilla.url_plantilla_imagen:
                plantilla_url_db = plantilla.url_plantilla_imagen
                logger.info(f"📋 Usando url_plantilla_imagen: {plantilla_url_db}")
            elif plantilla.archivo_plantilla_imagen:
                try:
                    plantilla_url_db = plantilla.archivo_plantilla_imagen.url
                    logger.info(f"📋 Usando archivo_plantilla_imagen.url: {plantilla_url_db}")
                except Exception:
                    pass
        
        if not generado and plantilla_url_db:
            try:
                from .utils_certificados import generar_certificado_marcadores
                img_buffer = generar_certificado_marcadores(
                    plantilla_url_o_path=plantilla_url_db,
                    nombre_estudiante=nombre_est,
                    cedula_estudiante=cedula_est,
                    url_verificacion=url_verificacion,
                    organizacion_nombre=org_nombre,
                )
                if img_buffer:
                    generado = _guardar_cert_s3(certificado, img_buffer, "P0 Marcadores+DB")
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
                        generado = _guardar_cert_s3(certificado, img_buffer, f"P1 Marcadores+Default({url_template[-20:]})")
                        if generado:
                            break
                except Exception as e:
                    logger.warning(f"⚠️ P1 falló con {url_template}: {e}")
        
        # =====================================================
        # PRIORIDAD 2: FALLBACK SIMPLE (texto sobre imagen, sin marcadores)
        # =====================================================
        if not generado:
            template_url = plantilla_url_db or None
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
                        generado = _guardar_cert_s3(certificado, img_buffer, f"P2 Simple({url_try[-20:]})")
                        if generado:
                            break
                except Exception as e:
                    logger.warning(f"⚠️ P2 falló con {url_try}: {e}")
        
        # =====================================================
        # PRIORIDAD 3: Generar imagen desde cero con Pillow
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
                
                draw.text((200, 80), "CERTIFICADO DE FINALIZACIÓN", font=font_sm, fill="black")
                draw.text((200, 180), "Se otorga a:", font=font_sm, fill="gray")
                bbox = draw.textbbox((0, 0), nombre_est.title(), font=font_big)
                w = bbox[2] - bbox[0]
                draw.text(((1200 - w) // 2, 250), nombre_est.title(), font=font_big, fill="black")
                draw.text((200, 400), f"Cédula: {cedula_est}", font=font_sm, fill="gray")
                draw.text((200, 460), f"Organización: {org_nombre}", font=font_sm, fill="gray")
                curso_nombre = certificado.curso.nombre if certificado.curso else ''
                draw.text((200, 520), f"Curso: {curso_nombre}", font=font_sm, fill="gray")
                draw.text((200, 600), f"Fecha: {timezone.now().strftime('%d/%m/%Y')}", font=font_sm, fill="gray")
                draw.text((200, 660), f"Código: {certificado.codigo_verificacion}", font=font_sm, fill="gray")
                
                buf = BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                
                generado = _guardar_cert_s3(certificado, buf, "P3 Desde-Cero")
            except Exception as e:
                logger.error(f"❌ P3 falló: {e}")
        
        if generado:
            certificado.emitido = True
            certificado.fecha_emision = timezone.now()
            certificado.save()
            logger.info(f"✅ Certificado {certificado.codigo_verificacion} GUARDADO EN S3 - archivo_imagen.name={certificado.archivo_imagen.name}")
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
        
        # Preferir imagen sobre PDF — usar URL pública directa (ACL public-read)
        if certificado.archivo_imagen:
            usar_imagen = True
            media_url = obtener_url_certificado_twilio(certificado)
            if not media_url:
                # Fallback a URL pública directa sin /media/ prefix
                s3_key = str(certificado.archivo_imagen.name)
                bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
                media_url = f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

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


def evaluar_elegibilidad_certificado(estudiante, curso) -> tuple[bool, str | None]:
    """
    Reglas opcionales por cliente (nota mínima en modo calificación 1–5).
    Returns: (puede_emitir, motivo_si_no)
    """
    from decimal import Decimal

    from core.gamificacion_modo import (
        MODO_CALIFICACION,
        formatear_nota,
        get_modo_gamificacion,
        resumen_calificaciones_estudiante,
    )

    cliente = getattr(estudiante, 'cliente', None)
    if not cliente or not getattr(cliente, 'exigir_nota_minima_certificado', False):
        return True, None
    if get_modo_gamificacion(cliente) != MODO_CALIFICACION:
        return True, None

    resumen = resumen_calificaciones_estudiante(estudiante, curso.id if curso else None)
    promedio = resumen.get('promedio')
    if promedio is None or resumen.get('cantidad', 0) == 0:
        return True, None

    minima = Decimal(str(getattr(cliente, 'nota_minima_certificado', None) or 3))
    if promedio < minima:
        return False, (
            f'Su promedio es {formatear_nota(promedio)}/5 y se requiere al menos '
            f'{formatear_nota(minima)}/5 para el certificado.'
        )
    return True, None


def mensaje_whatsapp_sin_certificado(estudiante, curso, motivo: str | None = None) -> str:
    """Texto cuando el curso se completó pero no aplica certificado."""
    from core.gamificacion_modo import formatear_nota, resumen_calificaciones_estudiante

    cliente = getattr(estudiante, 'cliente', None)
    resumen = resumen_calificaciones_estudiante(estudiante, curso.id if curso else None)
    prom = resumen.get('promedio')
    prom_txt = f'{formatear_nota(prom)}/5' if prom is not None else '—'
    minima = getattr(cliente, 'nota_minima_certificado', 3) if cliente else 3
    detalle = motivo or (
        f'Su promedio ({prom_txt}) está por debajo del mínimo ({formatear_nota(minima)}/5) '
        'definido por su organización.'
    )
    return (
        '🎓 *Curso completado*\n\n'
        f'{detalle}\n\n'
        'Puede seguir repasando el material escribiendo *menú*. '
        'Si cree que hay un error, escriba *ayuda* para contactar al equipo.'
    )


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

    puede, motivo = evaluar_elegibilidad_certificado(estudiante, curso)
    if not puede:
        logger.info(
            'Certificado no emitido para %s — %s: %s',
            estudiante.nombre,
            curso.nombre,
            motivo,
        )
        return None

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
            'imagen_url': obtener_url_certificado_twilio(certificado) if certificado.archivo_imagen else None
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
