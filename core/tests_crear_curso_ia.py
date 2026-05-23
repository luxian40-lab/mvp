"""Tests validación modelos IA en crear curso."""
from django.test import TestCase, override_settings

from core.utils_ia import validar_modelo_ia_disponible


class ValidarModeloIATest(TestCase):
    @override_settings(OPENAI_API_KEY='sk-test')
    def test_gemini_arroja_error_claro(self):
        with self.assertRaises(ValueError) as ctx:
            validar_modelo_ia_disponible('gemini-pro')
        self.assertIn('no está disponible', str(ctx.exception))

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_openai_ok(self):
        validar_modelo_ia_disponible('gpt-4o-mini')

    @override_settings(OPENAI_API_KEY='')
    def test_sin_key_arroja_error(self):
        with self.assertRaises(ValueError) as ctx:
            validar_modelo_ia_disponible('gpt-4o-mini')
        self.assertIn('OPENAI_API_KEY', str(ctx.exception))
