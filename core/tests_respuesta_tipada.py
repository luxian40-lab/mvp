"""Respuesta tipada: partes en orden; el texto con marcas es solo el formato legado."""
from django.test import SimpleTestCase

from core.conversacion.contexto import CORTAR, Respuesta
from core.conversacion.marcas import PAUSA, PLANTILLA, TEXTO, Parte, componer, partes

LEGADOS = [
    '[MULTI_MSG]Hola[SEP]Segundo',
    '[MULTI_MSG]Uno[SEP][DELAY:3][SEP]Dos',
    '[MULTI_MSG]Mire esto\n\n[MEDIA:https://x.test/a.mp4][SEP]Listo',
    '[MULTI_MSG][MEDIA:https://x.test/b.jpg]',
    '[MULTI_MSG]Antes[SEP][SEND_TEMPLATE:HXabc123][SEP]Después',
    '[MULTI_MSG]  con espacios  [SEP][SEP]  [SEP]fin',
]


class ComponerTests(SimpleTestCase):
    def test_leer_lo_compuesto_da_las_mismas_partes(self):
        for legado in LEGADOS:
            ps = partes(legado)
            self.assertEqual(partes(componer(ps)), ps, legado)

    def test_un_texto_solo_sale_sin_marcas(self):
        self.assertEqual(componer([Parte(TEXTO, texto='Hola')]), 'Hola')

    def test_media_pausa_y_plantilla(self):
        texto = componer([
            Parte(TEXTO, texto='Mire', media='https://x.test/v.mp4'),
            Parte(PAUSA, segundos=2),
            Parte(PLANTILLA, sid='HXabc'),
        ])
        self.assertEqual(
            partes(texto),
            [
                Parte(TEXTO, texto='Mire', media='https://x.test/v.mp4'),
                Parte(PAUSA, segundos=2),
                Parte(PLANTILLA, texto='[SEND_TEMPLATE:HXabc]', sid='HXabc'),
            ],
        )

    def test_sin_partes_es_vacio(self):
        self.assertEqual(componer([]), '')


class RespuestaTipadaTests(SimpleTestCase):
    def test_texto_legado_sigue_igual(self):
        r = Respuesta(texto='[MULTI_MSG]a[SEP]b')
        self.assertEqual(r.texto, '[MULTI_MSG]a[SEP]b')
        self.assertEqual(r.como_partes(), partes('[MULTI_MSG]a[SEP]b'))
        self.assertFalse(r.cortar)

    def test_de_partes_deja_el_texto_que_lee_el_cuerpo(self):
        r = Respuesta.de_partes(Parte(TEXTO, texto='a'), Parte(PAUSA, segundos=1), Parte(TEXTO, texto='b'))
        self.assertEqual(r.texto, '[MULTI_MSG]a[SEP][DELAY:1][SEP]b')
        self.assertEqual(
            r.como_partes(),
            [Parte(TEXTO, texto='a'), Parte(PAUSA, segundos=1), Parte(TEXTO, texto='b')],
        )

    def test_texto_plano_es_una_parte(self):
        self.assertEqual(Respuesta(texto=' Hola ').como_partes(), [Parte(TEXTO, texto='Hola')])
        self.assertEqual(Respuesta(texto='').como_partes(), [])
        self.assertEqual(Respuesta().como_partes(), [])

    def test_cortar_no_cambia(self):
        self.assertTrue(CORTAR.cortar)
        self.assertIsNone(CORTAR.texto)
        self.assertEqual(Respuesta(texto='x'), Respuesta(texto='x'))
