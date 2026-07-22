"""Tests CRUD catálogo / precios Nat en portal."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, ProductoCatalogo, ProductoComercial
from portal.models import PortalUsuario


@override_settings(SECURE_SSL_REDIRECT=False)
class PortalNatCatalogoTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.org = Cliente.objects.create(
            nombre='Agro Nat SA',
            contacto_principal='A',
            email='agro@nat.com',
            telefono='573003333001',
            activo=True,
            portal_productos='nat',
        )
        self.other = Cliente.objects.create(
            nombre='Otra Org',
            contacto_principal='B',
            email='otra@nat.com',
            telefono='573003333002',
            activo=True,
            portal_productos='nat',
        )
        self.user = User.objects.create_user('admin_cat', 'c@nat.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.org, rol='admin')
        self.http.post('/portal/login/', {'username': 'admin_cat', 'password': 'pass'})

    def test_crear_producto_catalogo(self):
        r = self.http.post('/portal/catalogo/nuevo/', {
            'nombre': 'Fungicida X',
            'descripcion': 'Control de hongos foliares',
            'problema_que_resuelve': 'Roya, manchas negras',
            'categoria': 'fungicida',
            'cultivos_objetivo': 'café',
            'activo': '1',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            ProductoCatalogo.objects.filter(cliente=self.org, nombre='Fungicida X').exists()
        )

    def test_crear_precio_sku(self):
        r = self.http.post('/portal/precios/nuevo/', {
            'sku': 'FUNG-X-1L',
            'nombre': 'Fungicida X 1L',
            'precio': '45000',
            'moneda': 'COP',
            'activo': '1',
        })
        self.assertEqual(r.status_code, 302)
        item = ProductoComercial.objects.get(cliente=self.org, sku='FUNG-X-1L')
        self.assertEqual(item.precio, 45000)

    def test_no_edita_producto_de_otra_org(self):
        alien = ProductoCatalogo.objects.create(
            cliente=self.other,
            nombre='Ajeno',
            descripcion='d',
            problema_que_resuelve='p',
        )
        r = self.http.get(f'/portal/catalogo/{alien.pk}/editar/')
        self.assertEqual(r.status_code, 404)

    def test_no_lista_precio_general(self):
        ProductoComercial.objects.create(
            cliente=None,
            sku='GEN-1',
            nombre='General',
            precio=1000,
        )
        ProductoComercial.objects.create(
            cliente=self.org,
            sku='ORG-1',
            nombre='Propio',
            precio=2000,
        )
        r = self.http.get('/portal/precios/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ORG-1')
        self.assertNotContains(r, 'GEN-1')

    def test_org_sin_nat_redirige(self):
        org_cursos = Cliente.objects.create(
            nombre='Solo Cursos',
            contacto_principal='C',
            email='cursos@test.com',
            telefono='573003333003',
            activo=True,
            portal_productos='cursos',
        )
        user = User.objects.create_user('admin_cursos', 'c@cursos.com', 'pass')
        PortalUsuario.objects.create(user=user, organizacion=org_cursos, rol='admin')
        http = Client()
        http.post('/portal/login/', {'username': 'admin_cursos', 'password': 'pass'})
        r = http.get('/portal/catalogo/')
        self.assertEqual(r.status_code, 302)
