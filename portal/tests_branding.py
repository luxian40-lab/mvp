"""Tests de branding del portal clientes."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente
from portal.branding import branding_portal_completo, pasos_branding
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario


class PortalBrandingHelpersTests(TestCase):
    def test_branding_incompleto_sin_logo_ni_subtitulo(self):
        org = Cliente(nombre='X', logo_url='', portal_subtitulo='')
        self.assertFalse(branding_portal_completo(org))
        self.assertEqual(len(pasos_branding(org)), 2)

    def test_branding_completo(self):
        org = Cliente(
            nombre='X',
            logo_url='https://example.com/logo.png',
            portal_subtitulo='Programa 2026',
        )
        self.assertTrue(branding_portal_completo(org))


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class PortalBrandingOnboardingTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Brand',
            contacto_principal='Ana',
            email='brand@test.com',
            telefono='573001234567',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        user = User.objects.create_user('portal_brand', password='pass1234')
        PortalUsuario.objects.create(user=user, organizacion=self.cliente, rol='admin')
        self.http = Client()
        session = self.http.session
        session[PORTAL_SESSION_KEY] = PortalUsuario.objects.get(user=user).pk
        session.save()

    def test_dashboard_muestra_onboarding_sin_branding(self):
        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Complete la identidad')
        self.assertContains(r, '/portal/perfil/')

    def test_dashboard_sin_banner_con_branding_completo(self):
        self.cliente.logo_url = 'https://example.com/l.png'
        self.cliente.portal_subtitulo = 'Mi programa'
        self.cliente.save()
        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Complete la identidad')

    def test_perfil_muestra_checklist(self):
        r = self.http.get('/portal/perfil/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Configuración de marca')
        self.assertContains(r, 'Vista previa en vivo')

    def test_favicon_bandera_colombia(self):
        r_login = Client().get('/portal/login/')
        self.assertContains(r_login, 'image/svg+xml')
        self.assertContains(r_login, 'FCD116')
