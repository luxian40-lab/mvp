"""QR del diploma: módulos enteros, sin grises de interpolar."""
from __future__ import annotations

import numpy as np
from PIL import Image

from core.certificados.certificado_qr import png_qr_nitido

URL = 'https://certificados.eki.technology/verificar-certificado/EKI-TEST-QR01/'


def _colores(img: Image.Image) -> set[tuple]:
    arr = np.asarray(img.convert('RGB'))
    return {tuple(int(c) for c in px) for px in arr.reshape(-1, 3)}


def test_qr_nitido_solo_blanco_y_negro():
    img = png_qr_nitido(URL, 110)
    assert img.size == (110, 110)
    assert _colores(img) <= {(0, 0, 0), (255, 255, 255)}


def test_qr_nitido_lado_pedido():
    img = png_qr_nitido(URL, 130)
    assert img.size == (130, 130)
    assert (0, 0, 0) in _colores(img)
    assert (255, 255, 255) in _colores(img)


def test_qr_diseno_eki_esquina_sin_grises():
    from core.certificado_diseno_eki import render_certificado_diseno_eki

    from core.certificado_diseno_eki import ALTO

    buf = render_certificado_diseno_eki(url_verificacion=URL)
    img = Image.open(buf).convert('RGB')
    w, h = img.size
    region = max(80, int(round(150 * h / float(ALTO))))
    crop = img.crop((w - region, h - region, w, h))
    grises = {
        c for c in _colores(crop)
        if c not in {(0, 0, 0), (255, 255, 255)} and min(c) == max(c)
    }
    assert len(grises) < 8
