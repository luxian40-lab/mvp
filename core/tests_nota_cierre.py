"""La nota de cierre es un entero de 1 a 10, guardado tal cual."""
from django.test import SimpleTestCase

from core.conversacion.estados.reto import nota_de


class NotaDeTests(SimpleTestCase):
    def test_toma_el_numero_entero(self):
        self.assertEqual(nota_de('8'), 8)
        self.assertEqual(nota_de(' 10 '), 10)
        self.assertEqual(nota_de('1/10'), 1)
        self.assertIsNone(nota_de('0'))
        self.assertIsNone(nota_de('11'))
        self.assertIsNone(nota_de('hola'))
        self.assertIsNone(nota_de('tengo 2'))
