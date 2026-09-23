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
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            with self.assertRaises(ValueError) as ctx:
                validar_modelo_ia_disponible('gpt-4o-mini')
        self.assertIn('OPENAI_API_KEY', str(ctx.exception))


class EstructuraCursoIATest(TestCase):
    def test_extrae_json_con_preambulo(self):
        from core.utils_ia import _extraer_json_objeto

        data = _extraer_json_objeto('Aquí va:\n```json\n{"titulo": "Café"}\n```')
        self.assertEqual(data['titulo'], 'Café')

    def test_guardar_crea_pasos_y_no_publica_wa(self):
        from core.models import Cliente, Modulo, PasoModulo, PreguntaModulo
        from core.utils_ia import guardar_curso_desde_estructura

        org = Cliente.objects.create(
            nombre='Org IA',
            nit='800222333-1',
            activo=True,
            contacto_principal='x',
            email='ia@eki.co',
            telefono='57300',
        )
        curso = guardar_curso_desde_estructura(
            {
                'titulo': 'Ventas en la finca',
                'descripcion': 'Cómo cobrar mejor.',
                'duracion_estimada': '3 semanas',
                'modulos': [
                    {
                        'nombre': 'Precio',
                        'descripcion': 'Margen',
                        'lecciones': [
                            {'titulo': 'Costo', 'contenido': 'Anote el costo antes de bajar el precio.'},
                            {'titulo': 'Vacía', 'contenido': ''},
                        ],
                        'mini_examen': [
                            {
                                'texto': '¿Qué mira primero?',
                                'opciones': [
                                    {'texto': 'El costo', 'es_correcta': True},
                                    {'texto': 'El vecino', 'es_correcta': False},
                                ],
                                'explicacion': 'Sin costo no hay margen.',
                            }
                        ],
                    }
                ],
            },
            org,
            'prompt',
        )
        self.assertFalse(curso.activo)
        mod = Modulo.objects.get(curso=curso)
        self.assertFalse(mod.publicado_wa)
        self.assertEqual(PasoModulo.objects.filter(modulo=mod).count(), 1)
        preg = PreguntaModulo.objects.get(modulo=mod)
        self.assertEqual(preg.respuesta_correcta, 'A')
