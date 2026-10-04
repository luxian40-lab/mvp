"""El mensaje 13 se descarta y el aviso sale una sola vez."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.antiflood import flood_excedido


class _Redis:
    def __init__(self):
        self.contadores = {}
        self.avisos = set()

    def incr(self, clave):
        self.contadores[clave] = self.contadores.get(clave, 0) + 1
        return self.contadores[clave]

    def expire(self, clave, segundos):
        return True

    def set(self, clave, valor, nx=False, ex=None):
        if nx and clave in self.avisos:
            return None
        self.avisos.add(clave)
        return True


@override_settings(LINEA_MAX_MSG_MIN=12)
class AntifloodTests(SimpleTestCase):
    def test_el_trece_avisa_una_vez(self):
        falso = _Redis()
        with patch('core.antiflood._cliente', return_value=falso):
            for _ in range(12):
                self.assertEqual(flood_excedido('573001112233'), (False, False))
            self.assertEqual(flood_excedido('573001112233'), (True, True))
            self.assertEqual(flood_excedido('573001112233'), (True, False))
        self.assertEqual(len(falso.avisos), 1)
