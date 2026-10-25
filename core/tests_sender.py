"""B2: el Sender envía por el phone id y la WABA de su línea, sin reemplazar el Client."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.lineas.sender import MetaSender, TwilioSender, sender_de_linea
from core.models import WhatsappLog

LINEAS = 'PN_UNO|+573000000001|Principal;PN_DOS|+573000000002|Segunda|cursos'


def _respuesta_graph(wamid='wamid.ok'):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {'messages': [{'id': wamid}]}
    return resp


@override_settings(
    WHATSAPP_TOKEN='token-prueba',
    META_LINEAS=LINEAS,
    WHATSAPP_BUSINESS_ACCOUNT_ID='WABA_UNO',
    WHATSAPP_BUSINESS_ACCOUNT_ID_2='WABA_DOS',
)
class MetaSenderTests(TestCase):
    def test_texto_sale_por_el_phone_id_de_la_linea(self):
        with patch('core.lineas.envio.requests.post', return_value=_respuesta_graph()) as post:
            res = MetaSender('PN_DOS').texto('+573001112233', 'Hola')
        self.assertTrue(res['success'])
        self.assertIn('/PN_DOS/messages', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['json']['text']['body'], 'Hola')
        log = WhatsappLog.objects.get(mensaje_id='wamid.ok')
        self.assertEqual(log.phone_id, 'PN_DOS')

    def test_dos_lineas_en_el_mismo_hilo_no_se_mezclan(self):
        with patch('core.lineas.envio.requests.post', return_value=_respuesta_graph()) as post:
            MetaSender('PN_UNO').texto('+573001112233', 'a')
            MetaSender('PN_DOS').texto('+573001112233', 'b')
            MetaSender('PN_UNO').texto('+573001112233', 'c')
        urls = [c.args[0].rsplit('/', 2)[-2] for c in post.call_args_list]
        self.assertEqual(urls, ['PN_UNO', 'PN_DOS', 'PN_UNO'])

    def test_no_deja_el_phone_id_puesto_al_salir(self):
        from core.sandbox_canal import phone_id_de_salida, salida_por_phone_id

        with salida_por_phone_id('PN_UNO'):
            with patch('core.lineas.envio.requests.post', return_value=_respuesta_graph()):
                MetaSender('PN_DOS').texto('+573001112233', 'x')
            self.assertEqual(phone_id_de_salida(), 'PN_UNO')

    def test_botones_y_plantilla_usan_la_linea(self):
        with patch('core.lineas.envio.requests.post', return_value=_respuesta_graph()) as post:
            MetaSender('PN_DOS').botones('+573001112233', 'Elija', [('si', 'Sí')])
            MetaSender('PN_DOS').plantilla('+573001112233', 'aviso', {'1': 'Ana'})
        self.assertEqual(len(post.call_args_list), 2)
        for llamada in post.call_args_list:
            self.assertIn('/PN_DOS/messages', llamada.args[0])
        self.assertEqual(post.call_args_list[1].kwargs['json']['type'], 'template')

    def test_sender_de_linea_trae_la_waba_de_cada_linea(self):
        uno = sender_de_linea('PN_UNO')
        dos = sender_de_linea('PN_DOS')
        self.assertEqual((uno.canal, uno.phone_id, uno.waba_id), ('meta', 'PN_UNO', 'WABA_UNO'))
        self.assertEqual((dos.canal, dos.phone_id, dos.waba_id), ('meta', 'PN_DOS', 'WABA_DOS'))

    def test_sender_de_linea_sin_phone_id_usa_el_del_turno(self):
        from core.sandbox_canal import salida_por_phone_id

        with salida_por_phone_id('PN_DOS'):
            self.assertEqual(sender_de_linea().phone_id, 'PN_DOS')


@override_settings(SANDBOX_WHATSAPP_PHONE_ID='', WHATSAPP_PHONE_ID='', META_LINEAS='')
class TwilioSenderTests(TestCase):
    def test_sin_phone_id_queda_el_legado(self):
        self.assertIsInstance(sender_de_linea(''), TwilioSender)

    def test_texto_delega_en_enviar_whatsapp_twilio(self):
        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}) as envio:
            TwilioSender('whatsapp:+14155238886').texto('+573001112233', 'Hola', agente='prueba')
        envio.assert_called_once_with(
            '+573001112233',
            'Hola',
            media_url=None,
            from_number='whatsapp:+14155238886',
            agente_evento='prueba',
        )

    def test_botones_salen_como_texto(self):
        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}) as envio:
            TwilioSender().botones('+573001112233', 'Elija', [('si', 'Sí'), ('no', 'No')])
        self.assertEqual(envio.call_args.args[1], 'Elija\n\n• Sí\n• No')

    def test_plantilla_delega_en_content_api(self):
        with patch('core.whatsapp_service.enviar_template_twilio', return_value={'success': True}) as envio:
            TwilioSender().plantilla('+573001112233', 'HX123', {'1': 'Ana'})
        envio.assert_called_once_with('+573001112233', 'HX123', {'1': 'Ana'})
