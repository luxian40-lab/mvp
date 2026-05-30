import json
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import openpyxl
from django.core.management import call_command
from django.test import TestCase

from core.precios_excel import (
    detect_header_row,
    excel_a_payload_json,
    leer_filas_excel,
    parse_precio,
    slug_sku,
)


def _crear_xlsx_filas(filas: list[list], path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r, fila in enumerate(filas, start=1):
        for c, val in enumerate(fila, start=1):
            ws.cell(row=r, column=c, value=val)
    wb.save(path)
    wb.close()


class PreciosExcelTests(TestCase):
    def test_parse_precio_formato_colombiano(self):
        self.assertEqual(parse_precio('$185.000'), Decimal('185000'))
        self.assertEqual(parse_precio('245000'), Decimal('245000'))

    def test_slug_sku_sin_codigo(self):
        sku = slug_sku('Urea 46%', 'bulto 50 kg', 5)
        self.assertIn('UREA', sku)
        self.assertTrue(sku.endswith('-R5'))

    def test_detecta_encabezado_no_en_fila_1(self):
        filas = [
            ('Lista de precios mayo 2026',),
            ('Producto', 'Precio', 'Presentación'),
            ('Urea', 185000, 'bulto 50 kg'),
        ]
        idx = detect_header_row(filas)
        self.assertEqual(idx, 1)

    def test_leer_excel_con_titulo_arriba(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lista.xlsx'
            _crear_xlsx_filas([
                ['Catálogo comercial'],
                ['Producto', 'Precio unitario', 'Presentación', 'Código'],
                ['Urea 46%', 185000, 'bulto 50 kg', 'UREA-46'],
                ['MAP 12-61-0', '$245.000', 'bulto 50 kg', ''],
            ], path)
            productos = leer_filas_excel(path)
            self.assertEqual(len(productos), 2)
            self.assertEqual(productos[0]['sku'], 'UREA-46')
            self.assertEqual(productos[0]['precio'], 185000.0)
            self.assertTrue(productos[1]['sku'].startswith('MAP'))

    def test_excel_a_json_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lista.xlsx'
            _crear_xlsx_filas([
                ['nombre', 'precio'],
                ['Glifosato', 42000],
            ], path)
            payload = excel_a_payload_json(path, cliente_id=7)
            self.assertEqual(payload['cliente_id'], 7)
            self.assertEqual(len(payload['productos']), 1)

    def test_comando_excel_precios_a_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / 'test.xlsx'
            out = Path(tmp) / 'out.json'
            _crear_xlsx_filas([
                ['Producto', 'Precio'],
                ['Abono X', 10000],
            ], xlsx)
            call_command('excel_precios_a_json', archivo=str(xlsx), salida=str(out))
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(len(data['productos']), 1)
