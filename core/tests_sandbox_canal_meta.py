"""Sandbox canal Meta: inbound adapter + menú/agentes/cursos sin Twilio HTTP."""

import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from core.sandbox_canal import (
    enviar_sandbox,
    es_inbound_twilio_http,
    inbound_desde_meta_message,
    inbound_es_meta,
    phone_id_es_sandbox,
    sandbox_via_meta,
    to_es_sandbox,
)
from core.sandbox_menu import dispatch_sandbox_menu, es_destino_sandbox


def _meta_envelope(message, *, phone_id='111222333', display='573009998888'):
    return {
        'object': 'whatsapp_business_account',
        'entry': [{
            'id': 'WABA',
            'changes': [{
                'field': 'messages',
                'value': {
                    'messaging_product': 'whatsapp',
                    'metadata': {
                        'display_phone_number': display,
                        'phone_number_id': phone_id,
                    },
                    'messages': [message],
                },
            }],
        }],
    }


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='573009998888',
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    WHATSAPP_VERIFY_TOKEN='eki_test_verify',
    BOT_COMERCIAL_WHATSAPP_NUMBER='573001111111',
)
class SandboxCanalMetaAdapterTests(TestCase):
    def test_texto_meta_a_inbound_canonico(self):
        inbound = inbound_desde_meta_message(
            {'from': '573001234567', 'id': 'wamid.abc', 'type': 'text', 'text': {'body': 'hola'}},
            {'metadata': {'display_phone_number': '573009998888', 'phone_number_id': '111222333'}},
        )
        self.assertEqual(inbound['Body'], 'hola')
        self.assertEqual(inbound['MessageSid'], 'wamid.abc')
        self.assertTrue(inbound['From'].endswith('573001234567'))
        self.assertTrue(inbound['To'].endswith('573009998888'))
        self.assertTrue(inbound_es_meta(inbound))
        self.assertTrue(phone_id_es_sandbox(inbound))
        self.assertTrue(es_destino_sandbox(inbound))

    def test_boton_interactivo_pasa_id_al_body(self):
        inbound = inbound_desde_meta_message(
            {
                'from': '573001234567',
                'id': 'wamid.btn',
                'type': 'interactive',
                'interactive': {'button_reply': {'id': 'acepto', 'title': 'Acepto'}},
            },
            {'metadata': {'display_phone_number': '573009998888', 'phone_number_id': '111222333'}},
        )
        self.assertEqual(inbound['Body'], 'acepto')

    def test_audio_meta_media_id_no_url_twilio(self):
        inbound = inbound_desde_meta_message(
            {
                'from': '573001234567',
                'id': 'wamid.aud',
                'type': 'audio',
                'audio': {'id': 'MEDIAID99', 'mime_type': 'audio/ogg'},
            },
            {'metadata': {'display_phone_number': '573009998888', 'phone_number_id': '111222333'}},
        )
        self.assertEqual(inbound['NumMedia'], '1')
        self.assertEqual(inbound['MediaUrl0'], 'MEDIAID99')
        self.assertFalse(inbound['MediaUrl0'].startswith('http'))

    def test_twilio_http_no_es_sandbox_si_proveedor_meta(self):
        twilio = {
            'From': 'whatsapp:+573001234567',
            'To': 'whatsapp:+573009998888',
            'Body': 'hola',
            'AccountSid': 'ACxxxxxxxx',
            'MessageSid': 'SMxxxxxxxx',
        }
        self.assertTrue(es_inbound_twilio_http(twilio))
        self.assertTrue(to_es_sandbox(twilio))
        self.assertFalse(es_destino_sandbox(twilio))

    def test_dict_de_test_sin_accountsid_sigue_siendo_sandbox(self):
        payload = {
            'From': 'whatsapp:+573001234567',
            'To': 'whatsapp:+573009998888',
            'Body': 'hola',
        }
        self.assertFalse(es_inbound_twilio_http(payload))
        self.assertTrue(es_destino_sandbox(payload))

    def test_sandbox_via_meta_default(self):
        self.assertTrue(sandbox_via_meta())


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='573009998888',
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
)
class SandboxCanalMetaSendTests(TestCase):
    @patch('core.sandbox_canal.requests.post')
    def test_enviar_sandbox_usa_graph_no_twilio(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'messages': [{'id': 'wamid.out'}]}
        with patch('core.utils.enviar_whatsapp_twilio') as mock_tw:
            result = enviar_sandbox('573001234567', 'hola sandbox')
        self.assertTrue(result.get('success'))
        self.assertEqual(result.get('mensaje_id'), 'wamid.out')
        mock_tw.assert_not_called()
        mock_post.assert_called_once()
        _args, kwargs = mock_post.call_args
        body = kwargs.get('json') or {}
        self.assertEqual(body.get('messaging_product'), 'whatsapp')
        self.assertEqual(body.get('to'), '573001234567')
        self.assertEqual(body.get('type'), 'text')

    def test_dispatch_menu_no_llama_twilio(self):
        with patch('core.sandbox_canal.enviar_meta', return_value={'success': True, 'mensaje_id': 'x'}) as send:
            out = dispatch_sandbox_menu({
                'From': 'whatsapp:+573001234590',
                'To': 'whatsapp:+573009998888',
                'Body': 'hola',
                '_eki_proveedor': 'meta',
                '_eki_phone_number_id': '111222333',
            })
        self.assertEqual(out, 'handled')
        self.assertTrue(send.called)


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='573009998888',
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    WHATSAPP_VERIFY_TOKEN='eki_test_verify',
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
)
class SandboxCanalMetaWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_get_verify_token(self):
        resp = self.client.get(
            '/webhook/whatsapp/',
            {'hub.mode': 'subscribe', 'hub.verify_token': 'eki_test_verify', 'hub.challenge': 'reto99'},
            secure=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), 'reto99')

    def test_post_meta_hola_dispara_menu_no_legacy(self):
        payload = _meta_envelope(
            {'from': '573001234591', 'id': 'wamid.in1', 'type': 'text', 'text': {'body': 'hola'}},
        )
        with patch('core.sandbox_menu.enviar_menu_sandbox', return_value={'success': True}) as menu, \
                patch('core.views._procesar_meta_webhook') as legacy:
            resp = self.client.post(
                '/webhook/whatsapp/',
                data=json.dumps(payload),
                content_type='application/json',
                secure=True,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(menu.called)
        legacy.assert_not_called()

    def test_post_meta_cursos_listo_usa_pipeline_edu_con_flag_meta(self):
        from core.models import SandboxCanalSesion
        from core.sandbox_menu import MODO_CURSOS

        SandboxCanalSesion.objects.create(telefono='573001234592', modo=MODO_CURSOS)
        payload = _meta_envelope(
            {'from': '573001234592', 'id': 'wamid.in2', 'type': 'text', 'text': {'body': 'listo'}},
        )
        with patch('core.views._procesar_twilio_webhook', return_value=None) as edu, \
                patch('core.views._procesar_meta_webhook') as legacy:
            resp = self.client.post(
                '/webhook/whatsapp/',
                data=json.dumps(payload),
                content_type='application/json',
                secure=True,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(edu.called)
        inbound = edu.call_args[0][0]
        self.assertEqual(inbound.get('_eki_proveedor'), 'meta')
        self.assertEqual((inbound.get('Body') or '').lower(), 'listo')
        legacy.assert_not_called()

    def test_post_meta_agronomo_enruta_nat(self):
        from core.models import SandboxCanalSesion
        from core.sandbox_menu import MODO_NAT

        SandboxCanalSesion.objects.create(telefono='573001234594', modo=MODO_NAT)
        payload = _meta_envelope(
            {'from': '573001234594', 'id': 'wamid.in3', 'type': 'text', 'text': {'body': 'mancha en tomate'}},
        )
        with patch('core.views._encolar_bot_comercial_si_async', return_value=False), \
                patch('core.bot_comercial.webhook._procesar_bot_comercial_twilio_webhook') as nat, \
                patch('core.views._procesar_meta_webhook') as legacy:
            resp = self.client.post(
                '/webhook/whatsapp/',
                data=json.dumps(payload),
                content_type='application/json',
                secure=True,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(nat.called)
        inbound = nat.call_args[0][0]
        self.assertEqual(inbound.get('_eki_proveedor'), 'meta')
        self.assertIn('tomate', (inbound.get('Body') or '').lower())
        legacy.assert_not_called()

    def test_post_twilio_sandbox_se_ignora_cuando_canal_es_meta(self):
        with patch('core.views._procesar_twilio_webhook') as edu, \
                patch('core.sandbox_menu.dispatch_sandbox_menu') as disp:
            resp = self.client.post(
                '/webhook/whatsapp/',
                {
                    'From': 'whatsapp:+573001234593',
                    'To': 'whatsapp:+573009998888',
                    'Body': 'hola',
                    'AccountSid': 'ACtest',
                    'MessageSid': 'SMtestignore',
                },
                secure=True,
            )
        self.assertEqual(resp.status_code, 200)
        disp.assert_not_called()
        edu.assert_not_called()
