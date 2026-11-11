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


def _tope_maestro():
    try:
        from django.conf import settings
        return int(getattr(settings, 'CERT_MAESTRO_LADO_MAX', 4096) or 4096)
    except Exception:
        return 4096


def _preparar_lienzo(fondo, *, max_lado=None):
    """Fondo a tamaño nativo (tope de lado). Escala = alto / 848. Sin fondo: 1200×848."""
    if max_lado is None:
        max_lado = _tope_maestro()
    if fondo is None:
        return None, ANCHO, ALTO, 1.0
    img = fondo.convert('RGB') if fondo.mode != 'RGB' else fondo.copy()
    w, h = img.size
    largo = max(w, h)
    if largo > max_lado:
        escala_cap = max_lado / float(largo)
        img = img.resize(
            (max(1, int(w * escala_cap)), max(1, int(h * escala_cap))),
            Image.Resampling.LANCZOS,
        )
        w, h = img.size
    return img, w, h, h / float(ALTO)


def _px(valor, escala):
    return max(1, int(round(valor * escala)))


def _cargar_fuentes(escala=1.0):
    escala = max(escala, 0.25)
    aqui = os.path.dirname(os.path.abspath(__file__))
    candidatas = [
        os.path.join(aqui, 'fonts', 'GreatVibes-Regular.ttf'),
        os.path.join(aqui, '..', 'fonts', 'GreatVibes-Regular.ttf'),
        'arial.ttf',
        'C:\\Windows\\Fonts\\arial.ttf',
        'C:\\Windows\\Fonts\\arialbd.ttf',
    ]
    bases = (56, 24, 22, 18)
    for path in candidatas:
        try:
            return tuple(ImageFont.truetype(path, _px(b, escala)) for b in bases)
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
    url_verificacion='https://certificados.eki.technology/verificar-certificado/DEMO/',
    fecha_emision=None,
) -> BytesIO:
    """Renderiza certificado PNG con colores/textos/fondo del diseño eki."""
    from django.utils import timezone

    color_primario = _hex_a_rgb(getattr(plantilla, 'color_primario', None), (44, 62, 80))
    color_secundario = _hex_a_rgb(getattr(plantilla, 'color_secundario', None), (52, 152, 219))
    texto_superior = (getattr(plantilla, 'texto_superior', None) or 'eki - Soluciones Educativas').strip()
    texto_certificado = (getattr(plantilla, 'texto_certificado', None) or 'CERTIFICADO DE FINALIZACIÓN').strip()

    fondo = _abrir_imagen_campo(getattr(plantilla, 'imagen_fondo', None) if plantilla else None)
    img, ancho, alto, escala = _preparar_lienzo(fondo)
    if img is None:
        img = Image.new('RGB', (ancho, alto), (255, 255, 255))
        draw_bg = ImageDraw.Draw(img)
        margin = _px(36, escala)
        draw_bg.rectangle(
            (margin, margin, ancho - margin, alto - margin),
            outline=color_primario,
            width=_px(4, escala),
        )
        draw_bg.rectangle(
            (margin + _px(10, escala), margin + _px(10, escala),
             ancho - margin - _px(10, escala), alto - margin - _px(10, escala)),
            outline=color_secundario,
            width=_px(2, escala),
        )

    draw = ImageDraw.Draw(img)
    font_titulo, font_nombre, font_medio, font_peq = _cargar_fuentes(escala)

    logo = _abrir_imagen_campo(getattr(plantilla, 'logo_institucion', None) if plantilla else None)
    if logo:
        logo.thumbnail((_px(140, escala), _px(140, escala)), Image.Resampling.LANCZOS)
        img.paste(logo, ((ancho - logo.width) // 2, _px(42, escala)))

    _texto_centrado(draw, _px(170, escala), texto_superior, font_medio, color_primario, ancho=ancho)
    _texto_centrado(draw, _px(230, escala), texto_certificado, font_titulo, color_secundario, ancho=ancho)
    draw.line(
        (_px(220, escala), _px(290, escala), ancho - _px(220, escala), _px(290, escala)),
        fill=color_secundario,
        width=_px(3, escala),
    )

    _texto_centrado(draw, _px(330, escala), 'Se otorga el presente certificado a', font_peq, (30, 30, 30), ancho=ancho)
    _texto_centrado(draw, _px(380, escala), (nombre_estudiante or NOMBRE_DEMO).upper(), font_nombre, color_primario, ancho=ancho)
    _texto_centrado(draw, _px(470, escala), 'Por haber completado satisfactoriamente el curso', font_peq, (30, 30, 30), ancho=ancho)
    _texto_centrado(draw, _px(520, escala), curso_nombre or CURSO_DEMO, font_medio, color_secundario, ancho=ancho)
    _texto_centrado(draw, _px(590, escala), f'Calificación final: {calificacion_final}%', font_peq, (30, 30, 30), ancho=ancho)

    if not fecha_emision:
        fecha_emision = timezone.localdate()
    if hasattr(fecha_emision, 'strftime'):
        fecha_txt = fecha_emision.strftime('%d/%m/%Y')
    else:
        fecha_txt = str(fecha_emision)
    _texto_centrado(draw, _px(640, escala), f'Fecha de emisión: {fecha_txt}', font_peq, (80, 80, 80), ancho=ancho)

    codigo = f'Código: {codigo_verificacion}'
    draw.text((_px(48, escala), alto - _px(56, escala)), codigo, font=font_peq, fill=(120, 120, 120))

    try:
        import qrcode
        qr_lado = _px(110, escala)
        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(url_verificacion or 'https://certificados.eki.technology/verificar/')
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='black', back_color='white').resize((qr_lado, qr_lado))
        img.paste(qr_img, (ancho - _px(150, escala), alto - _px(150, escala)))
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
