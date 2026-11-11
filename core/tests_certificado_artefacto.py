"""PDF A4 del diploma: página estándar, PNG nativo embebido (sin tope 1100×850)."""
from __future__ import annotations

from io import BytesIO

from PIL import Image
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import A4, landscape

from core.certificados.certificado_artefacto import png_buffer_a_pdf_a4


def _png(size, color=(255, 255, 255)) -> BytesIO:
    buf = BytesIO()
    Image.new('RGB', size, color).save(buf, format='PNG')
    buf.seek(0)
    return buf


def _page_size(pdf_buf: BytesIO) -> tuple[float, float]:
    pdf_buf.seek(0)
    page = PdfReader(pdf_buf).pages[0]
    box = page.mediabox
    return float(box.width), float(box.height)


def test_png_buffer_a_pdf_a4_pagina_apaisada():
    aw, ah = landscape(A4)
    pdf = png_buffer_a_pdf_a4(_png((2400, 1700)))
    w, h = _page_size(pdf)
    assert abs(w - aw) < 1.5
    assert abs(h - ah) < 1.5
    # El tope viejo era 1100×850 puntos; A4 apaisada es ~842×595.
    assert abs(w - 1100) > 50


def test_png_buffer_a_pdf_a4_retrato_usa_a4_vertical():
    aw, ah = A4
    pdf = png_buffer_a_pdf_a4(_png((1200, 1800)))
    w, h = _page_size(pdf)
    assert abs(w - aw) < 1.5
    assert abs(h - ah) < 1.5


def test_png_buffer_a_pdf_a4_es_pdf():
    pdf = png_buffer_a_pdf_a4(_png((400, 300)))
    assert pdf.read()[:4] == b'%PDF'
