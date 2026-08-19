"""CSRF en producción: orígenes eki siempre presentes."""
import os
import importlib
from unittest import mock

from django.test import SimpleTestCase


class ProductionCsrfOriginsTests(SimpleTestCase):
    def test_csrf_trusted_origins_incluye_admin(self):
        with mock.patch.dict(os.environ, {'CSRF_TRUSTED_ORIGINS': ''}, clear=False):
            mod = importlib.import_module('mvp_project.settings_production')
            importlib.reload(mod)
            origins = mod.CSRF_TRUSTED_ORIGINS
        self.assertIn('https://admin.eki.technology', origins)
        self.assertIn('https://app.eki.technology', origins)
        self.assertTrue(
            any('elasticbeanstalk.com' in o for o in origins),
            origins,
        )

    def test_csrf_cookie_no_httponly(self):
        mod = importlib.import_module('mvp_project.settings_production')
        self.assertFalse(mod.CSRF_COOKIE_HTTPONLY)
