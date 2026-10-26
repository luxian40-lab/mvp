"""Parser único de [MULTI_MSG] / [SEP]: mismas partes que las copias que reemplaza."""
from django.test import SimpleTestCase

from core.conversacion.multimsg import partes_multimsg, partir_sep

CASOS = [
    '',
    'hola',
    '[MULTI_MSG]',
    '[MULTI_MSG]uno',
    '[MULTI_MSG]uno[SEP]dos',
    '[MULTI_MSG]uno[SEP][SEP]dos[SEP]',
    '[MULTI_MSG][MULTI_MSG]uno[SEP]dos',
    'uno[SEP]dos',
    ' [MULTI_MSG]uno',
    '[MULTI_MSG] uno [SEP] [DELAY:2] [SEP]tres',
]


class ParserUnicoTests(SimpleTestCase):
    def test_partir_sep_es_split(self):
        for texto in CASOS:
            self.assertEqual(partir_sep(texto), texto.split('[SEP]'), texto)

    def test_partes_quita_la_marca_solo_al_inicio(self):
        for texto in CASOS:
            viejo = texto[len('[MULTI_MSG]'):] if texto.startswith('[MULTI_MSG]') else texto
            self.assertEqual(partes_multimsg(texto), viejo.split('[SEP]'), texto)

    def test_partes_igual_a_replace_cuando_empieza_con_la_marca(self):
        for texto in CASOS:
            if texto.startswith('[MULTI_MSG]'):
                self.assertEqual(
                    partes_multimsg(texto), texto.replace('[MULTI_MSG]', '', 1).split('[SEP]'), texto,
                )
