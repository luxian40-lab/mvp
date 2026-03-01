"""
🎓 Generador de Certificados con Detección de Marcadores Visuales (RGB)
Usa numpy + Pillow para detectar marcadores de color en la plantilla
y posicionar dinámicamente: Nombre, Cédula y QR.

Adaptado para Django + AWS S3 (sin guardar en disco local).
"""

import os
import logging
import requests
import numpy as np
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE MARCADORES RGB ---
MARCADOR_NOMBRE = (128, 128, 128)   # Gris para nombre
MARCADOR_CEDULA = (255, 0, 0)       # Rojo puro para cédula
MARCADOR_QR = (0, 0, 255)           # Azul puro para QR
TOLERANCIA_COLOR = 8                # Tolerancia para detección de marcadores

# --- RUTA DE FUENTES ---
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')


def encontrar_marcador(np_img, color_objetivo, tolerancia=TOLERANCIA_COLOR):
    """
    Busca un marcador de color en la imagen y devuelve su centro.
    
    Args:
        np_img: Array numpy de la imagen (H, W, 3)
        color_objetivo: Tupla RGB (R, G, B)
        tolerancia: Margen de error en cada canal
    
    Returns:
        tuple (x, y) del centro del marcador, o None si no se encuentra
    """
    mask = np.all(np.abs(np_img.astype(int) - np.array(color_objetivo)) <= tolerancia, axis=-1)
    coords = np.argwhere(mask)
    if coords.size == 0:
        return None
    y, x = coords.mean(axis=0)
    return int(x), int(y)


def cargar_fuente(nombre_fuente='GreatVibes-Regular.ttf', tamaño=80):
    """
    Carga una fuente TTF desde la carpeta core/fonts/.
    Si no se encuentra, usa la fuente por defecto de Pillow.
    """
    ruta_fuente = os.path.join(FONTS_DIR, nombre_fuente)
    try:
        return ImageFont.truetype(ruta_fuente, tamaño)
    except (IOError, OSError):
        logger.warning(f"⚠️ Fuente '{nombre_fuente}' no encontrada en {FONTS_DIR}. Usando fuente por defecto.")
        return ImageFont.load_default()


