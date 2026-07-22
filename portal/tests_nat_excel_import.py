"""Tests import Excel Nat (productos + precios)."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, ProductoCatalogo, ProductoComercial
from portal.models import PortalUsuario
from portal.nat_catalogo_service import generar_plantilla_excel_nat, importar_excel_nat


@override_settings(SECURE_SSL_REDIRECT=False)
class NatExcelImportTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Import Nat SA',
            contacto_principal='A',
            email='importnat@test.com',
            telefono='573005555001',
            activo=True,
            portal_productos='nat',
        )
        self.user = User.objects.create_user('imp_nat', 'i@nat.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.org, rol='admin')
        self.http = Client()
        self.http.post('/portal/login/', {'username': 'imp_nat', 'password': 'pass'})

    def test_plantilla_descarga(self):
        r = self.http.get('/portal/catalogo/plantilla/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])

    def test_importar_plantilla_ejemplo(self):
        buf = generar_plantilla_excel_nat()
        resultado = importar_excel_nat(self.org, buf)
        self.assertEqual(resultado['productos_creados'], 1)
        self.assertEqual(resultado['precios_creados'], 1)
        self.assertTrue(
            ProductoCatalogo.objects.filter(cliente=self.org, nombre='Fungicida Café Plus').exists()
        )
        self.assertTrue(
            ProductoComercial.objects.filter(cliente=self.org, sku='FUNG-CAFE-500G').exists()
        )

        # Segunda pasada = update
        buf2 = generar_plantilla_excel_nat()
        r2 = importar_excel_nat(self.org, buf2)
        self.assertEqual(r2['productos_creados'], 0)
        self.assertEqual(r2['productos_actualizados'], 1)
        self.assertEqual(r2['precios_actualizados'], 1)

    def test_vista_importar_post(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = generar_plantilla_excel_nat()
        up = SimpleUploadedFile(
            'plantilla.xlsx',
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        r = self.http.post('/portal/catalogo/importar/', {'archivo': up})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ProductoCatalogo.objects.filter(cliente=self.org).exists())
        self.assertTrue(ProductoComercial.objects.filter(cliente=self.org).exists())
