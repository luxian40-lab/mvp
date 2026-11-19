"""Generación y vista previa de certificados con diseño eki (Pillow)."""

from __future__ import annotations

import logging
import math
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

ANCHO = 1200
ALTO = 848
A4_ANCHO_DEFAULT = 3508
A4_ALTO_DEFAULT = 2480
# Papel claro; acentos de marca eki
PAPEL_EKI = (252, 250, 255)
MORADO = (154, 108, 172)       # #9A6CAC
MORADO_PROFUNDO = (122, 78, 142)  # #7A4E8E
MORADO_TINTA = (95, 58, 110)   # #5F3A6E
MORADO_CLARO = (236, 226, 242)
TEXTO_MARCA_DEFAULT = 'eki'
TEXTO_MARCA_LEGADO = 'eki - Soluciones Educativas'
NOMBRE_DEMO = 'MARÍA GONZÁLEZ PÉREZ'
CURSO_DEMO = '[Nombre del curso]'


def _hex_a_rgb(hex_color: str, default=(95, 58, 110)) -> tuple[int, int, int]:
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


def _tamano_diseno_sin_fondo():
    """A4 apaisado si no hay fondo. Layout sigue midiendo en 1200×848."""
    try:
        from django.conf import settings
        w = int(getattr(settings, 'CERT_DISENO_EKI_ANCHO', A4_ANCHO_DEFAULT) or A4_ANCHO_DEFAULT)
        h = int(getattr(settings, 'CERT_DISENO_EKI_ALTO', A4_ALTO_DEFAULT) or A4_ALTO_DEFAULT)
        return max(800, w), max(600, h)
    except Exception:
        return A4_ANCHO_DEFAULT, A4_ALTO_DEFAULT


def _preparar_lienzo(fondo, *, max_lado=None):
    """Fondo a tamaño nativo (tope de lado). Escala = alto / 848. Sin fondo: A4."""
    if max_lado is None:
        max_lado = _tope_maestro()
    if fondo is None:
        w, h = _tamano_diseno_sin_fondo()
        return None, w, h, h / float(ALTO)
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


def _dirs_fuentes():
    aqui = os.path.dirname(os.path.abspath(__file__))
    return (
        os.path.join(aqui, '..', 'fonts'),
        os.path.join(aqui, 'fonts'),
    )


