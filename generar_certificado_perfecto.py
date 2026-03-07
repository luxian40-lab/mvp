"""
🎓 Generador de Certificados Perfecto — Prueba Local + S3
Usa marcadores de color puros para posicionar elementos dinámicamente.
Soporta modo local (guardar PNG) y modo S3 (BytesIO en RAM → S3 → presigned URL).

Marcadores de color:
  - Magenta (255, 0, 255) → Nombre
  - Rojo (255, 0, 0) → Cédula
  - Azul (0, 0, 255) → QR
  - Verde (0, 255, 0) → Empresa
  - Naranja (255, 128, 0) → Eki
Tolerancia: 0 (solo coincidencia exacta)
"""

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import qrcode
import requests
import io
import os

# --- CONFIGURACIÓN DE MARCADORES RGB ---
# ⚪ Gris (128,128,128) → Nombre del estudiante
# 🔴 Rojo (255,0,0) → Cédula (documento)
# 🔵 Azul (0,0,255) → Código QR de verificación
MARCADOR_NOMBRE  = (128, 128, 128)  # Gris puro para nombre
MARCADOR_CEDULA  = (255, 0, 0)      # Rojo puro para cédula
MARCADOR_QR      = (0, 0, 255)      # Azul puro para QR
MARCADOR_EMPRESA = (0, 255, 0)      # Verde puro para empresa (legacy)
MARCADOR_EKI     = (255, 128, 0)    # Naranja puro para Eki (legacy)
TOLERANCIA       = 30               # Tolerancia para JPEG (artefactos de compresión)


# --- PLANTILLA EN S3 ---
PLANTILLA_URL = "https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/certificadoeki.png"


def encontrar_marcador(np_img, color_objetivo, tolerancia=TOLERANCIA):
    """
    Busca un marcador de color en la imagen y devuelve su centro.
    
    Args:
        np_img: Array numpy de la imagen (H, W, 3)
        color_objetivo: Tupla RGB (R, G, B)
        tolerancia: Margen de error en cada canal (0 = exacto)
    
    Returns:
        tuple (x, y) del centro del marcador, o None si no se encuentra
    """
    mask = np.all(np.abs(np_img.astype(int) - np.array(color_objetivo)) <= tolerancia, axis=-1)
    coords = np.argwhere(mask)
    if coords.size == 0:
        return None
    y, x = coords.mean(axis=0)
    return int(x), int(y)


