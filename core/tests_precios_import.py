"""Tests importación precios comerciales (Excel/JSON → Postgres)."""
import json
import tempfile
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Cliente, ProductoComercial
from core.precios_import import importar_precios_desde_archivo


def _xlsx_con_filas(filas: list[list], path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in filas:
        ws.append(row)
    wb.save(path)


class PreciosImportTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Import Test SA')

    def test_importar_excel_crea_productos(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lista.xlsx'
            _xlsx_con_filas([
                ['nombre', 'precio', 'sku', 'categoria'],
                ['Urea 46%', 185000, 'UREA-46', 'fertilizante'],
            ], path)
            result = importar_precios_desde_archivo(
                path, cliente_id=self.cliente.id,
            )
            self.assertEqual(result.total_validos, 1)
            self.assertEqual(result.creados, 1)
            obj = ProductoComercial.objects.get(cliente=self.cliente, sku='UREA-46')
            self.assertEqual(obj.precio, Decimal('185000'))

    def test_dry_run_no_escribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lista.xlsx'
            _xlsx_con_filas([
                ['nombre', 'precio', 'sku'],
                ['Glifosato', 42000, 'GLIF-1'],
            ], path)
            result = importar_precios_desde_archivo(path, dry_run=True)
            self.assertEqual(result.total_validos, 1)
            self.assertEqual(ProductoComercial.objects.count(), 0)

    def test_importar_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lista.json'
            path.write_text(json.dumps({
                'cliente_id': self.cliente.id,
                'productos': [{
                    'sku': 'MAP-12',
                    'nombre': 'MAP 12-61-0',
                    'precio': 245000,
                }],
            }), encoding='utf-8')
            result = importar_precios_desde_archivo(path)
            self.assertEqual(result.actualizados + result.creados, 1)


class ProductoComercialAdminImportTests(TestCase):
    def setUp(self):
        self.admin = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='admin_precios',
            email='a@test.com',
            password='pass12345',
        )
        self.admin.login(username='admin_precios', password='pass12345')

    def test_importar_precios_url_responde(self):
        url = reverse('admin:core_productocomercial_importar_precios')
        resp = self.admin.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Importar precios')
