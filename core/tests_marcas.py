"""Lector único de marcas: mismas reglas que tenían las copias de envío y pasos."""
from django.test import SimpleTestCase

from core.conversacion.marcas import PAUSA, PLANTILLA, TEXTO, Parte, es_marcado, partes, separar_media


class MarcasTests(SimpleTestCase):
    def test_solo_cuenta_si_empieza_con_la_marca(self):
        self.assertTrue(es_marcado('[MULTI_MSG]a'))
        self.assertFalse(es_marcado('hola [MULTI_MSG]'))
        self.assertFalse(es_marcado(None))

    def test_partes_en_orden_sin_vacias(self):
        self.assertEqual(
            partes('[MULTI_MSG] Uno [SEP][SEP]  [SEP]Dos'),
            [Parte(TEXTO, texto='Uno'), Parte(TEXTO, texto='Dos')],
        )

    def test_pausa_solo_si_la_parte_es_la_marca_completa(self):
        self.assertEqual(partes('[MULTI_MSG][DELAY:3]'), [Parte(PAUSA, segundos=3)])
        self.assertEqual(partes('[MULTI_MSG][DELAY:3] y texto')[0].tipo, TEXTO)

    def test_plantilla_conserva_texto_y_sid(self):
        parte = partes('[MULTI_MSG][SEND_TEMPLATE:HXab12]')[0]
        self.assertEqual((parte.tipo, parte.sid, parte.texto), (PLANTILLA, 'HXab12', '[SEND_TEMPLATE:HXab12]'))
        self.assertEqual(partes('[MULTI_MSG][SEND_TEMPLATE:malo]')[0].sid, '')

    def test_media_sale_de_la_parte(self):
        self.assertEqual(
            partes('[MULTI_MSG][MEDIA:https://x/a.jpg] Mire'),
            [Parte(TEXTO, texto='Mire', media='https://x/a.jpg')],
        )
        self.assertEqual(separar_media('[MEDIA: ] solo'), ('solo', None))
        self.assertEqual(separar_media('sin media'), ('sin media', None))

    def test_la_marca_de_inicio_se_quita_una_vez(self):
        self.assertEqual(partes('[MULTI_MSG]a[MULTI_MSG]b')[0].texto, 'a[MULTI_MSG]b')
