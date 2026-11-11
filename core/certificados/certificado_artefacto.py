"""Artefactos del diploma: PDF A4 y (más adelante) copia para WhatsApp.

El PNG se embebe a tamaño nativo. La página es A4 en puntos de ReportLab;
tratar píxeles como puntos produce hojas de ~50 pulgadas.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


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