def _truetype(nombres, size):
    for carpeta in _dirs_fuentes():
        for nombre in nombres:
            path = os.path.normpath(os.path.join(carpeta, nombre))
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                continue
    for path in ('arial.ttf', r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\arialbd.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _peso_variable(font, nombre):
    try:
        names = font.get_variation_names()
        clave = nombre.encode('ascii') if isinstance(nombre, str) else nombre
        if clave in names:
            font.set_variation_by_name(nombre)
    except Exception:
        pass
    return font


def _cargar_fuentes(escala=1.0):
    """Expletus Sans para el diploma; Covered By Your Grace solo para la palabra eki."""
    escala = max(escala, 0.25)
    ui = ('ExpletusSans-Variable.ttf',)
    marca = ('CoveredByYourGrace.ttf',)
    fallback = ('GreatVibes-Regular.ttf',)
    titulo = _peso_variable(_truetype(ui + fallback, _px(34, escala)), 'SemiBold')
    nombre = _peso_variable(_truetype(ui + fallback, _px(42, escala)), 'SemiBold')
    medio = _truetype(ui + fallback, _px(24, escala))
    peq = _truetype(ui + fallback, _px(18, escala))
    eki = _truetype(marca + fallback, _px(52, escala))
    pill = _peso_variable(_truetype(ui + fallback, _px(36, escala)), 'Bold')
    return titulo, nombre, medio, peq, eki, pill


def _texto_centrado(draw, y, texto, font, fill, ancho=ANCHO):
    if not texto:
        return
    bbox = draw.textbbox((0, 0), texto, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((ancho - w) // 2, y), texto, font=font, fill=fill)


def _ancho_texto(draw, texto, font):
    if not texto:
        return 0
    bbox = draw.textbbox((0, 0), texto, font=font)
    return bbox[2] - bbox[0]


def _texto_marca(texto) -> str:
    """La marca es solo eki. El legado 'Soluciones Educativas' no se pinta."""
    raw = (texto or '').strip()
    if not raw or raw.lower() == TEXTO_MARCA_LEGADO.lower():
        return TEXTO_MARCA_DEFAULT
    return raw


def _margen_interno(escala):
    return _px(56, escala)


def _caja_qr(ancho, alto, escala, lado=None):
    lado = lado if lado is not None else _px(118, escala)
    hueco = _margen_interno(escala) + _px(12, escala)
    return ancho - hueco - lado, alto - hueco - lado, lado


def _repo_static(*parts):
    aqui = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(aqui, '..', '..', 'static', *parts))


def _cargar_logo_eki(escala):
    """Logo marca eki (PNG del repo). Fallback: None."""
    candidatos = (
        _repo_static('calculadora_margen', 'eki-logo.png'),
        _repo_static('aprende', 'img', 'eki-logo.png'),
    )
    for path in candidatos:
        try:
            if not os.path.isfile(path):
                continue
            logo = Image.open(path).convert('RGBA')
            alto_logo = _px(78, escala)
            ratio = alto_logo / float(logo.height)
            logo = logo.resize(
                (max(1, int(logo.width * ratio)), alto_logo),
                Image.Resampling.LANCZOS,
            )
            return logo
        except Exception as exc:
            logger.warning('Logo eki no cargó (%s): %s', path, exc)
    return None


def _cuarto(capa, cx, cy, radio, inicio, fin, color):
    """Cuarto de círculo completo. Los radios rectos coinciden con el borde."""
    overlay = Image.new('RGBA', capa.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).pieslice(
        (cx - radio, cy - radio, cx + radio, cy + radio),
        inicio, fin, fill=(*color, 255),
    )
    return Image.alpha_composite(capa, overlay)


def _cintas_esquinas(capa, primario, secundario, escala):
    """Dos cuartos sólidos de marca. No imitan el 3D del mock."""
    del escala
    w, h = capa.size
    radio = int(h * 0.16)
    interno = int(radio * 0.62)
    capa = _cuarto(capa, 0, 0, radio, 0, 90, primario)
    capa = _cuarto(capa, 0, 0, interno, 0, 90, secundario)
    capa = _cuarto(capa, w, h, radio, 180, 270, primario)
    capa = _cuarto(capa, w, h, interno, 180, 270, secundario)
    return capa


def _ondas_sutiles(capa, color, escala):
    """Líneas onduladas tipo guilloché muy suaves."""
    overlay = Image.new('RGBA', capa.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    w, h = capa.size
    paso = _px(28, escala)
    amp = _px(10, escala)
    for i, y0 in enumerate(range(_px(120, escala), h - _px(120, escala), paso)):
        pts = []
        for x in range(0, w, _px(8, escala)):
            y = y0 + int(amp * math.sin((x / float(w)) * math.pi * 4 + i * 0.4))
            pts.append((x, y))
        if len(pts) > 1:
            d.line(pts, fill=(*color, 28), width=max(1, _px(1, escala)))
    return Image.alpha_composite(capa, overlay)


def _rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _fecha_con_calendario(draw, ancho, y, fecha_txt, font, fill, color, escala):
    """Icono de calendario junto a la fecha. El grupo queda centrado."""
    texto = f'Fecha de emisión: {fecha_txt}'
    lado = _px(22, escala)
    gap = _px(10, escala)
    tw = _ancho_texto(draw, texto, font)
    x = (ancho - (lado + gap + tw)) // 2
    trazo = max(2, _px(2, escala))
    _rounded_rect(draw, (x, y, x + lado, y + lado), radius=_px(4, escala), outline=color, width=trazo)
    draw.rectangle((x, y, x + lado, y + _px(7, escala)), fill=color)
    draw.line((x + _px(6, escala), y - _px(3, escala), x + _px(6, escala), y + _px(4, escala)), fill=color, width=trazo)
    draw.line((x + lado - _px(6, escala), y - _px(3, escala), x + lado - _px(6, escala), y + _px(4, escala)), fill=color, width=trazo)
    draw.text((x + lado + gap, y), texto, font=font, fill=fill)


def _pintar_preset_eki(img, color_primario, color_secundario, escala):
    """Look cercano al mock de marca: papel, blobs, marco redondeado, ondas."""
    ancho, alto = img.size
    base = Image.new('RGBA', (ancho, alto), (*PAPEL_EKI, 255))
    primario = color_primario or MORADO_TINTA
    secundario = color_secundario or MORADO

    base = _cintas_esquinas(base, primario, secundario, escala)
    base = _ondas_sutiles(base, primario, escala)

    draw = ImageDraw.Draw(base)
    m = _px(36, escala)
    _rounded_rect(
        draw,
        (m, m, ancho - m, alto - m),
        radius=_px(28, escala),
        outline=(*primario, 220),
        width=_px(3, escala),
    )
    rgb = Image.new('RGB', (ancho, alto), PAPEL_EKI)
    rgb.paste(base, mask=base.split()[3] if base.mode == 'RGBA' else None)
    # Copiar sobre img in-place
    img.paste(rgb)


def _partir_titulo(texto: str) -> tuple[str, str]:
    raw = (texto or 'CERTIFICADO DE FINALIZACIÓN').strip()
    up = raw.upper()
    if 'FINALIZACIÓN' in up or 'FINALIZACION' in up:
        return 'CERTIFICADO DE', 'FINALIZACIÓN'
    partes = raw.split()
    if len(partes) >= 2:
        return ' '.join(partes[:-1]).upper(), partes[-1].upper()
    return raw.upper(), ''


def render_certificado_diseno_eki(
    *,
    plantilla=None,
    nombre_estudiante=NOMBRE_DEMO,
    curso_nombre=CURSO_DEMO,
    calificacion_final=95,  # se conserva en firma; ya no se pinta
    codigo_verificacion='DEMO-0001',
    url_verificacion='https://certificados.eki.technology/verificar-certificado/DEMO/',
    fecha_emision=None,
) -> BytesIO:
    """Renderiza certificado PNG con look de marca eki (sin calificación)."""
    from django.utils import timezone

    del calificacion_final  # no se muestra en el diploma

    color_primario = _hex_a_rgb(getattr(plantilla, 'color_primario', None), MORADO_TINTA)
    color_secundario = _hex_a_rgb(getattr(plantilla, 'color_secundario', None), MORADO)
    texto_certificado = (
        getattr(plantilla, 'texto_certificado', None) or 'CERTIFICADO DE FINALIZACIÓN'
    ).strip()

    fondo = _abrir_imagen_campo(getattr(plantilla, 'imagen_fondo', None) if plantilla else None)
    img, ancho, alto, escala = _preparar_lienzo(fondo)
    if img is None:
        img = Image.new('RGB', (ancho, alto), PAPEL_EKI)
        _pintar_preset_eki(img, color_primario, color_secundario, escala)
    else:
        # Con fondo Canva, no forzamos el preset; solo tipografía eki
        pass

    draw = ImageDraw.Draw(img)
    font_titulo, font_nombre, font_medio, font_peq, font_eki, font_pill = _cargar_fuentes(escala)

    # Logo marca (plantilla o asset eki)
    logo = _abrir_imagen_campo(getattr(plantilla, 'logo_institucion', None) if plantilla else None)
    if logo is None:
        logo_rgba = _cargar_logo_eki(escala)
        if logo_rgba is not None:
            x_logo = (ancho - logo_rgba.width) // 2
            img.paste(logo_rgba, (x_logo, _px(58, escala)), logo_rgba)
        else:
            _texto_centrado(draw, _px(70, escala), 'eki', font_eki, color_primario, ancho=ancho)
    else:
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        logo.thumbnail((_px(200, escala), _px(90, escala)), Image.Resampling.LANCZOS)
        img.paste(logo, ((ancho - logo.width) // 2, _px(58, escala)), logo)

    linea1, linea2 = _partir_titulo(texto_certificado)
    _texto_centrado(draw, _px(170, escala), linea1, font_titulo, color_primario, ancho=ancho)

    if linea2:
        pill_txt = linea2
        tw = _ancho_texto(draw, pill_txt, font_pill)
        pad_x, pad_y = _px(36, escala), _px(14, escala)
        pill_w = tw + pad_x * 2
        pill_h = _px(56, escala)
        px0 = (ancho - pill_w) // 2
        py0 = _px(220, escala)
        _rounded_rect(
            draw,
            (px0, py0, px0 + pill_w, py0 + pill_h),
            radius=_px(28, escala),
            fill=color_secundario,
        )
        # brillos laterales
        draw.line(
            (px0 - _px(40, escala), py0 + pill_h // 2, px0 - _px(8, escala), py0 + pill_h // 2),
            fill=color_secundario,
            width=_px(2, escala),
        )
        draw.line(
            (px0 + pill_w + _px(8, escala), py0 + pill_h // 2, px0 + pill_w + _px(40, escala), py0 + pill_h // 2),
            fill=color_secundario,
            width=_px(2, escala),
        )
        bbox = draw.textbbox((0, 0), pill_txt, font=font_pill)
        th = bbox[3] - bbox[1]
        draw.text(
            (px0 + pad_x, py0 + (pill_h - th) // 2 - _px(2, escala)),
            pill_txt,
            font=font_pill,
            fill=(255, 255, 255),
        )

    # Sello check
    sello_r = _px(28, escala)
    sx, sy = ancho // 2, _px(320, escala)
    draw.ellipse((sx - sello_r, sy - sello_r, sx + sello_r, sy + sello_r), fill=color_secundario)
    # check simple
    draw.line(
        (sx - _px(10, escala), sy, sx - _px(2, escala), sy + _px(10, escala)),
        fill=(255, 255, 255),
        width=_px(4, escala),
    )
    draw.line(
        (sx - _px(2, escala), sy + _px(10, escala), sx + _px(14, escala), sy - _px(10, escala)),
        fill=(255, 255, 255),
        width=_px(4, escala),
    )
    draw.line(( _px(220, escala), sy, sx - sello_r - _px(8, escala), sy), fill=MORADO_CLARO, width=_px(2, escala))
    draw.line((sx + sello_r + _px(8, escala), sy, ancho - _px(220, escala), sy), fill=MORADO_CLARO, width=_px(2, escala))

    _texto_centrado(
        draw, _px(370, escala), 'Se otorga el presente certificado a', font_peq, (90, 80, 100), ancho=ancho,
    )

    nombre = (nombre_estudiante or NOMBRE_DEMO).upper()
    nw = _ancho_texto(draw, nombre, font_nombre)
    box_pad_x, box_pad_y = _px(40, escala), _px(16, escala)
    box_w = nw + box_pad_x * 2
    box_h = _px(70, escala)
    bx0 = (ancho - box_w) // 2
    by0 = _px(410, escala)
    _rounded_rect(
        draw,
        (bx0, by0, bx0 + box_w, by0 + box_h),
        radius=_px(18, escala),
        fill=MORADO_CLARO,
    )
    bbox = draw.textbbox((0, 0), nombre, font=font_nombre)
    nh = bbox[3] - bbox[1]
    draw.text(
        (bx0 + box_pad_x, by0 + (box_h - nh) // 2 - _px(2, escala)),
        nombre,
        font=font_nombre,
        fill=color_primario,
    )

    _texto_centrado(
        draw,
        _px(510, escala),
        'Por haber completado satisfactoriamente el curso',
        font_peq,
        (90, 80, 100),
        ancho=ancho,
    )
    _texto_centrado(
        draw, _px(555, escala), curso_nombre or CURSO_DEMO, font_medio, color_secundario, ancho=ancho,
    )

    if not fecha_emision:
        fecha_emision = timezone.localdate()
    if hasattr(fecha_emision, 'strftime'):
        fecha_txt = fecha_emision.strftime('%d/%m/%Y')
    else:
        fecha_txt = str(fecha_emision)
    _fecha_con_calendario(
        draw, ancho, _px(640, escala), fecha_txt, font_peq, (120, 110, 130), color_secundario, escala,
    )

    # Código en pastilla (izq)
    codigo = f'Código: {codigo_verificacion}'
    cw = _ancho_texto(draw, codigo, font_peq)
    ch = _px(36, escala)
    cx0 = _margen_interno(escala)
    cy0 = alto - _margen_interno(escala) - ch
    _rounded_rect(
        draw,
        (cx0, cy0, cx0 + cw + _px(28, escala), cy0 + ch),
        radius=_px(18, escala),
        fill=MORADO_CLARO,
    )
    draw.text((cx0 + _px(14, escala), cy0 + _px(8, escala)), codigo, font=font_peq, fill=color_primario)

    # QR en tarjeta blanca (der), sin tapar margen
    try:
        from core.certificados.certificado_qr import png_qr_nitido

        x_qr, y_qr, qr_lado = _caja_qr(ancho, alto, escala)
        pad = _px(10, escala)
        _rounded_rect(
            draw,
            (int(x_qr) - pad, int(y_qr) - pad, int(x_qr) + qr_lado + pad, int(y_qr) + qr_lado + pad),
            radius=_px(14, escala),
            fill=(255, 255, 255),
            outline=MORADO_CLARO,
            width=_px(2, escala),
        )
        qr_img = png_qr_nitido(
            url_verificacion or 'https://certificados.eki.technology/verificar/',
            qr_lado,
        )
        img.paste(qr_img, (int(x_qr), int(y_qr)))
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
