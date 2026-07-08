"""Tests Nat Knowledge Hub — biblioteca, portal solo-Nat."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from core.models import BibliotecaConocimiento, Cliente
from portal.capabilities import portal_home_url, portal_solo_nat
from portal.models import PortalUsuario


class BibliotecaNatServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Nat',
            contacto_principal='A',
            email='nat@test.com',
            telefono='573001111001',
            activo=True,
            portal_productos='nat',
        )

    @patch('core.biblioteca_nat_service.encolar_indexacion')
    def test_crear_faq_indexa(self, mock_enc):
        from core.biblioteca_nat_service import crear_desde_formulario

        item = crear_desde_formulario(
            self.cliente,
            {
                'titulo': 'PC en palma',
                'formato': 'faq',
                'pregunta': '¿Qué hacer con PC?',
                'texto_contenido': 'Aplicar manejo integrado…',
                'categoria': 'faq',
                'cultivo': 'palma',
            },
        )
        self.assertEqual(item.formato, 'faq')
        mock_enc.assert_called_once_with(item.pk)


class PortalSoloNatTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.cliente = Cliente.objects.create(
            nombre='Solo Nat SA',
            contacto_principal='A',
            email='solo@nat.com',
            telefono='573002222001',
            activo=True,
            portal_productos='nat',
        )
        self.user = User.objects.create_user('admin_nat', 'a@nat.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.cliente, rol='admin')

    def test_portal_solo_nat_detectado(self):
        self.assertTrue(portal_solo_nat(self.cliente))
        self.assertEqual(portal_home_url(self.cliente), '/portal/biblioteca/')

    def test_login_redirige_biblioteca(self):
        r = self.http.post('/portal/login/', {'username': 'admin_nat', 'password': 'pass'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/portal/biblioteca/')

    def test_dashboard_redirige_biblioteca(self):
        self.http.post('/portal/login/', {'username': 'admin_nat', 'password': 'pass'})
        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/portal/biblioteca/')

    def test_biblioteca_carga(self):
        self.http.post('/portal/login/', {'username': 'admin_nat', 'password': 'pass'})
        r = self.http.get('/portal/biblioteca/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Biblioteca de conocimiento')

    @patch('core.biblioteca_nat_service.encolar_indexacion')
    def test_crear_faq_desde_portal(self, _mock_enc):
        self.http.post('/portal/login/', {'username': 'admin_nat', 'password': 'pass'})
        r = self.http.post('/portal/biblioteca/nuevo/', {
            'formato': 'faq',
            'titulo': 'Roya en café',
            'pregunta': '¿Cómo controlar roya?',
            'texto_contenido': 'Monitoreo y fungicida según cartilla…',
            'categoria': 'faq',
            'cultivo': 'café',
            'estado_publicacion': 'publicado',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(BibliotecaConocimiento.objects.filter(cliente=self.cliente, titulo='Roya en café').exists())
