"""PDF A4 del diploma: página estándar, PNG nativo embebido (sin tope 1100×850)."""
from __future__ import annotations

from io import BytesIO

from PIL import Image
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import A4, landscape

from hashlib import sha256
import os

from core.certificados.certificado_artefacto import (
    nombres_s3_envio,
    png_buffer_a_pdf_a4,
    png_maestro_acotado,
    png_para_whatsapp,
)
from core.certificados.certificado_diseno_eki import ANCHO, ALTO, _preparar_lienzo


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


def test_png_para_whatsapp_reduce_lado():
    out = png_para_whatsapp(_png((3200, 2000)), max_bytes=5 * 1024 * 1024, max_lado=1600)
    img = Image.open(out)
    img.load()
    assert max(img.size) <= 1600


def test_png_para_whatsapp_bajo_tope_bytes():
    ruido = Image.frombytes('RGB', (2200, 2200), os.urandom(2200 * 2200 * 3))
    buf = BytesIO()
    ruido.save(buf, format='PNG')
    buf.seek(0)
    assert buf.getbuffer().nbytes > 5 * 1024 * 1024
    out = png_para_whatsapp(buf, max_bytes=5 * 1024 * 1024, max_lado=1600)
    assert out.getbuffer().nbytes <= 5 * 1024 * 1024
    img = Image.open(out)
    img.load()


def test_hash_maestro_no_es_el_de_whatsapp():
    maestro = _png((2400, 1600))
    raw = maestro.getvalue()
    wa = png_para_whatsapp(BytesIO(raw), max_bytes=5 * 1024 * 1024, max_lado=1600)
    assert sha256(raw).hexdigest() != sha256(wa.getvalue()).hexdigest()


def test_png_maestro_acotado_respeta_tope():
    out = png_maestro_acotado(_png((5000, 3000)), max_lado=4096)
    img = Image.open(out)
    img.load()
    assert max(img.size) <= 4096


def test_nombres_s3_envio_prefiere_whatsapp():
    assert nombres_s3_envio('certs/wa.jpg', 'certs/maestro.png') == [
        'certs/wa.jpg',
        'certs/maestro.png',
    ]


def test_nombres_s3_envio_sin_whatsapp_usa_maestro():
    assert nombres_s3_envio('', 'certs/maestro.png') == ['certs/maestro.png']
    assert nombres_s3_envio(None, None) == []


def test_preparar_lienzo_fondo_grande_no_baja_a_1200():
    fondo = Image.new('RGB', (2400, 1700), (200, 200, 210))
    img, w, h, escala = _preparar_lienzo(fondo, max_lado=4096)
    assert (w, h) != (ANCHO, ALTO)
    assert (w, h) == (2400, 1700)
    assert img.size == (2400, 1700)
    assert abs(escala - (1700 / 848)) < 0.001


def test_preparar_lienzo_sin_fondo_es_a4():
    from core.certificados.certificado_diseno_eki import A4_ALTO_DEFAULT, A4_ANCHO_DEFAULT

    img, w, h, escala = _preparar_lienzo(None, max_lado=4096)
    assert img is None
    assert (w, h) == (A4_ANCHO_DEFAULT, A4_ALTO_DEFAULT)
    assert abs(escala - (A4_ALTO_DEFAULT / ALTO)) < 0.001
