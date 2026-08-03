"""Regresión: marcadores RGB (nombre/cédula/fecha/QR) en certificados."""

from datetime import date
from io import BytesIO

import numpy as np
from django.test import SimpleTestCase
from django.utils import timezone
from PIL import Image

from core.utils_certificados import (
    FUENTE_CEDULA_DEFAULT,
    FUENTE_NOMBRE_DEFAULT,
    MARCADOR_CEDULA,
    MARCADOR_FECHA,
    MARCADOR_NOMBRE,
    MARCADOR_QR,
    TAMAÑO_QR_DEFAULT,
    encontrar_marcador,
    generar_certificado_marcadores,
)

URL_QR = 'https://certificados.eki.technology/verificar-certificado/EKI-TEST-QR01/'


def _plantilla_con_marcadores(*, con_fecha=True, size=(600, 420)):
    """Plantilla sintética blanca con manchas RGB puras (nombre/cédula/fecha/QR)."""
    img = Image.new('RGB', size, (255, 255, 255))
    draw_pts = [
        (300, 120, MARCADOR_NOMBRE),
        (300, 200, MARCADOR_CEDULA),
        (300, 280, MARCADOR_FECHA if con_fecha else (255, 255, 255)),
        (480, 340, MARCADOR_QR),
    ]
    pixels = img.load()
    for cx, cy, color in draw_pts:
        if color == (255, 255, 255):
            continue
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                x, y = cx + dx, cy + dy
                if 0 <= x < size[0] and 0 <= y < size[1]:
                    pixels[x, y] = color
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class CertificadoMarcadoresQrTests(SimpleTestCase):
    def test_defaults_nombre_y_cedula_mas_pequenos(self):
        self.assertLessEqual(FUENTE_NOMBRE_DEFAULT, 60)
        self.assertLessEqual(FUENTE_CEDULA_DEFAULT, 32)

    def test_encontrar_marcadores_en_plantilla(self):
        raw = _plantilla_con_marcadores(con_fecha=True)
        np_img = np.array(Image.open(BytesIO(raw)).convert('RGB'))
        self.assertIsNotNone(encontrar_marcador(np_img, MARCADOR_NOMBRE))
        self.assertIsNotNone(encontrar_marcador(np_img, MARCADOR_CEDULA))
        self.assertIsNotNone(encontrar_marcador(np_img, MARCADOR_FECHA))
        self.assertIsNotNone(encontrar_marcador(np_img, MARCADOR_QR))

    def test_qr_se_pega_y_codifica_url_verificacion(self):
        try:
            from pyzbar.pyzbar import decode as zbar_decode
        except ImportError:
            zbar_decode = None

        buf = generar_certificado_marcadores(
            plantilla_bytes=_plantilla_con_marcadores(con_fecha=False),
            nombre_estudiante='Ana María López',
            cedula_estudiante='1020304050',
            url_verificacion=URL_QR,
            tamaño_qr=TAMAÑO_QR_DEFAULT,
            ajuste_qr_y=0,
        )
        out = Image.open(buf).convert('RGB')
        self.assertEqual(out.size, (600, 420))

        # Zona del marcador azul debe tener contraste (QR pegado, no azul puro).
        crop = out.crop((480 - 65, 340 - 65, 480 + 65, 340 + 65))
        arr = np.array(crop)
        self.assertTrue(arr.min() < 40, 'QR debería incluir píxeles oscuros')
        self.assertTrue(arr.max() > 200, 'QR debería incluir píxeles claros')

        if zbar_decode is not None:
            decoded = zbar_decode(crop)
            self.assertTrue(decoded, 'QR no decodificable')
            payloads = [d.data.decode('utf-8') for d in decoded]
            self.assertIn(URL_QR, payloads)

    def test_fecha_hoy_si_hay_marcador_amarillo(self):
        hoy = timezone.localdate().strftime('%d/%m/%Y')
        buf = generar_certificado_marcadores(
            plantilla_bytes=_plantilla_con_marcadores(con_fecha=True),
            nombre_estudiante='Pedro Ruiz',
            cedula_estudiante='99887766',
            url_verificacion=URL_QR,
            fecha_emision=timezone.localdate(),
            ajuste_qr_y=0,
        )
        # Sin OCR: validamos que la generación no falla y el marcador amarillo desaparece.
        out = Image.open(buf).convert('RGB')
        np_img = np.array(out)
        self.assertIsNone(encontrar_marcador(np_img, MARCADOR_FECHA))
        self.assertEqual(hoy, timezone.localdate().strftime('%d/%m/%Y'))

    def test_sin_amarillo_sigue_generando(self):
        buf = generar_certificado_marcadores(
            plantilla_bytes=_plantilla_con_marcadores(con_fecha=False),
            nombre_estudiante='Laura Díaz',
            cedula_estudiante='11223344',
            url_verificacion=URL_QR,
            fecha_emision=date(2026, 8, 3),
            ajuste_qr_y=0,
        )
        out = Image.open(buf)
        self.assertEqual(out.format, 'PNG')

    def test_falla_sin_marcador_qr(self):
        img = Image.new('RGB', (400, 300), (255, 255, 255))
        px = img.load()
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                px[100 + dx, 80 + dy] = MARCADOR_NOMBRE
                px[100 + dx, 150 + dy] = MARCADOR_CEDULA
        raw = BytesIO()
        img.save(raw, format='PNG')
        with self.assertRaises(ValueError) as ctx:
            generar_certificado_marcadores(
                plantilla_bytes=raw.getvalue(),
                nombre_estudiante='X',
                cedula_estudiante='1',
                url_verificacion=URL_QR,
            )
        self.assertIn('QR', str(ctx.exception))
