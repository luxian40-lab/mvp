"""Saludo formal Inicio admin (por hora)."""

from django.test import SimpleTestCase

from core.templatetags.eki_admin import saludo_por_hora


class EkiAdminSaludoTests(SimpleTestCase):
    def test_manana(self):
        self.assertEqual(saludo_por_hora('Ana', 8), 'Buenos días, Ana')
        self.assertEqual(saludo_por_hora('Ana', 5), 'Buenos días, Ana')

    def test_tarde(self):
        self.assertEqual(saludo_por_hora('Ana', 12), 'Buenas tardes, Ana')
        self.assertEqual(saludo_por_hora('Ana', 18), 'Buenas tardes, Ana')

    def test_noche(self):
        self.assertEqual(saludo_por_hora('Ana', 19), 'Buenas noches, Ana')
        self.assertEqual(saludo_por_hora('Ana', 2), 'Buenas noches, Ana')

    def test_nombre_vacio(self):
        self.assertEqual(saludo_por_hora('', 10), 'Buenos días, equipo')
