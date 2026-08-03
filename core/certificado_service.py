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
import time
import boto3
from botocore.config import Config as BotoConfig

logger = logging.getLogger(__name__)

# Tras plantilla Twilio, pausa breve antes del diploma (mensaje de sesión + imagen).
PAUSA_TRAS_PLANTILLA_SEG = 2.0
MAX_REINTENTOS_ENVIO_DIPLOMA = 3

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


def _subir_bytes_s3_directo(buffer, filename, content_type='image/png'):
    """
    Sube bytes de certificado a S3 usando boto3 DIRECTAMENTE.
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
                'ContentType': content_type,
                'ContentDisposition': 'inline',
                'ACL': 'public-read',
            }
        )

        s3_client.head_object(Bucket=bucket, Key=s3_key)

        public_url = f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"✅ Certificado SUBIDO DIRECTO a S3: {s3_key} -> {public_url}")
        return s3_key, public_url

    except Exception as e:
        logger.error(f"❌ Error subiendo certificado a S3: {e}", exc_info=True)
        return None, None


def _subir_imagen_s3_directo(buffer, filename):
    """Compat: sube PNG del diploma."""
    return _subir_bytes_s3_directo(buffer, filename, content_type='image/png')


def hash_sha256_buffer(buffer) -> str:
    """SHA-256 hex del contenido actual del buffer (sin alterar posición final)."""
    import hashlib

    pos = buffer.tell()
    buffer.seek(0)
    digest = hashlib.sha256(buffer.read()).hexdigest()
    buffer.seek(pos)
    return digest


def png_buffer_a_pdf(png_buffer):
    """
    Convierte un PNG (BytesIO) a PDF de una página con el diploma a tamaño real.
    WhatsApp sigue usando PNG; el PDF es el artefacto descargable/verificable.
    """
    from io import BytesIO

    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    png_buffer.seek(0)
    raw = png_buffer.read()
    with Image.open(BytesIO(raw)) as img:
        w_px, h_px = img.size
        max_w, max_h = 1100, 850
        scale = min(max_w / float(w_px), max_h / float(h_px), 1.0)
        page_w = max(1, int(w_px * scale))
        page_h = max(1, int(h_px * scale))

    out = BytesIO()
    c = canvas.Canvas(out, pagesize=(page_w, page_h))
    c.drawImage(
        ImageReader(BytesIO(raw)),
        0,
        0,
        width=page_w,
        height=page_h,
        preserveAspectRatio=True,
        mask='auto',
    )
    c.showPage()
    c.save()
    out.seek(0)
    return out


def organizacion_emisora_de(certificado) -> str:
    """Nombre de organización para diploma y verificación (cliente.nombre, no contacto)."""
    est = getattr(certificado, 'estudiante', None)
    cliente = getattr(est, 'cliente', None) if est else None
    if cliente:
        nombre = (getattr(cliente, 'nombre', None) or '').strip()
        if nombre:
            return nombre
    snap = (getattr(certificado, 'organizacion_emisora', None) or '').strip()
    return snap or 'eki'


def url_publica_s3_key(s3_key: str | None) -> str | None:
    if not s3_key:
        return None
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
    return f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{s3_key}"


def obtener_url_pdf_certificado(certificado) -> str | None:
    if not certificado.archivo_pdf:
        return None
    try:
        name = str(certificado.archivo_pdf.name)
        if name.startswith('http'):
            return name
        # Keys directas en S3 (mismo patrón que imagen)
        if name.startswith(S3_CERT_PREFIX) or name.startswith('Certificados'):
            return url_publica_s3_key(name)
        return certificado.archivo_pdf.url
    except Exception:
        return url_publica_s3_key(str(certificado.archivo_pdf.name))


def _guardar_cert_s3(certificado, img_buffer, label=""):
    """
    Sube PNG (+ PDF derivado) a S3 via boto3 DIRECTO y actualiza el modelo.
    Retorna True si el PNG se guardó.
    """
    from io import BytesIO

    filename = f"certificado_{certificado.codigo_verificacion}.png"
    img_buffer.seek(0)
    raw = img_buffer.read()
    digest = hash_sha256_buffer(BytesIO(raw))
    s3_key, public_url = _subir_imagen_s3_directo(BytesIO(raw), filename)
    if not s3_key:
        return False

    certificado.archivo_imagen.name = s3_key
    certificado.hash_sha256 = digest
    org = organizacion_emisora_de(certificado)
    if org:
        certificado.organizacion_emisora = org[:200]

    try:
        pdf_buf = png_buffer_a_pdf(BytesIO(raw))
        pdf_name = f"certificado_{certificado.codigo_verificacion}.pdf"
        pdf_key, _ = _subir_bytes_s3_directo(pdf_buf, pdf_name, content_type='application/pdf')
        if pdf_key:
            certificado.archivo_pdf.name = pdf_key
        else:
            logger.warning('⚠️ PDF no subió a S3 para %s (PNG sí)', certificado.codigo_verificacion)
    except Exception as e:
        logger.warning('⚠️ No se pudo generar/subir PDF para %s: %s', certificado.codigo_verificacion, e)

    logger.info(f"✅ {label}: S3 key={s3_key}, URL={public_url}, hash={digest[:12]}…")
    return True


def asegurar_pdf_certificado(certificado) -> bool:
    """
    Si hay PNG en S3 y falta PDF/hash, regenera PDF (y hash) sin tocar el PNG.
    """
    if not certificado.archivo_imagen:
        return False
    if certificado.archivo_pdf and certificado.hash_sha256:
        return True

    from io import BytesIO

    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
    s3_key = str(certificado.archivo_imagen.name)
    try:
        s3 = _get_s3_client()
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
        raw = obj['Body'].read()
        buf = BytesIO(raw)
        if not certificado.hash_sha256:
            certificado.hash_sha256 = hash_sha256_buffer(buf)
        if not certificado.organizacion_emisora:
            certificado.organizacion_emisora = organizacion_emisora_de(certificado)[:200]
        if not certificado.archivo_pdf:
            pdf_buf = png_buffer_a_pdf(buf)
            pdf_name = f"certificado_{certificado.codigo_verificacion}.pdf"
            pdf_key, _ = _subir_bytes_s3_directo(pdf_buf, pdf_name, content_type='application/pdf')
            if pdf_key:
                certificado.archivo_pdf.name = pdf_key
        certificado.save(update_fields=[
            'hash_sha256', 'organizacion_emisora', 'archivo_pdf', 'actualizado_en',
        ])
        return bool(certificado.archivo_pdf)
    except Exception as e:
        logger.warning('asegurar_pdf_certificado falló (%s): %s', certificado.codigo_verificacion, e)
        return False


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
        fuente_nombre = ImageFont.truetype(os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 56)
        fuente_detalle = ImageFont.truetype(os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 30)
        fuente_fecha = ImageFont.truetype(os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 26)
    except (IOError, OSError):
        logger.warning("⚠️ Fuente GreatVibes no encontrada, usando default")
        fuente_nombre = ImageFont.load_default()
        fuente_detalle = ImageFont.load_default()
        fuente_fecha = fuente_detalle
    
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

    # Fecha de hoy centrada al 68%
    from django.utils import timezone as _tz
    fecha_txt = _tz.localdate().strftime('%d/%m/%Y')
    bbox_f = draw.textbbox((0, 0), fecha_txt, font=fuente_fecha)
    w_f = bbox_f[2] - bbox_f[0]
    draw.text(
        ((ancho - w_f) // 2, int(alto * 0.68)),
        fecha_txt, font=fuente_fecha, fill="black"
    )
    
    # QR en esquina inferior derecha
    try:
        import qrcode
        qr_img = qrcode.make(url_verificacion).resize((130, 130))
        plantilla.paste(qr_img, (ancho - 220, alto - 220))
    except Exception as qr_e:
        logger.warning(f"⚠️ No se pudo generar QR: {qr_e}")
    
    buf = BytesIO()
    plantilla.save(buf, format="PNG")
    buf.seek(0)
    logger.info(f"✅ Certificado SIMPLE generado para: {nombre_cap}")
    return buf


def resolver_plantilla_certificado(estudiante, curso, plantilla_id=None):
    """
    Elige la plantilla que se usará al generar el certificado.
    Prioridad: id explícito → curso+cliente → curso → cliente → por_defecto.
    """
    from .models_certificados import PlantillaCertificado

    if plantilla_id:
        p = PlantillaCertificado.objects.filter(pk=plantilla_id, activa=True).first()
        if p:
            return p, 'elegida_manual'

    cliente = getattr(estudiante, 'cliente', None) if estudiante else None
    if curso and cliente:
        p = PlantillaCertificado.objects.filter(
            curso=curso, cliente=cliente, activa=True,
        ).first()
        if p:
            return p, 'curso_y_cliente'

    if curso:
        p = PlantillaCertificado.objects.filter(curso=curso, activa=True).first()
        if p:
            return p, 'curso'

    if cliente:
        p = PlantillaCertificado.objects.filter(
            cliente=cliente, curso__isnull=True, activa=True,
        ).first()
        if p:
            return p, 'cliente'

    p = PlantillaCertificado.objects.filter(por_defecto=True, activa=True).first()
    if p:
        return p, 'por_defecto'

    return None, 'diseno_eki_default'


def plantillas_selectables_para_curso(cliente, curso):
    """Plantillas que el admin puede elegir para un curso presencial."""
    from .models_certificados import PlantillaCertificado
    from django.db.models import Q

    return list(
        PlantillaCertificado.objects.filter(activa=True).filter(
            Q(curso=curso)
            | Q(cliente=cliente, curso__isnull=True)
            | Q(por_defecto=True)
            | Q(cliente__isnull=True, curso__isnull=True)
        ).distinct().order_by('nombre')
    )


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
    
    GARANTÍA: Siempre genera archivo_imagen (PNG) para WhatsApp.
    Además genera PDF derivado + hash SHA-256 para verificación/descarga.
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
            asegurar_pdf_certificado(certificado)
            return True
        except Exception:
            logger.warning(f"⚠️ Certificado {certificado.codigo_verificacion} tenía imagen pero NO EXISTE en S3, regenerando...")
    
    try:
        from .models_certificados import PlantillaCertificado
        
        if not plantilla:
            plantilla, origen = resolver_plantilla_certificado(
                certificado.estudiante,
                certificado.curso,
            )
            logger.info(
                '📋 Plantilla certificado (%s): %s',
                origen,
                plantilla.nombre if plantilla else 'diseño eki por defecto',
            )
        
        url_verificacion = certificado.obtener_url_verificacion()
        org_nombre = organizacion_emisora_de(certificado)
        nombre_est = certificado.estudiante.nombre
        cedula_est = certificado.estudiante.cedula or ''
        
        generado = False
        modo = plantilla.modo_efectivo() if plantilla else 'imagen'

        # =====================================================
        # PRIORIDAD 0A: Diseño eki (colores, textos, fondo opcional)
        # =====================================================
        if not generado and plantilla and modo == 'diseno_eki':
            try:
                from .certificado_diseno_eki import generar_certificado_diseno_eki
                img_buffer = generar_certificado_diseno_eki(certificado, plantilla)
                if img_buffer:
                    generado = _guardar_cert_s3(certificado, img_buffer, 'P0 Diseño eki')
            except Exception as e:
                logger.warning(f'⚠️ Diseño eki falló ({e}), continuando...')

        # =====================================================
        # PRIORIDAD 0B: Marcadores RGB con plantilla de DB (modo imagen)
        # =====================================================
        plantilla_url_db = None
        if plantilla and modo == 'imagen':
            plantilla_url_db = plantilla.obtener_url_plantilla_imagen()
            if plantilla_url_db:
                logger.info(f"📋 Usando plantilla imagen: {plantilla_url_db}")

        if not generado and plantilla_url_db:
            try:
                from .utils_certificados import generar_certificado_marcadores
                img_buffer = generar_certificado_marcadores(
                    plantilla_url_o_path=plantilla_url_db,
                    nombre_estudiante=nombre_est,
                    cedula_estudiante=cedula_est,
                    url_verificacion=url_verificacion,
                    organizacion_nombre=org_nombre,
                    fecha_emision=getattr(certificado, 'fecha_emision', None)
                    or getattr(certificado, 'fecha_completado', None)
                    or timezone.localdate(),
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
                        fecha_emision=getattr(certificado, 'fecha_emision', None)
                        or getattr(certificado, 'fecha_completado', None)
                        or timezone.localdate(),
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


def _variables_plantilla_certificado(certificado) -> dict:
    """Variables típicas para plantillas Twilio ({{1}}, {{2}}, …)."""
    est = certificado.estudiante
    curso = certificado.curso
    return {
        '1': est.nombre or 'estudiante',
        '2': curso.nombre if curso else 'curso',
        '3': certificado.codigo_verificacion or '',
        '4': certificado.obtener_url_verificacion() or '',
    }


def _media_url_certificado(certificado) -> str | None:
    if certificado.archivo_imagen:
        media_url = obtener_url_certificado_twilio(certificado)
        if media_url:
            return media_url
        s3_key = str(certificado.archivo_imagen.name)
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
        return f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    if certificado.archivo_pdf:
        return certificado.archivo_pdf.url
    return None


def _enviar_whatsapp_con_reintentos(
    telefono: str,
    texto: str,
    *,
    media_url: str | None = None,
    pausa_inicial: float = 0.0,
) -> dict:
    """Reintenta envío de sesión (p. ej. imagen del diploma tras plantilla HSM)."""
    from .utils import enviar_whatsapp_twilio

    if pausa_inicial > 0:
        time.sleep(pausa_inicial)

    ultimo: dict = {'success': False, 'response': 'sin respuesta'}
    for intento in range(1, MAX_REINTENTOS_ENVIO_DIPLOMA + 1):
        ultimo = enviar_whatsapp_twilio(
            telefono=telefono,
            texto=texto,
            media_url=media_url,
        )
        if ultimo.get('success'):
            return ultimo
        detalle = str(ultimo.get('response', '')).lower()
        reintentar = any(x in detalle for x in ('63016', '63019', 'window', '24 hour', '24-hour', 'rate', 'media'))
        if intento < MAX_REINTENTOS_ENVIO_DIPLOMA and reintentar:
            time.sleep(2.0 * intento)
            continue
        break
    return ultimo


def _intentar_enviar_imagen_diploma(
    estudiante,
    certificado,
    *,
    caption: str,
    media_url: str,
    pausa_inicial: float,
) -> tuple[dict, str]:
    """Intenta enviar la imagen del diploma por sesión (con reintentos)."""
    resultado = _enviar_whatsapp_con_reintentos(
        estudiante.telefono,
        caption,
        media_url=media_url,
        pausa_inicial=pausa_inicial,
    )
    if resultado.get('success'):
        return resultado, 'imagen'
    logger.warning(
        '⚠️ Imagen diploma falló para %s: %s',
        certificado.codigo_verificacion,
        resultado.get('response'),
    )
    return resultado, 'fallo'


def _variables_plantilla_media_certificado(
    certificado,
    media_url: str,
    media_var_index: str = '1',
) -> dict:
    """
    Variables para plantilla de IMAGEN (header media + texto).
    Por defecto: {{1}} = URL imagen (header), {{2}} = nombre, {{3}} = curso, {{4}} = código.
    """
    est = certificado.estudiante
    curso = certificado.curso
    base = {
        media_var_index: media_url,
        '2': est.nombre or 'estudiante',
        '3': curso.nombre if curso else 'curso',
        '4': certificado.codigo_verificacion or '',
    }
    # Si el header usa otro índice, no pisar el {{1}} de texto del autor.
    base.setdefault('1', media_url)
    return base


def _enviar_plantilla_media_twilio(telefono: str, content_sid: str, variables: dict) -> dict:
    """Wrapper testeable para plantilla con imagen (header media)."""
    from .enviar_plantillas import enviar_plantilla_twilio

    return enviar_plantilla_twilio(telefono, content_sid, variables=variables)


def enviar_certificado_whatsapp(
    certificado,
    *,
    twilio_content_sid_media: str | None = None,
    media_var_index: str = '1',
    twilio_content_sid: str | None = None,
    template_variables: dict | None = None,
    tras_plantilla_previo: bool = False,
):
    """
    Envía el certificado por WhatsApp al estudiante.

    Prioridad de modos:
      0. twilio_content_sid_media → plantilla aprobada CON imagen en el header
         (la URL del PNG va como variable). UN solo mensaje business-initiated que
         entrega el diploma SIN que el estudiante responda. ← modo ideal.
      1. twilio_content_sid / tras_plantilla_previo → plantilla de texto + imagen de
         sesión (solo funciona si la ventana de 24 h está abierta).

    Returns:
        bool: True si se envió exitosamente
    """
    if not certificado.emitido or (not certificado.archivo_pdf and not certificado.archivo_imagen):
        logger.error(f"Certificado {certificado.codigo_verificacion} no está generado")
        return False

    try:
        estudiante = certificado.estudiante
        curso = certificado.curso
        media_url = _media_url_certificado(certificado)
        if not media_url:
            logger.error(f"Certificado {certificado.codigo_verificacion} no tiene archivo")
            return False

        verificacion_url = certificado.obtener_url_verificacion()
        mencion = certificado.obtener_mencion()
        calificacion = float(certificado.calificacion_final)
        vars_tpl = template_variables or _variables_plantilla_certificado(certificado)
        sid_media = (twilio_content_sid_media or '').strip()
        sid = (twilio_content_sid or '').strip()
        pausa = PAUSA_TRAS_PLANTILLA_SEG if tras_plantilla_previo else 0.0
        modo_envio = 'imagen'

        caption_corto = (
            f"🎓 *{estudiante.nombre}* — certificado *{curso.nombre}* "
            f"({calificacion}%). Código: `{certificado.codigo_verificacion}`"
        )
        if mencion:
            caption_corto += f"\n🏆 {mencion}"

        if sid_media:
            # MODO IDEAL: plantilla aprobada con imagen del certificado en el header.
            resultado = _enviar_plantilla_media_twilio(
                estudiante.telefono,
                sid_media,
                _variables_plantilla_media_certificado(
                    certificado, media_url, media_var_index,
                ),
            )
            modo_envio = 'plantilla_imagen'
        elif sid:
            from .enviar_plantillas import enviar_plantilla_twilio

            tpl_res = enviar_plantilla_twilio(
                estudiante.telefono,
                sid,
                variables=vars_tpl,
            )
            if not tpl_res.get('success'):
                logger.error(
                    "❌ Plantilla Twilio diploma falló para %s: %s",
                    certificado.codigo_verificacion,
                    tpl_res.get('response'),
                )
                return False
            resultado, modo_envio = _intentar_enviar_imagen_diploma(
                estudiante,
                certificado,
                caption=caption_corto,
                media_url=media_url,
                pausa_inicial=pausa or PAUSA_TRAS_PLANTILLA_SEG,
            )
        elif tras_plantilla_previo:
            resultado, modo_envio = _intentar_enviar_imagen_diploma(
                estudiante,
                certificado,
                caption=caption_corto,
                media_url=media_url,
                pausa_inicial=pausa,
            )
        else:
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

            resultado, modo_envio = _intentar_enviar_imagen_diploma(
                estudiante,
                certificado,
                caption=mensaje,
                media_url=media_url,
                pausa_inicial=0,
            )

        if resultado.get('success'):
            certificado.enviado_whatsapp = True
            certificado.fecha_envio = timezone.now()
            certificado.save(update_fields=['enviado_whatsapp', 'fecha_envio'])
            logger.info(
                "✅ Certificado %s enviado a %s (modo=%s, template_diploma=%s)",
                certificado.codigo_verificacion,
                estudiante.telefono,
                modo_envio,
                bool(sid),
            )
            return True

        logger.error(f"❌ Error enviando certificado: {resultado.get('response')}")
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
        'Puede seguir repasando el material escribiendo *listo*. '
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
    from django.urls import reverse
    
    try:
        certificado = Certificado.objects.select_related(
            'estudiante',
            'estudiante__cliente',
            'curso',
        ).get(
            codigo_verificacion__iexact=(codigo_verificacion or '').strip(),
            emitido=True,
        )

        if certificado.anulado:
            return {
                'valido': False,
                'anulado': True,
                'codigo': certificado.codigo_verificacion,
                'error': 'Certificado anulado',
                'motivo_anulacion': certificado.motivo_anulacion or '',
            }

        # Backfill PDF/hash si hace falta (best-effort; no bloquea verificación)
        try:
            asegurar_pdf_certificado(certificado)
            certificado.refresh_from_db()
        except Exception:
            pass

        pdf_url = obtener_url_pdf_certificado(certificado)
        imagen_url = (
            obtener_url_certificado_twilio(certificado)
            if certificado.archivo_imagen
            else None
        )
        # Enlace estable de descarga (vista Django) — siempre en certs emitidos
        try:
            descarga_path = reverse(
                'descargar_certificado',
                kwargs={'codigo_verificacion': certificado.codigo_verificacion},
            )
        except Exception:
            descarga_path = f"/descargar-certificado/{certificado.codigo_verificacion}/"

        org = (
            (certificado.organizacion_emisora or '').strip()
            or organizacion_emisora_de(certificado)
        )
        horas = certificado.horas_estimadas_curso()
        semanas = getattr(certificado.curso, 'duracion_semanas', None)

        return {
            'valido': True,
            'codigo': certificado.codigo_verificacion,
            'estudiante': certificado.estudiante.nombre,
            'cedula_enmascarada': certificado.cedula_enmascarada(),
            'curso': certificado.curso.nombre,
            'organizacion': org,
            'calificacion': float(certificado.calificacion_final),
            'mencion': certificado.obtener_mencion(),
            'fecha_inicio': certificado.fecha_inicio,
            'fecha_completado': certificado.fecha_completado,
            'fecha_emision': certificado.fecha_emision,
            'duracion_dias': certificado.duracion_curso(),
            'duracion_semanas': semanas,
            'horas_estimadas': horas,
            'hash_sha256': certificado.hash_sha256 or '',
            'pdf_url': pdf_url or descarga_path,
            'imagen_url': imagen_url,
            'descarga_url': descarga_path,
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
