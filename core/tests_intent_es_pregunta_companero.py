"""Detector: ¿parece pregunta? / cierre corto en pausa del Compañero."""
from django.test import SimpleTestCase

from core.conversacion.intent_detector import (
    mensaje_cierre_corto_companero,
    mensaje_declina_preguntas,
    mensaje_parece_pregunta_companero,
)


class MensajeParecePreguntaCompaneroTests(SimpleTestCase):
    def test_pregunta_con_signos(self):
        self.assertTrue(mensaje_parece_pregunta_companero('¿qué es el interés compuesto?'))
        self.assertTrue(mensaje_parece_pregunta_companero('que es un CDT?'))

    def test_pregunta_con_interrogativa(self):
        self.assertTrue(mensaje_parece_pregunta_companero('cómo mido el éxito de una inversión'))
        self.assertTrue(mensaje_parece_pregunta_companero('por qué importa el interés compuesto'))

    def test_pedido_explicar(self):
        self.assertTrue(mensaje_parece_pregunta_companero('explíqueme el módulo de deudas'))
        self.assertTrue(mensaje_parece_pregunta_companero('no entiendo el interés compuesto todavía'))

    def test_duda_en_prosa_con_senal(self):
        self.assertTrue(
            mensaje_parece_pregunta_companero('el interés compuesto no me quedó claro del todo')
        )

    def test_cierre_y_declina_no_son_pregunta(self):
        self.assertFalse(mensaje_parece_pregunta_companero('No tengo preguntas.'))
        self.assertFalse(mensaje_parece_pregunta_companero('todo bien'))
        self.assertFalse(mensaje_parece_pregunta_companero('nada'))

    def test_ambiguo_sin_senales(self):
        self.assertFalse(mensaje_parece_pregunta_companero('bla bla'))
        self.assertFalse(mensaje_parece_pregunta_companero('interes compuesto'))


class MensajeCierreCortoCompaneroTests(SimpleTestCase):
    def test_cierres(self):
        for msg in (
            'nada',
            'todo bien',
            'gracias',
            'perfecto',
            'así está',
            'asi esta',
            'ya está',
            'listo gracias',
        ):
            with self.subTest(msg=msg):
                self.assertTrue(mensaje_cierre_corto_companero(msg), msg)

    def test_no_cierra_pregunta(self):
        self.assertFalse(mensaje_cierre_corto_companero('¿qué es el interés compuesto?'))
        self.assertFalse(mensaje_cierre_corto_companero('el interés compuesto no me quedó claro'))

    def test_declina_sigue_aparte(self):
        self.assertTrue(mensaje_declina_preguntas('No tengo preguntas.'))
        # cierre corto no sustituye declina; ambos pueden ser True en 'nada'
        self.assertTrue(mensaje_cierre_corto_companero('nada'))
