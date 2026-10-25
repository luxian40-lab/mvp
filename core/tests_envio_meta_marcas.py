"""enviar_meta parte el texto armado por el curso: nadie ve [MULTI_MSG] ni [SEP]."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.lineas.envio import enviar_meta

TEL = '573001110050'


@override_settings(WHATSAPP_TOKEN='tok', WHATSAPP_PHONE_ID='100000000000001', META_LINEAS='')
class EnvioMetaMarcasTests(TestCase):
    def setUp(self):
        self.enviados = []

        def graph(payload, agente=''):
            self.enviados.append(payload)
            return {'success': True, 'mensaje_id': f'wamid.{len(self.enviados)}', 'response': ''}

        self.graph = patch('core.lineas.envio._post_graph', side_effect=graph).start()
        self.pausas = patch('core.lineas.envio.time.sleep').start()
        self.addCleanup(patch.stopall)

    def _textos(self):
        return [p.get('text', {}).get('body') or p.get(p['type'], {}).get('caption', '') for p in self.enviados]

    def test_multi_msg_sale_como_un_mensaje_por_parte(self):
        enviar_meta(TEL, '[MULTI_MSG]Lineal1\n\nMódulo 1[SEP]Responda *listo*')
        self.assertEqual(self._textos(), ['Lineal1\n\nMódulo 1', 'Responda *listo*'])
        self.assertFalse([t for t in self._textos() if '[MULTI_MSG]' in t or '[SEP]' in t])

    def test_delay_pausa_sin_mandar_mensaje(self):
        enviar_meta(TEL, '[MULTI_MSG]Uno[SEP][DELAY:3][SEP]Dos')
        self.assertEqual(self._textos(), ['Uno', 'Dos'])
        self.pausas.assert_any_call(3)

    def test_media_de_una_parte_va_como_adjunto(self):
        enviar_meta(TEL, '[MULTI_MSG]Intro[SEP][MEDIA:https://cdn.example.com/a.jpg] Mire la foto')
        self.assertEqual(self.enviados[1]['type'], 'image')
        self.assertEqual(self.enviados[1]['image']['link'], 'https://cdn.example.com/a.jpg')
        self.assertEqual(self.enviados[1]['image']['caption'], 'Mire la foto')

    def test_plantilla_twilio_se_omite(self):
        enviar_meta(TEL, '[MULTI_MSG]Uno[SEP][SEND_TEMPLATE:HXabc123][SEP]Dos')
        self.assertEqual(self._textos(), ['Uno', 'Dos'])

    def test_boton_continuemos_de_la_ultima_parte_sale_como_boton(self):
        enviar_meta(TEL, '[MULTI_MSG]Módulo 2[SEP]Pulse continuar[SEND_BUTTON:continuemos]')
        self.assertEqual(self.enviados[0]['type'], 'text')
        self.assertEqual(self.enviados[1]['type'], 'interactive')

    def test_si_una_parte_falla_no_sigue(self):
        self.graph.side_effect = lambda payload, agente='': {'success': False, 'mensaje_id': None, 'response': 'x'}
        resultado = enviar_meta(TEL, '[MULTI_MSG]Uno[SEP]Dos')
        self.assertFalse(resultado['success'])
        self.assertEqual(self.graph.call_count, 1)

    def test_texto_sin_marcas_no_cambia(self):
        enviar_meta(TEL, 'Hola')
        self.assertEqual(self._textos(), ['Hola'])
