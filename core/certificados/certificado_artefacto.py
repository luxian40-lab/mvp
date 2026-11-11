"""Artefactos del diploma: PDF A4 y copia liviana para WhatsApp.

El PNG se embebe a tamaño nativo. La página es A4 en puntos de ReportLab;
tratar píxeles como puntos produce hojas de ~50 pulgadas.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

_WA_MAX_BYTES_DEFAULT = 5 * 1024 * 1024
_WA_LADO_DEFAULT = 1600
_MAESTRO_LADO_DEFAULT = 4096


def _setting_int(nombre: str, default: int) -> int:
    try:
        from django.conf import settings
        return int(getattr(settings, nombre, default) or default)
    except Exception:
        return default


def png_maestro_acotado(png_buffer, *, max_lado=None) -> BytesIO:
    """Reduce el PNG maestro si un lado supera CERT_MAESTRO_LADO_MAX."""
    if max_lado is None:
        max_lado = _setting_int('CERT_MAESTRO_LADO_MAX', _MAESTRO_LADO_DEFAULT)
    png_buffer.seek(0)
    raw = png_buffer.read()
    with Image.open(BytesIO(raw)) as img:
        w, h = img.size
        largo = max(w, h)
        if largo <= max_lado:
            out = BytesIO(raw)
            out.seek(0)
            return out
        escala = max_lado / float(largo)
        nueva = img.convert('RGB') if img.mode != 'RGB' else img.copy()
        nueva = nueva.resize(
            (max(1, int(w * escala)), max(1, int(h * escala))),
            Image.Resampling.LANCZOS,
        )
    out = BytesIO()
    nueva.save(out, format='PNG', optimize=True)
    out.seek(0)
    return out


def png_para_whatsapp(png_buffer, *, max_bytes=None, max_lado=None) -> BytesIO:
    """Copia del diploma para WhatsApp: lado y peso acotados (JPEG si hace falta)."""
    if max_bytes is None:
        max_bytes = _setting_int('WHATSAPP_IMAGE_MAX_BYTES', _WA_MAX_BYTES_DEFAULT)
    if max_lado is None:
        max_lado = _setting_int('CERT_WA_LADO_MAX', _WA_LADO_DEFAULT)
    png_buffer.seek(0)
    img = Image.open(png_buffer)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    w, h = img.size
    largo = max(w, h)
    if largo > max_lado:
        escala = max_lado / float(largo)
        img = img.resize(
            (max(1, int(w * escala)), max(1, int(h * escala))),
            Image.Resampling.LANCZOS,
        )

    png_out = BytesIO()
    img.save(png_out, format='PNG', optimize=True)
    png_out.seek(0)
    if png_out.getbuffer().nbytes <= max_bytes:
        return png_out

    ultimo = png_out
    for quality in (92, 85, 75, 65, 55):
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        buf.seek(0)
        ultimo = buf
        if buf.getbuffer().nbytes <= max_bytes:
            return buf

    while max(img.size) > 640:
        img = img.resize(
            (max(1, img.size[0] // 2), max(1, img.size[1] // 2)),
            Image.Resampling.LANCZOS,
        )
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=55, optimize=True)
        buf.seek(0)
        ultimo = buf
        if buf.getbuffer().nbytes <= max_bytes:
            return buf
    return ultimo



def nombres_s3_envio(whatsapp_name=None, imagen_name=None) -> list[str]:
    """WhatsApp primero; diplomas viejos solo tienen el PNG maestro."""
    nombres = []
    wa = str(whatsapp_name or '').strip()
    if wa:
        nombres.append(wa)
    img = str(imagen_name or '').strip()
    if img and img not in nombres:
        nombres.append(img)
    return nombres


def png_buffer_a_pdf_a4(png_buffer) -> BytesIO:
    """Una página A4 (apaisada si el PNG es más ancho que alto) con el PNG completo."""
    png_buffer.seek(0)
    raw = png_buffer.read()
    with Image.open(BytesIO(raw)) as img:
        w_px, h_px = img.size
    if w_px <= 0 or h_px <= 0:
        raise ValueError('PNG del diploma sin dimensiones')

    page_w, page_h = landscape(A4) if w_px >= h_px else A4
    scale = min(page_w / float(w_px), page_h / float(h_px))
    draw_w = w_px * scale
    draw_h = h_px * scale
    x = (page_w - draw_w) / 2.0
    y = (page_h - draw_h) / 2.0

    out = BytesIO()
    c = canvas.Canvas(out, pagesize=(page_w, page_h))
    c.drawImage(
        ImageReader(BytesIO(raw)),
        x,
        y,
        width=draw_w,
        height=draw_h,
        preserveAspectRatio=True,
        mask='auto',
    )
    c.showPage()
    c.save()
    out.seek(0)
    return out
