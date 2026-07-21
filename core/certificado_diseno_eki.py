"""Generación y vista previa de certificados con diseño eki (Pillow)."""

from __future__ import annotations

import logging
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

ANCHO = 1200
ALTO = 848
NOMBRE_DEMO = 'MARÍA GONZÁLEZ PÉREZ'
CURSO_DEMO = 'Curso de demostración eki'


def _hex_a_rgb(hex_color: str, default=(44, 62, 80)) -> tuple[int, int, int]:
    raw = (hex_color or '').strip().lstrip('#')
    if len(raw) != 6:
        return default
    try:
        return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default


def _abrir_imagen_campo(file_field):
    if not file_field:
        return None
    try:
        with file_field.open('rb') as fh:
            img = Image.open(fh).copy()
        if img.mode in ('RGBA', 'P', 'LA'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img)
            return bg
        if img.mode != 'RGB':
            return img.convert('RGB')
        return img
    except Exception as exc:
        logger.warning('No se pudo abrir imagen de plantilla: %s', exc)
        return None


def _cargar_fuentes():
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    candidatas = [
        (os.path.join(fonts_dir, 'GreatVibes-Regular.ttf'), 56, 28, 22, 18),
        ('arial.ttf', 42, 22, 18, 14),
        ('C:\\Windows\\Fonts\\arial.ttf', 42, 22, 18, 14),
        ('C:\\Windows\\Fonts\\arialbd.ttf', 42, 22, 18, 14),
    ]
    for path, s1, s2, s3, s4 in candidatas:
        try:
            return (
                ImageFont.truetype(path, s1),
                ImageFont.truetype(path, s2),
                ImageFont.truetype(path, s3),
                ImageFont.truetype(path, s4),
            )
        except (IOError, OSError):
            continue
    default = ImageFont.load_default()
    return default, default, default, default


def _texto_centrado(draw, y, texto, font, fill, ancho=ANCHO):
    if not texto:
        return
    bbox = draw.textbbox((0, 0), texto, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((ancho - w) // 2, y), texto, font=font, fill=fill)


def render_certificado_diseno_eki(
    *,
    plantilla=None,
    nombre_estudiante=NOMBRE_DEMO,
    curso_nombre=CURSO_DEMO,
    calificacion_final=95,
    codigo_verificacion='DEMO-0001',
    url_verificacion='https://admin.eki.technology/verificar-certificado/DEMO/',
    fecha_emision=None,
) -> BytesIO:
    """Renderiza certificado PNG con colores/textos/fondo del diseño eki."""
    from django.utils import timezone

    color_primario = _hex_a_rgb(getattr(plantilla, 'color_primario', None), (44, 62, 80))
    color_secundario = _hex_a_rgb(getattr(plantilla, 'color_secundario', None), (52, 152, 219))
    texto_superior = (getattr(plantilla, 'texto_superior', None) or 'eki - Soluciones Educativas').strip()
    texto_certificado = (getattr(plantilla, 'texto_certificado', None) or 'CERTIFICADO DE FINALIZACIÓN').strip()

    fondo = _abrir_imagen_campo(getattr(plantilla, 'imagen_fondo', None) if plantilla else None)
    if fondo:
        img = fondo.resize((ANCHO, ALTO), Image.Resampling.LANCZOS)
    else:
        img = Image.new('RGB', (ANCHO, ALTO), (255, 255, 255))
        draw_bg = ImageDraw.Draw(img)
        margin = 36
        draw_bg.rectangle(
            (margin, margin, ANCHO - margin, ALTO - margin),
            outline=color_primario,
            width=4,
        )
        draw_bg.rectangle(
            (margin + 10, margin + 10, ANCHO - margin - 10, ALTO - margin - 10),
            outline=color_secundario,
            width=2,
        )

    draw = ImageDraw.Draw(img)
    font_titulo, font_nombre, font_medio, font_peq = _cargar_fuentes()

    logo = _abrir_imagen_campo(getattr(plantilla, 'logo_institucion', None) if plantilla else None)
    if logo:
        logo.thumbnail((140, 140), Image.Resampling.LANCZOS)
        img.paste(logo, ((ANCHO - logo.width) // 2, 42))

    _texto_centrado(draw, 170, texto_superior, font_medio, color_primario)
    _texto_centrado(draw, 230, texto_certificado, font_titulo, color_secundario)
    draw.line((220, 290, ANCHO - 220, 290), fill=color_secundario, width=3)

    _texto_centrado(draw, 330, 'Se otorga el presente certificado a', font_peq, (30, 30, 30))
    _texto_centrado(draw, 380, (nombre_estudiante or NOMBRE_DEMO).upper(), font_nombre, color_primario)
    _texto_centrado(draw, 470, 'Por haber completado satisfactoriamente el curso', font_peq, (30, 30, 30))
    _texto_centrado(draw, 520, curso_nombre or CURSO_DEMO, font_medio, color_secundario)
    _texto_centrado(draw, 590, f'Calificación final: {calificacion_final}%', font_peq, (30, 30, 30))

    if not fecha_emision:
        fecha_emision = timezone.localdate()
    if hasattr(fecha_emision, 'strftime'):
        fecha_txt = fecha_emision.strftime('%d/%m/%Y')
    else:
        fecha_txt = str(fecha_emision)
    _texto_centrado(draw, 640, f'Fecha de emisión: {fecha_txt}', font_peq, (80, 80, 80))

    codigo = f'Código: {codigo_verificacion}'
    bbox = draw.textbbox((0, 0), codigo, font=font_peq)
    draw.text((48, ALTO - 56), codigo, font=font_peq, fill=(120, 120, 120))

    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(url_verificacion or 'https://admin.eki.technology/verificar/')
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='black', back_color='white').resize((110, 110))
        img.paste(qr_img, (ANCHO - 150, ALTO - 150))
    except Exception as exc:
        logger.warning('QR no generado en diseño eki: %s', exc)

    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf


def generar_certificado_diseno_eki(certificado, plantilla) -> BytesIO | None:
    if not plantilla:
        return None
    return render_certificado_diseno_eki(
        plantilla=plantilla,
        nombre_estudiante=certificado.estudiante.nombre,
        curso_nombre=certificado.curso.nombre if certificado.curso else '',
        calificacion_final=getattr(certificado, 'calificacion_final', 0) or 0,
        codigo_verificacion=certificado.codigo_verificacion,
        url_verificacion=certificado.obtener_url_verificacion(),
        fecha_emision=getattr(certificado, 'fecha_emision', None) or getattr(certificado, 'fecha_completado', None),
    )