def generar_certificado_marcadores(
    plantilla_url_o_path,
    nombre_estudiante,
    cedula_estudiante,
    url_verificacion,
    organizacion_nombre=None,
    fuente_nombre_size=80,
    fuente_cedula_size=40,
    tamaño_qr=200,
    ajuste_qr_y=-40,
):
    """
    Genera un certificado usando detección de marcadores de color.
    
    Args:
        plantilla_url_o_path: URL de S3 o path local a la imagen plantilla
        nombre_estudiante: Nombre del estudiante (se capitaliza)
        cedula_estudiante: Número de documento
        url_verificacion: URL para el código QR
        organizacion_nombre: Nombre de la organización (opcional)
        fuente_nombre_size: Tamaño de fuente para el nombre
        fuente_cedula_size: Tamaño de fuente para la cédula
        tamaño_qr: Tamaño del QR en píxeles
        ajuste_qr_y: Ajuste vertical del QR respecto al marcador
    
    Returns:
        BytesIO: Buffer con la imagen PNG del certificado
    """
    # 1. Cargar plantilla (desde URL o archivo local)
    if plantilla_url_o_path.startswith('http'):
        response = requests.get(plantilla_url_o_path, timeout=15)
        response.raise_for_status()
        plantilla = Image.open(BytesIO(response.content)).convert("RGB")
    else:
        plantilla = Image.open(plantilla_url_o_path).convert("RGB")
    
    ancho_img, alto_img = plantilla.size
    draw = ImageDraw.Draw(plantilla)
    
    # 2. Cargar fuentes
    fuente_nombre = cargar_fuente('GreatVibes-Regular.ttf', fuente_nombre_size)
    fuente_cedula = cargar_fuente('GreatVibes-Regular.ttf', fuente_cedula_size)
    
    # 3. Detectar marcadores RGB
    np_img = np.array(plantilla)
    
    pos_nombre = encontrar_marcador(np_img, MARCADOR_NOMBRE)
    pos_cedula = encontrar_marcador(np_img, MARCADOR_CEDULA)
    pos_qr = encontrar_marcador(np_img, MARCADOR_QR)
    
    if pos_nombre is None:
        raise ValueError("No se encontró el marcador de NOMBRE (gris RGB 128,128,128) en la plantilla.")
    if pos_cedula is None:
        raise ValueError("No se encontró el marcador de CÉDULA (rojo RGB 255,0,0) en la plantilla.")
    if pos_qr is None:
        raise ValueError("No se encontró el marcador de QR (azul RGB 0,0,255) en la plantilla.")
    
    logger.info(f"📍 Marcadores detectados - Nombre: {pos_nombre}, Cédula: {pos_cedula}, QR: {pos_qr}")
    
    # 4. Borrar marcadores (reemplazar con color local del fondo)
    for pos in [pos_nombre, pos_cedula, pos_qr]:
        x, y = pos
        # Tomar el color del pixel cercano como fondo
        color_fondo = plantilla.getpixel((x, min(y + 20, alto_img - 1)))
        draw.ellipse([x - 10, y - 10, x + 10, y + 10], fill=color_fondo)
    
    # 5. Estampar NOMBRE (centrado en el marcador)
    nombre_capitalizado = nombre_estudiante.strip().title()
    caja_nombre = draw.textbbox((0, 0), nombre_capitalizado, font=fuente_nombre)
    ancho_nombre = caja_nombre[2] - caja_nombre[0]
    alto_nombre = caja_nombre[3] - caja_nombre[1]
    draw.text(
        (pos_nombre[0] - ancho_nombre // 2, pos_nombre[1] - alto_nombre // 2),
        nombre_capitalizado,
        font=fuente_nombre,
        fill="black"
    )
    
    # 6. Estampar CÉDULA (centrada en el marcador)
    texto_cedula = str(cedula_estudiante)
    caja_cedula = draw.textbbox((0, 0), texto_cedula, font=fuente_cedula)
    ancho_cedula = caja_cedula[2] - caja_cedula[0]
    alto_cedula = caja_cedula[3] - caja_cedula[1]
    draw.text(
        (pos_cedula[0] - ancho_cedula // 2, pos_cedula[1] - alto_cedula // 2),
        texto_cedula,
        font=fuente_cedula,
        fill="black"
    )
    
    # 7. Generar y pegar QR (centrado en el marcador con ajuste)
    qr_img = qrcode.make(url_verificacion)
    qr_img = qr_img.resize((tamaño_qr, tamaño_qr))
    x_qr = pos_qr[0] - tamaño_qr // 2
    y_qr = pos_qr[1] - tamaño_qr // 2 + ajuste_qr_y
    plantilla.paste(qr_img, (int(x_qr), int(y_qr)))
    
    # 8. Guardar en buffer (RAM, no disco)
    buffer = BytesIO()
    plantilla.save(buffer, format="PNG")
    buffer.seek(0)
    
    logger.info(f"✅ Certificado generado para: {nombre_capitalizado}")
    return buffer


def subir_certificado_s3(buffer, organizacion_slug, cedula, curso_id):
    """
    Sube el certificado generado a AWS S3.
    
    Args:
        buffer: BytesIO con la imagen PNG
        organizacion_slug: Nombre de la organización (slugificado)
        cedula: Cédula del estudiante
        curso_id: ID del curso
    
    Returns:
        str: URL del certificado en S3
    """
    import boto3
    from botocore.config import Config
    from django.utils.text import slugify
    
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
    region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-2')
    
    org_slug = slugify(organizacion_slug or 'eki')
    key = f"certificados/{org_slug}/{cedula}_{curso_id}.png"
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
        aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
        config=Config(signature_version='s3v4', region_name=region)
    )
    
    buffer.seek(0)
    s3_client.upload_fileobj(
        buffer,
        bucket,
        key,
        ExtraArgs={
            'ContentType': 'image/png',
            'ACL': 'public-read'
        }
    )
    
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    logger.info(f"✅ Certificado subido a S3: {url}")
    return url


def generar_y_subir_certificado(estudiante, curso, plantilla_url=None, url_verificacion=None):
    """
    Función principal: genera certificado con marcadores y lo sube a S3.
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso
        plantilla_url: URL de la plantilla en S3 (opcional, usa default)
        url_verificacion: URL para el QR (se genera automáticamente si no se pasa)
    
    Returns:
        str: URL del certificado en S3
    """
    from .models_certificados import Certificado
    
    # URL de plantilla por defecto
    if not plantilla_url:
        plantilla_url = "https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/prueba_certificado.png"
    
    # Generar URL de verificación
    if not url_verificacion:
        try:
            cert = Certificado.objects.filter(
                estudiante=estudiante,
                curso=curso
            ).first()
            if cert:
                url_verificacion = f"https://www.eki.com.co/verificar-certificado/{cert.codigo_verificacion}/"
            else:
                url_verificacion = "https://www.eki.com.co/"
        except Exception:
            url_verificacion = "https://www.eki.com.co/"
    
    org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'Eki'
    
    # Generar imagen del certificado
    buffer = generar_certificado_marcadores(
        plantilla_url_o_path=plantilla_url,
        nombre_estudiante=estudiante.nombre,
        cedula_estudiante=estudiante.cedula,
        url_verificacion=url_verificacion,
        organizacion_nombre=org_nombre,
    )
    
    # Subir a S3
    url_s3 = subir_certificado_s3(
        buffer=buffer,
        organizacion_slug=org_nombre,
        cedula=estudiante.cedula,
        curso_id=curso.id
    )
    
    return url_s3
