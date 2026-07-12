"""Tests de branding del portal clientes."""

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings

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

    def test_favicon_portal_distinto(self):
        r_login = Client().get('/portal/login/')
        self.assertEqual(r_login.status_code, 200)
        self.assertContains(r_login, 'favicons/portal.svg')
        self.assertContains(r_login, 'image/svg+xml')


class FaviconSurfacesTests(SimpleTestCase):
    """Los favicons deben diferenciarse por color, no todos morados."""

    def test_favicons_tienen_colores_distintos(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'static' / 'favicons'
        colors = {}
        for name in ('admin', 'portal', 'aprende', 'studio'):
            svg = (root / f'{name}.svg').read_text(encoding='utf-8')
            # primer fill de fondo
            import re
            m = re.search(r'fill="(#[0-9a-fA-F]{6})"', svg)
            self.assertIsNotNone(m, name)
            colors[name] = m.group(1).lower()
        self.assertEqual(colors['portal'], '#7a4e8e')
        self.assertEqual(colors['admin'], '#0f172a')
        self.assertEqual(colors['aprende'], '#0f6e6a')
        self.assertEqual(colors['studio'], '#c2410c')
        self.assertEqual(len(set(colors.values())), 4)
