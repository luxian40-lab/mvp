from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from core.drip_schedule import (
    format_mensaje_bloqueo_calendario_modulo,
    format_mensaje_bloqueo_drip,
)
from core.modulo_publicacion import format_mensaje_bloqueo_contenido_pendiente
from core.tutor_ia_modulo import limpiar_emojis


class BloqueoModuloSinEmojisTests(TestCase):
    """Los avisos de módulo pausado/bloqueado siguen la misma regla que los retos."""

    def _mensajes(self):
        return {
            'drip': format_mensaje_bloqueo_drip(date.today() + timedelta(days=2)),
            'calendario': format_mensaje_bloqueo_calendario_modulo(
                timezone.now() + timedelta(days=2)
            ),
            'pausado': format_mensaje_bloqueo_contenido_pendiente(),
        }

    def test_ningun_mensaje_de_bloqueo_trae_emojis(self):
        for nombre, mensaje in self._mensajes().items():
            with self.subTest(mensaje=nombre):
                self.assertEqual(mensaje, limpiar_emojis(mensaje))
                self.assertNotIn('🌱', mensaje)

    def test_se_conserva_el_tono_y_la_informacion(self):
        for nombre, mensaje in self._mensajes().items():
            with self.subTest(mensaje=nombre):
                self.assertTrue(mensaje.startswith('*¡Excelente energía!*'))
                self.assertIn('repasa el material del módulo', mensaje)
