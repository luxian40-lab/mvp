"""
🎓 Generador de Certificados con Detección de Marcadores Visuales (RGB)
Usa numpy + Pillow para detectar marcadores de color en la plantilla
y posicionar dinámicamente: Nombre, Cédula, Fecha (opcional) y QR.

Marcadores de color:
  - ⚪ Gris (128, 128, 128) → Nombre del estudiante
  - 🔴 Rojo (255, 0, 0) → Cédula (documento)
  - 🟡 Amarillo (255, 255, 0) → Fecha de emisión (opcional)
  - 🔵 Azul (0, 0, 255) → Código QR de verificación

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
from django.utils import timezone

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE MARCADORES RGB ---
# ⚪ Gris (128,128,128) → Nombre del estudiante
# 🔴 Rojo (255,0,0) → Cédula (documento)
# 🟡 Amarillo (255,255,0) → Fecha de emisión (opcional)
# 🔵 Azul (0,0,255) → Código QR de verificación
MARCADOR_NOMBRE  = (128, 128, 128)  # Gris puro para nombre
MARCADOR_CEDULA  = (255, 0, 0)      # Rojo puro para cédula
MARCADOR_FECHA   = (255, 255, 0)    # Amarillo puro para fecha
MARCADOR_QR      = (0, 0, 255)      # Azul puro para QR
TOLERANCIA_COLOR = 18               # Tolerancia reducida para detectar solo marcadores puros
TAMAÑO_QR_DEFAULT = 130             # Antes 190; más compacto en plantillas
FUENTE_NOMBRE_DEFAULT = 56          # Antes 80; nombres largos caben mejor
FUENTE_CEDULA_DEFAULT = 33          # +3 px (antes 30; histórico 40)
FUENTE_FECHA_DEFAULT = 29           # +3 px (antes 26)

# --- RUTA DE FUENTES ---
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')


def encontrar_marcador(np_img, color_objetivo, tolerancia=TOLERANCIA_COLOR):
    """
    Busca un marcador de color en la imagen y devuelve su centro.
    Usa subdivisión en bloques + densidad local para aislar el marcador
    real del ruido JPEG disperso, SIN depender de scipy.
    
    Algoritmo:
    1. Detecta todos los pixeles que coinciden con el color ± tolerancia
    2. Divide la imagen en bloques de 30×30 px
    3. Cuenta pixeles coincidentes por bloque
    4. El bloque con más pixeles = zona del marcador real
    5. Toma todos los pixeles en un radio de 30px del centro de ese bloque
    6. Devuelve la mediana de esos pixeles como centro del marcador
    
    Esto resiste ruido JPEG disperso (1-2 px por bloque) y encuentra
    el marcador concentrado (decenas de px en un bloque).
    
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
    
    total_px = len(coords)
    
    # Si hay pocos pixeles (< 50), es un marcador puro sin ruido → mediana simple
    if total_px < 50:
        y_med = int(np.median(coords[:, 0]))
        x_med = int(np.median(coords[:, 1]))
        logger.info(f"🔍 Marcador {color_objetivo}: {total_px} px, directo mediana=({x_med},{y_med})")
        return x_med, y_med
    
    # Muchos pixeles → hay ruido JPEG. Usar subdivisión en bloques para encontrar
    # la zona de mayor densidad (= el marcador real)
    BLOCK_SIZE = 30
    h, w = np_img.shape[:2]
    rows_blocks = (h + BLOCK_SIZE - 1) // BLOCK_SIZE
    cols_blocks = (w + BLOCK_SIZE - 1) // BLOCK_SIZE
    
    # Contar pixeles por bloque usando vectorización
    block_y = coords[:, 0] // BLOCK_SIZE
    block_x = coords[:, 1] // BLOCK_SIZE
    block_ids = block_y * cols_blocks + block_x
    
    # Encontrar el bloque con más pixeles
    unique_blocks, counts = np.unique(block_ids, return_counts=True)
    best_idx = np.argmax(counts)
    best_block_id = unique_blocks[best_idx]
    best_count = counts[best_idx]
    
    # Centro del bloque ganador
    best_by = (best_block_id // cols_blocks) * BLOCK_SIZE + BLOCK_SIZE // 2
    best_bx = (best_block_id % cols_blocks) * BLOCK_SIZE + BLOCK_SIZE // 2
    
    # Tomar pixeles en un radio de 30px alrededor del centro del bloque ganador
    RADIO = 30
    dist_y = np.abs(coords[:, 0] - best_by)
    dist_x = np.abs(coords[:, 1] - best_bx)
    nearby = (dist_y <= RADIO) & (dist_x <= RADIO)
    cluster_coords = coords[nearby]
    
    if len(cluster_coords) < 3:
        # Fallback: mediana global
        y_med = int(np.median(coords[:, 0]))
        x_med = int(np.median(coords[:, 1]))
        logger.info(f"🔍 Marcador {color_objetivo}: {total_px} px, fallback mediana=({x_med},{y_med})")
        return x_med, y_med
    
    y_med = int(np.median(cluster_coords[:, 0]))
    x_med = int(np.median(cluster_coords[:, 1]))
    logger.info(f"🔍 Marcador {color_objetivo}: {total_px} px total, cluster={len(cluster_coords)} px en bloque, centro=({x_med},{y_med})")
    return x_med, y_med


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
    plantilla_url_o_path=None,
    *,
    plantilla_bytes=None,
    nombre_estudiante,
    cedula_estudiante,
    url_verificacion,
    organizacion_nombre=None,
    fecha_emision=None,
    fuente_nombre_size=FUENTE_NOMBRE_DEFAULT,
    fuente_cedula_size=FUENTE_CEDULA_DEFAULT,
    fuente_fecha_size=FUENTE_FECHA_DEFAULT,
    tamaño_qr=TAMAÑO_QR_DEFAULT,
    ajuste_qr_y=20,
):
    """
    Genera un certificado usando detección de marcadores de color.
    
    Args:
        plantilla_url_o_path: URL de S3 o path local a la imagen plantilla
        nombre_estudiante: Nombre del estudiante (se capitaliza)
        cedula_estudiante: Número de documento
        url_verificacion: URL para el código QR
        organizacion_nombre: Nombre de la organización (opcional)
        fecha_emision: Fecha a estampar si hay marcador amarillo (default: hoy)
        fuente_nombre_size: Tamaño de fuente para el nombre
        fuente_cedula_size: Tamaño de fuente para la cédula
        fuente_fecha_size: Tamaño de fuente para la fecha
        tamaño_qr: Tamaño del QR en píxeles
        ajuste_qr_y: Ajuste vertical del QR respecto al marcador
    
    Returns:
        BytesIO: Buffer con la imagen PNG del certificado
    """
    # 1. Cargar plantilla (bytes en memoria, URL o archivo local)
    if plantilla_bytes:
        plantilla = Image.open(BytesIO(plantilla_bytes)).convert("RGB")
    elif plantilla_url_o_path and str(plantilla_url_o_path).startswith('http'):
        response = requests.get(plantilla_url_o_path, timeout=15)
        response.raise_for_status()
        plantilla = Image.open(BytesIO(response.content)).convert("RGB")
    elif plantilla_url_o_path:
        plantilla = Image.open(plantilla_url_o_path).convert("RGB")
    else:
        raise ValueError("Debe indicar plantilla_bytes o plantilla_url_o_path")
    
    ancho_img, alto_img = plantilla.size
    draw = ImageDraw.Draw(plantilla)
    
    # 2. Cargar fuentes
    fuente_nombre = cargar_fuente('GreatVibes-Regular.ttf', fuente_nombre_size)
    fuente_cedula = cargar_fuente('GreatVibes-Regular.ttf', fuente_cedula_size)
    fuente_fecha = cargar_fuente('GreatVibes-Regular.ttf', fuente_fecha_size)
    
    # 3. Detectar marcadores RGB
    np_img = np.array(plantilla)
    
    pos_nombre = encontrar_marcador(np_img, MARCADOR_NOMBRE)
    pos_cedula = encontrar_marcador(np_img, MARCADOR_CEDULA)
    pos_fecha = encontrar_marcador(np_img, MARCADOR_FECHA)
    pos_qr = encontrar_marcador(np_img, MARCADOR_QR)
    
    if pos_nombre is None:
        raise ValueError("No se encontró el marcador de NOMBRE (Gris RGB 128,128,128) en la plantilla.")
    if pos_cedula is None:
        raise ValueError("No se encontró el marcador de CÉDULA (Rojo RGB 255,0,0) en la plantilla.")
    if pos_qr is None:
        raise ValueError("No se encontró el marcador de QR (Azul RGB 0,0,255) en la plantilla.")
    
    logger.info(
        f"📍 Marcadores detectados - Nombre: {pos_nombre}, Cédula: {pos_cedula}, "
        f"Fecha: {pos_fecha}, QR: {pos_qr}"
    )
    
    # 4. Borrar marcadores (reemplazar con color local del fondo)
    todos_marcadores = [pos_nombre, pos_cedula, pos_fecha, pos_qr]
    for pos in todos_marcadores:
        if pos is not None:
            x, y = pos
            # Tomar el color del pixel cercano como fondo
            color_fondo = plantilla.getpixel((max(x - 25, 0), min(y + 25, alto_img - 1)))
            # Radio grande (20px) para borrar completamente el marcador
            draw.ellipse([x - 20, y - 20, x + 20, y + 20], fill=color_fondo)
    
    # 5. Estampar NOMBRE (centrado horizontalmente, baseline en el marcador)
    nombre_capitalizado = nombre_estudiante.strip().title()
    draw.text(
        (pos_nombre[0], pos_nombre[1]),
        nombre_capitalizado,
        font=fuente_nombre,
        fill="black",
        anchor="ms"  # Middle-baseline: centra horizontal, baseline en el marcador (nombre "se sienta" sobre la línea)
    )
    logger.info(f"📝 Nombre '{nombre_capitalizado}' estampado en ({pos_nombre[0]}, {pos_nombre[1]}) con anchor=ms, font_size={fuente_nombre_size}")
    
    # 6. Estampar CÉDULA (centrada horizontalmente, baseline en el marcador)
    texto_cedula = str(cedula_estudiante)
    draw.text(
        (pos_cedula[0], pos_cedula[1]),
        texto_cedula,
        font=fuente_cedula,
        fill="black",
        anchor="ms"  # Middle-baseline: centra horizontal, baseline en el marcador
    )

    # 6b. Estampar FECHA si hay marcador amarillo (hoy por defecto)
    if pos_fecha is not None:
        if not fecha_emision:
            fecha_emision = timezone.localdate()
        if hasattr(fecha_emision, 'strftime'):
            texto_fecha = fecha_emision.strftime('%d/%m/%Y')
        else:
            texto_fecha = str(fecha_emision)
        draw.text(
            (pos_fecha[0], pos_fecha[1]),
            texto_fecha,
            font=fuente_fecha,
            fill="black",
            anchor="ms",
        )
        logger.info(
            f"📅 Fecha '{texto_fecha}' estampada en ({pos_fecha[0]}, {pos_fecha[1]}) "
            f"font_size={fuente_fecha_size}"
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
        plantilla_url = "https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/certificadoeki.png"
    
    # Generar URL de verificación
    if not url_verificacion:
        try:
            cert = Certificado.objects.filter(
                estudiante=estudiante,
                curso=curso
            ).first()
            if cert:
                url_verificacion = cert.obtener_url_verificacion()
            else:
                base = getattr(
                    settings,
                    'CERTIFICADO_VERIFICACION_BASE_URL',
                    'https://certificados.eki.technology',
                ).rstrip('/')
                url_verificacion = f"{base}/verificar/"
        except Exception:
            base = getattr(
                settings,
                'CERTIFICADO_VERIFICACION_BASE_URL',
                'https://certificados.eki.technology',
            ).rstrip('/')
            url_verificacion = f"{base}/verificar/"
    
    org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
    
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
