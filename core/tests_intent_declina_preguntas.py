"""Detector: el estudiante declina preguntas al Compañero (pausa pre-reto)."""
from django.test import SimpleTestCase

from core.intent_detector import mensaje_declina_preguntas, mensaje_indica_listo


class MensajeDeclinaPreguntasTests(SimpleTestCase):
    def test_oscar_no_tengo_preguntas(self):
        self.assertTrue(mensaje_declina_preguntas('No tengo preguntas.'))
        self.assertTrue(mensaje_declina_preguntas('No tengo preguntas'))

    def test_variantes_cortas(self):
        for msg in (
            'no tengo pregunta',
            'no tengo más preguntas',
            'no tengo mas preguntas',
            'no tengo dudas',
            'no tengo duda',
            'sin preguntas',
            'sin dudas',
            'ninguna',
            'ninguna pregunta',
            'ninguna duda',
            'nada que preguntar',
            'no quiero preguntar',
            'no hay preguntas',
        ):
            with self.subTest(msg=msg):
                self.assertTrue(mensaje_declina_preguntas(msg), msg)

    def test_pregunta_real_no_declina(self):
        self.assertFalse(mensaje_declina_preguntas('¿qué es el interés compuesto?'))
        self.assertFalse(
            mensaje_declina_preguntas(
                'no tengo preguntas del módulo 4 pero sí sobre interés compuesto'
            )
        )

    def test_listo_continuar_no_son_declina(self):
        self.assertFalse(mensaje_declina_preguntas('listo'))
        self.assertFalse(mensaje_declina_preguntas('continuemos'))
        self.assertTrue(mensaje_indica_listo('listo'))
        self.assertTrue(mensaje_indica_listo('continuemos'))

    def test_vacio_y_audio_fallido(self):
        self.assertFalse(mensaje_declina_preguntas(''))
        self.assertFalse(mensaje_declina_preguntas(None))
        self.assertFalse(mensaje_declina_preguntas('[AUDIO_NO_TRANSCRITO]'))
