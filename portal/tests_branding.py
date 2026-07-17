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

    def test_portal_identidad_visual(self):
        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Plus+Jakarta+Sans')
        self.assertContains(r, 'eki <em>portal</em>')
        self.assertContains(r, 'Inicio')
        self.assertNotContains(r, 'Fraunces')
        self.assertNotContains(r, 'family=Sora')
        self.assertNotContains(r, 'IBM+Plex+Sans')

    def test_perfil_muestra_checklist(self):
        r = self.http.get('/portal/perfil/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Configuración de marca')
        self.assertContains(r, 'Vista previa en vivo')

    def test_favicon_portal_distinto(self):
        r_login = Client().get('/portal/login/')
        self.assertEqual(r_login.status_code, 200)
        self.assertContains(r_login, 'favicons/portal')
        self.assertContains(r_login, 'image/png')

    def test_login_hero_premium_saas(self):
        r_login = Client().get('/portal/login/')
        self.assertEqual(r_login.status_code, 200)
        self.assertContains(r_login, 'eki')
        self.assertContains(r_login, 'portal')
        self.assertContains(r_login, 'Bienvenido nuevamente')
        self.assertContains(r_login, 'Progreso del programa')
        self.assertContains(r_login, 'Participantes activos')
        self.assertContains(r_login, 'Cobertura por sede')
        self.assertNotContains(r_login, 'Ingresar con Google')
        self.assertNotContains(r_login, 'google-btn')
        self.assertNotContains(r_login, 'images.unsplash.com')
        self.assertNotContains(r_login, 'hero-metrics')

    def test_login_hero_es_una_sola_escena(self):
        """El dashboard vive integrado en el hero, sin bloques de imagen aparte ni personaje."""
        r_login = Client().get('/portal/login/')
        self.assertEqual(r_login.status_code, 200)
        self.assertContains(r_login, 'hero-stage')
        self.assertContains(r_login, 'class="dash"')
        self.assertNotContains(r_login, 'hero__visual')
        self.assertNotContains(r_login, 'portal-hero-integrated.png')


class FaviconSurfacesTests(SimpleTestCase):
    """Cada superficie tiene favicon propio (PNG de marca o SVG de color distinto)."""

    def test_favicons_tienen_colores_distintos(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'static' / 'favicons'
        # Portal y Aprende usan logo de marca en PNG.
        self.assertTrue((root / 'portal.png').is_file())
        self.assertTrue((root / 'portal-32.png').is_file())
        self.assertTrue((root / 'aprende.png').is_file())
        self.assertTrue((root / 'aprende-32.png').is_file())
        # Admin / studio siguen en SVG con colores distintos.
        import re
        colors = {}
        for name in ('admin', 'studio'):
            svg = (root / f'{name}.svg').read_text(encoding='utf-8')
            m = re.search(r'fill="(#[0-9a-fA-F]{6})"', svg)
            self.assertIsNotNone(m, name)
            colors[name] = m.group(1).lower()
        self.assertEqual(colors['admin'], '#0f172a')
        self.assertEqual(colors['studio'], '#c2410c')
        self.assertNotEqual(colors['admin'], colors['studio'])