def generar_certificado_en_memoria(
    nombre_estudiante,
    cedula_estudiante,
    url_verificacion,
    organizacion_nombre="eki",
    eki_texto="EKI",
    plantilla_url=None,
    fuente_nombre_size=80,
    fuente_cedula_size=40,
    tamano_qr=200,
):
    """
    Genera un certificado en memoria (BytesIO) detectando marcadores de color.
    
    Returns:
        io.BytesIO: Buffer con la imagen PNG del certificado
    """
    url = plantilla_url or PLANTILLA_URL
    
    # 1. Descargar plantilla desde S3
    print(f"📥 Descargando plantilla: {url}")
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    plantilla = Image.open(io.BytesIO(response.content)).convert("RGB")
    ancho_img, alto_img = plantilla.size
    print(f"   Tamaño: {ancho_img}x{alto_img}")
    
    draw = ImageDraw.Draw(plantilla)
    
    # 2. Cargar fuentes
    try:
        fuente_nombre = ImageFont.truetype("GreatVibes-Regular.ttf", fuente_nombre_size)
        fuente_cedula = ImageFont.truetype("GreatVibes-Regular.ttf", fuente_cedula_size)
    except IOError:
        # Buscar en core/fonts/
        fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core', 'fonts')
        try:
            fuente_nombre = ImageFont.truetype(os.path.join(fonts_dir, "GreatVibes-Regular.ttf"), fuente_nombre_size)
            fuente_cedula = ImageFont.truetype(os.path.join(fonts_dir, "GreatVibes-Regular.ttf"), fuente_cedula_size)
        except IOError:
            print("⚠️ Fuente GreatVibes no encontrada, usando default.")
            fuente_nombre = ImageFont.load_default()
            fuente_cedula = ImageFont.load_default()
    
    # 3. Detectar marcadores RGB
    np_img = np.array(plantilla)
    
    pos_nombre  = encontrar_marcador(np_img, MARCADOR_NOMBRE)
    pos_cedula  = encontrar_marcador(np_img, MARCADOR_CEDULA)
    pos_qr      = encontrar_marcador(np_img, MARCADOR_QR)
    pos_empresa = encontrar_marcador(np_img, MARCADOR_EMPRESA)
    pos_eki     = encontrar_marcador(np_img, MARCADOR_EKI)
    
    # Resumen de detección
    marcadores = {
        'Nombre (Magenta)': pos_nombre,
        'Cédula (Rojo)': pos_cedula,
        'QR (Azul)': pos_qr,
        'Empresa (Verde)': pos_empresa,
        'Eki (Naranja)': pos_eki,
    }
    for nombre_m, pos in marcadores.items():
        if pos:
            print(f"   ✅ {nombre_m}: ({pos[0]}, {pos[1]})")
        else:
            print(f"   ❌ {nombre_m}: NO ENCONTRADO")
    
    # Validar marcadores obligatorios
    if pos_nombre is None:
        raise ValueError("No se encontró el marcador de NOMBRE (Magenta 255,0,255)")
    if pos_cedula is None:
        raise ValueError("No se encontró el marcador de CÉDULA (Rojo 255,0,0)")
    if pos_qr is None:
        raise ValueError("No se encontró el marcador de QR (Azul 0,0,255)")
    
    # 4. Borrar todos los marcadores encontrados (reemplazar con fondo local)
    todos_marcadores = [pos_nombre, pos_cedula, pos_qr, pos_empresa, pos_eki]
    for pos in todos_marcadores:
        if pos is not None:
            x, y = pos
            # Tomar color de fondo cercano
            safe_y = min(y + 20, alto_img - 1)
            safe_x = min(x + 20, ancho_img - 1)
            color_fondo = plantilla.getpixel((safe_x, safe_y))
            draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=color_fondo)
    
    # 5. Estampar NOMBRE (centrado en el marcador)
    nombre_capitalizado = nombre_estudiante.strip().title()
    caja = draw.textbbox((0, 0), nombre_capitalizado, font=fuente_nombre)
    ancho_t = caja[2] - caja[0]
    alto_t = caja[3] - caja[1]
    draw.text(
        (pos_nombre[0] - ancho_t // 2, pos_nombre[1] - alto_t // 2),
        nombre_capitalizado, font=fuente_nombre, fill="black"
    )
    
    # 6. Estampar CÉDULA (centrada)
    texto_cedula = str(cedula_estudiante)
    caja = draw.textbbox((0, 0), texto_cedula, font=fuente_cedula)
    ancho_t = caja[2] - caja[0]
    alto_t = caja[3] - caja[1]
    draw.text(
        (pos_cedula[0] - ancho_t // 2, pos_cedula[1] - alto_t // 2),
        texto_cedula, font=fuente_cedula, fill="black"
    )
    
    # 7. Estampar EMPRESA (si marcador encontrado)
    if pos_empresa and organizacion_nombre:
        caja = draw.textbbox((0, 0), organizacion_nombre, font=fuente_cedula)
        ancho_t = caja[2] - caja[0]
        alto_t = caja[3] - caja[1]
        draw.text(
            (pos_empresa[0] - ancho_t // 2, pos_empresa[1] - alto_t // 2),
            organizacion_nombre, font=fuente_cedula, fill="black"
        )
    
    # 8. Estampar EKI (si marcador encontrado)
    if pos_eki and eki_texto:
        caja = draw.textbbox((0, 0), eki_texto, font=fuente_cedula)
        ancho_t = caja[2] - caja[0]
        alto_t = caja[3] - caja[1]
        draw.text(
            (pos_eki[0] - ancho_t // 2, pos_eki[1] - alto_t // 2),
            eki_texto, font=fuente_cedula, fill="black"
        )
    
    # 9. Generar y pegar QR (centrado en el marcador)
    qr_img = qrcode.make(url_verificacion)
    qr_img = qr_img.resize((tamano_qr, tamano_qr))
    x_qr = pos_qr[0] - tamano_qr // 2
    y_qr = pos_qr[1] - tamano_qr // 2
    plantilla.paste(qr_img, (int(x_qr), int(y_qr)))
    
    # 10. Guardar en buffer (RAM — no disco)
    buffer_memoria = io.BytesIO()
    plantilla.save(buffer_memoria, format="PNG")
    buffer_memoria.seek(0)
    
    print(f"✅ Certificado generado en memoria para: {nombre_capitalizado}")
    return buffer_memoria


def subir_a_s3(buffer, cedula, bucket='eki-produccion', region='us-east-2'):
    """
    Sube el certificado desde RAM a S3 y devuelve presigned URL.
    
    Args:
        buffer: BytesIO con la imagen PNG
        cedula: Cédula del estudiante (para nombre del archivo)
        bucket: Nombre del bucket S3
        region: Región de AWS
    
    Returns:
        str: Presigned URL válida por 1 hora
    """
    import boto3
    
    s3_client = boto3.client(
        's3',
        region_name=region,
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    )
    
    nombre_archivo_s3 = f"certificados_generados/certificado_{cedula}.png"
    
    buffer.seek(0)
    s3_client.upload_fileobj(
        buffer,
        bucket,
        nombre_archivo_s3,
        ExtraArgs={'ContentType': 'image/png'}
    )
    
    print(f"✅ Certificado subido a S3: {nombre_archivo_s3}")
    
    # Generar presigned URL válida por 1 hora
    url_firmada = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': nombre_archivo_s3},
        ExpiresIn=3600
    )
    
    return url_firmada


# ============================================================
# PRUEBA LOCAL
# ============================================================
if __name__ == "__main__":
    personas = [
        {"nombre": "Julian Ramirez", "cedula": "1014310196", "qr": "https://landingcertificados.netlify.app/"},
        {"nombre": "Andres Rubiano", "cedula": "1231231", "qr": "https://landingcertificados.netlify.app/"},
        {"nombre": "Luisa Salazar", "cedula": "1283182381", "qr": "https://landingcertificados.netlify.app/"},
        {"nombre": "Andrea Ramos", "cedula": "73288123", "qr": "https://landingcertificados.netlify.app/"},
        {"nombre": "Juliana Rodriguez", "cedula": "21838123", "qr": "https://landingcertificados.netlify.app/"},
    ]
    
    local_dir = r"C:\Users\luxia\OneDrive\Escritorio\PY"
    os.makedirs(local_dir, exist_ok=True)
    
    for persona in personas:
        try:
            buffer = generar_certificado_en_memoria(
                nombre_estudiante=persona["nombre"],
                cedula_estudiante=persona["cedula"],
                url_verificacion=persona["qr"],
                organizacion_nombre="eki",
                eki_texto="EKI",
            )
            
            # Guardar localmente para prueba visual
            nombre_archivo = f"certificado_{persona['nombre'].replace(' ', '_').lower()}.png"
            ruta_completa = os.path.join(local_dir, nombre_archivo)
            with open(ruta_completa, 'wb') as f:
                f.write(buffer.read())
            print(f"💾 Guardado local: {ruta_completa}")
            
            # --- Descomentar para subir a S3 ---
            # from dotenv import load_dotenv
            # load_dotenv()
            # buffer.seek(0)
            # url = subir_a_s3(buffer, persona["cedula"])
            # print(f"🌐 URL firmada: {url}")
            
        except Exception as e:
            print(f"❌ Error con {persona['nombre']}: {e}")
        
        print("─" * 50)
