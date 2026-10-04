"""CSRF en producción: orígenes eki siempre presentes."""
import os
import importlib
from unittest import mock

from django.test import SimpleTestCase


_ENV_OK = {
    'SECRET_KEY': 'x' * 50,
    'EKI_ALLOWED_HOSTS': 'admin.eki.technology,app.eki.technology',
    'CSRF_TRUSTED_ORIGINS': 'https://admin.eki.technology',
}


class ProductionCsrfOriginsTests(SimpleTestCase):
    def test_csrf_vacio_no_arranca(self):
        from django.core.exceptions import ImproperlyConfigured

        env = dict(_ENV_OK)
        env['CSRF_TRUSTED_ORIGINS'] = ''
        with mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(ImproperlyConfigured):
                mod = importlib.import_module('mvp_project.settings_production')
                importlib.reload(mod)

    def test_secret_de_desarrollo_no_arranca(self):
        from django.core.exceptions import ImproperlyConfigured

        env = dict(_ENV_OK)
        env['SECRET_KEY'] = 'django-insecure-mvp-clave-secreta-cambiar-en-produccion'
        with mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(ImproperlyConfigured):
                mod = importlib.import_module('mvp_project.settings_production')
                importlib.reload(mod)

    def test_hosts_vacios_no_arranca(self):
        from django.core.exceptions import ImproperlyConfigured

        env = dict(_ENV_OK)
        env['EKI_ALLOWED_HOSTS'] = ''
        with mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(ImproperlyConfigured):
                mod = importlib.import_module('mvp_project.settings_production')
                importlib.reload(mod)

    def test_csrf_trusted_origins_incluye_admin(self):
        with mock.patch.dict(os.environ, _ENV_OK, clear=False):
            mod = importlib.import_module('mvp_project.settings_production')
            importlib.reload(mod)
            origins = mod.CSRF_TRUSTED_ORIGINS
        self.assertIn('https://admin.eki.technology', origins)
        self.assertIn('https://app.eki.technology', origins)
        self.assertTrue(
            any('elasticbeanstalk.com' in o for o in origins),
            origins,
        )

    def test_hsts_por_defecto(self):
        env = dict(_ENV_OK)
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop('SECURE_HSTS_SECONDS', None)
            os.environ.pop('SECURE_HSTS_INCLUDE_SUBDOMAINS', None)
            mod = importlib.import_module('mvp_project.settings_production')
            importlib.reload(mod)
        self.assertEqual(mod.SECURE_HSTS_SECONDS, 86400)
        self.assertFalse(mod.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertFalse(mod.SECURE_HSTS_PRELOAD)

    def test_hsts_segundos_y_subdominios_desde_env(self):
        env = dict(_ENV_OK)
        env['SECURE_HSTS_SECONDS'] = '3600'
        env['SECURE_HSTS_INCLUDE_SUBDOMAINS'] = 'true'
        with mock.patch.dict(os.environ, env, clear=False):
            mod = importlib.import_module('mvp_project.settings_production')
            importlib.reload(mod)
        self.assertEqual(mod.SECURE_HSTS_SECONDS, 3600)
        self.assertTrue(mod.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertFalse(mod.SECURE_HSTS_PRELOAD)

    def test_firma_meta_exigida_si_el_env_no_la_apaga(self):
        with mock.patch.dict(os.environ, _ENV_OK, clear=False):
            os.environ.pop('WHATSAPP_REQUIRE_SIGNATURE', None)
            mod = importlib.import_module('mvp_project.settings_production')
            importlib.reload(mod)
        self.assertTrue(mod.WHATSAPP_REQUIRE_SIGNATURE)

    def test_csrf_cookie_no_httponly(self):
        with mock.patch.dict(os.environ, _ENV_OK, clear=False):
            mod = importlib.import_module('mvp_project.settings_production')
            importlib.reload(mod)
        self.assertFalse(mod.CSRF_COOKIE_HTTPONLY)
