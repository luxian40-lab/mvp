"""Tope duro de audio e imagen en la subida del admin. El aviso de 3G no cambia."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.admin._common import _rechazar_si_supera_tope_meta


class TopeMediaMetaTests(TestCase):
    def test_imagen_sobre_5mb_no_pasa(self):
        with self.assertRaises(ValidationError):
            _rechazar_si_supera_tope_meta(b'x' * (5 * 1024 * 1024 + 1), 'foto.png')

    def test_audio_de_16mb_pasa(self):
        _rechazar_si_supera_tope_meta(b'x' * (16 * 1024 * 1024), 'nota.mp3')

    def test_audio_sobre_16mb_no_pasa(self):
        with self.assertRaises(ValidationError):
            _rechazar_si_supera_tope_meta(b'x' * (16 * 1024 * 1024 + 1), 'nota.mp3')
