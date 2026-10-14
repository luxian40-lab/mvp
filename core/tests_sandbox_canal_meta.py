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
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=False,
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

    @patch('core.sandbox_canal.requests.post')
    def test_marcador_continuemos_sale_como_boton(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'messages': [{'id': 'wamid.btn'}]}
        result = enviar_sandbox('573001234567', 'Cuando termines.\n\n[SEND_BUTTON:continuemos]')
        self.assertTrue(result.get('success'))
        body = mock_post.call_args.kwargs.get('json') or {}
        self.assertEqual(body.get('type'), 'interactive')
        botones = body['interactive']['action']['buttons']
        self.assertEqual(botones[0]['reply']['id'], 'continuemos')
        self.assertEqual(botones[0]['reply']['title'], 'Continuemos')
        self.assertNotIn('listo', (body['interactive']['body']['text'] or '').lower())

    @patch('core.sandbox_canal.requests.post')
    def test_confirmacion_de_cedula_sale_con_botones(self, mock_post):
        from core.sandbox_canal import enviar_sandbox_template_fallback
        from core.whatsapp_service import TWILIO_CONTENT_SIDS

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'messages': [{'id': 'wamid.datos'}]}
        result = enviar_sandbox_template_fallback(
            '573001234567',
            TWILIO_CONTENT_SIDS['confirmar_datos_v2'],
            {
                '1': 'Julian Ramirez',
                '2': 'CC 1014310196',
                '3': 'REDDI-eki',
                '4': 'No registrada',
                '5': 'No registrado',
            },
        )
        self.assertTrue(result.get('success'))
        body = mock_post.call_args.kwargs.get('json') or {}
        self.assertEqual(body.get('type'), 'interactive')
        texto = body['interactive']['body']['text']
        self.assertIn('Julian Ramirez', texto)
        self.assertNotIn('Mensaje del curso', texto)
        botones = body['interactive']['action']['buttons']
        self.assertEqual(botones[0]['reply']['id'], 'si')
        self.assertEqual(botones[0]['reply']['title'], 'Están bien')
        self.assertEqual(botones[1]['reply']['id'], 'no')
        self.assertEqual(botones[1]['reply']['title'], 'Hay un error')

    def test_habeas_en_meta_sale_con_botones_aunque_el_sid_sea_otro(self):
        from core.models import Cliente, ConfiguracionGlobal
        from core.sandbox_canal import canal_sandbox_meta
        from core.whatsapp_service import enviar_habeas_data

        cliente = Cliente.objects.create(
            nombre='Org Habeas',
            contacto_principal='Ops',
            email='habeas@test.com',
            telefono='573001100099',
            content_sid_habeas_data_twilio='HXOTROHABEAS0001',
        )
        cfg = ConfiguracionGlobal.get_solo()
        cfg.content_sid_habeas_data_global = 'HXOTROHABEAS0001'
        cfg.save(update_fields=['content_sid_habeas_data_global', 'fecha_actualizacion'])
        with canal_sandbox_meta():
            with patch('core.sandbox_canal._post_graph', return_value={'success': True, 'mensaje_id': 'wamid.h'}) as post:
                result = enviar_habeas_data('573001234567', cliente=cliente)
        self.assertTrue(result.get('success'))
        payload = post.call_args[0][0]
        self.assertEqual(payload.get('type'), 'interactive')
        ids = [b['reply']['id'] for b in payload['interactive']['action']['buttons']]
        self.assertEqual(ids, ['acepto', 'no_acepto'])
        self.assertNotIn('Mensaje del curso', payload['interactive']['body']['text'])

    def test_dispatch_menu_no_llama_twilio(self):
        from core.models import SandboxCanalSesion

        SandboxCanalSesion.objects.create(telefono='573001234590', habeas_aceptado=True)
        with patch('core.sandbox_canal._post_graph', return_value={'success': True, 'mensaje_id': 'x'}) as send:
            with patch('core.utils.enviar_whatsapp_twilio') as mock_tw:
                out = dispatch_sandbox_menu({
                    'From': 'whatsapp:+573001234590',
                    'To': 'whatsapp:+573009998888',
                    'Body': 'hola',
                    '_eki_proveedor': 'meta',
                    '_eki_phone_number_id': '111222333',
                })
        self.assertEqual(out, 'handled')
        self.assertTrue(send.called)
        mock_tw.assert_not_called()
        body = send.call_args[0][0]
        self.assertEqual(body.get('type'), 'interactive')
        botones = body['interactive']['action']['buttons']
        self.assertEqual(botones[0]['reply']['id'], 'formacion')
        self.assertEqual(botones[1]['reply']['id'], 'asesoria')


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='573009998888',
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    WHATSAPP_APP_SECRET='',
    WHATSAPP_VERIFY_TOKEN='eki_test_verify',
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=False,
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
        from core.models import SandboxCanalSesion

        SandboxCanalSesion.objects.create(telefono='573001234591', habeas_aceptado=True)
        payload = _meta_envelope(
            {'from': '573001234591', 'id': 'wamid.in1', 'type': 'text', 'text': {'body': 'hola'}},
        )
        with patch('core.sandbox_menu.enviar_menu_sandbox', return_value={'success': True}) as menu, \
                patch('core.views.entrada._procesar_meta_webhook') as legacy:
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

        SandboxCanalSesion.objects.create(
            telefono='573001234592', modo=MODO_CURSOS, habeas_aceptado=True,
        )
        payload = _meta_envelope(
            {'from': '573001234592', 'id': 'wamid.in2', 'type': 'text', 'text': {'body': 'listo'}},
        )
        with patch('core.views.webhook_meta._procesar_twilio_webhook', return_value=None) as edu, \
                patch('core.views.entrada._procesar_meta_webhook') as legacy:
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

        SandboxCanalSesion.objects.create(
            telefono='573001234594', modo=MODO_NAT, habeas_aceptado=True,
        )
        payload = _meta_envelope(
            {'from': '573001234594', 'id': 'wamid.in3', 'type': 'text', 'text': {'body': 'mancha en tomate'}},
        )
        with patch('core.views.webhook_meta._encolar_bot_comercial_si_async', return_value=False), \
                patch('core.bot_comercial.webhook._procesar_bot_comercial_twilio_webhook') as nat, \
                patch('core.views.entrada._procesar_meta_webhook') as legacy:
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

    def _post(self, payload):
        return self.client.post(
            '/webhook/whatsapp/',
            data=json.dumps(payload),
            content_type='application/json',
            secure=True,
        )

    def test_reintento_de_meta_no_responde_dos_veces(self):
        from core.models import SandboxCanalSesion

        SandboxCanalSesion.objects.create(telefono='573001234595', habeas_aceptado=True)
        payload = _meta_envelope(
            {'from': '573001234595', 'id': 'wamid.dup1', 'type': 'text', 'text': {'body': 'hola'}},
        )
        with patch('core.sandbox_menu.enviar_menu_sandbox', return_value={'success': True}) as menu:
            self.assertEqual(self._post(payload).status_code, 200)
            self.assertEqual(self._post(payload).status_code, 200)
        self.assertEqual(menu.call_count, 1)

    def _tasks_falso(self, **delay_kwargs):
        import sys
        import types
        from unittest.mock import MagicMock

        falso = types.ModuleType('core.tasks')
        falso.procesar_sandbox_meta_async = MagicMock()
        falso.procesar_sandbox_meta_async.delay = MagicMock(**delay_kwargs)
        return patch.dict(sys.modules, {'core.tasks': falso}), falso.procesar_sandbox_meta_async.delay

    @override_settings(SANDBOX_CELERY_ASYNC=True)
    def test_con_flag_encola_y_no_procesa_en_el_request(self):
        payload = _meta_envelope(
            {'from': '573001234596', 'id': 'wamid.async1', 'type': 'text', 'text': {'body': 'hola'}},
        )
        modulo, delay = self._tasks_falso()
        with modulo, patch('core.views.entrada._aplicar_sandbox_menu') as sync:
            self.assertEqual(self._post(payload).status_code, 200)
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(delay.call_args.args[0]['MessageSid'], 'wamid.async1')
        sync.assert_not_called()

    @override_settings(SANDBOX_CELERY_ASYNC=True)
    def test_sin_redis_responde_500_y_suelta_el_reclamo(self):
        from core.webhook_evento import WebhookEventoProcesado

        payload = _meta_envelope(
            {'from': '573001234597', 'id': 'wamid.async2', 'type': 'text', 'text': {'body': 'hola'}},
        )
        modulo, _ = self._tasks_falso(side_effect=ConnectionError('redis'))
        with modulo, patch('core.views.entrada._aplicar_sandbox_menu', return_value=None) as sync:
            self.assertEqual(self._post(payload).status_code, 500)
        self.assertEqual(sync.call_count, 0)
        self.assertFalse(
            WebhookEventoProcesado.objects.filter(external_id='wamid.async2').exists()
        )

    def test_post_twilio_sandbox_se_ignora_cuando_canal_es_meta(self):
        with patch('core.views.entrada._procesar_twilio_webhook') as edu, \
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


class HabeasMetaAntesDelCursoTests(TestCase):
    def _est(self):
        from core.models import Cliente, Estudiante

        org = Cliente.objects.create(
            nombre='Org Corte',
            contacto_principal='Ops',
            email='corte@test.com',
            telefono='573001100088',
        )
        return Estudiante.objects.create(
            nombre='Julian',
            cedula='1014310196',
            telefono='573026480629',
            cliente=org,
            acepto_terminos=False,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )

    def _post(self, body, sid):
        return {
            '_eki_proveedor': 'meta',
            'From': 'whatsapp:+573026480629',
            'Body': body,
            'MessageSid': sid,
        }

    def test_listo_sin_aceptar_manda_botones_y_no_entra_al_curso(self):
        from core.views.webhook_twilio import _procesar_twilio_webhook

        self._est()
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as botones, \
                patch('core.views.webhook_twilio._procesar_twilio_webhook_cuerpo') as cuerpo:
            _procesar_twilio_webhook(self._post('Listo', 'wamid.listo1'))
        botones.assert_called_once()
        cuerpo.assert_not_called()

    def test_si_acepta_y_pide_la_cedula(self):
        from core.views.webhook_twilio import _procesar_twilio_webhook

        est = self._est()
        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}) as envio, \
                patch('core.views.webhook_twilio._procesar_twilio_webhook_cuerpo') as cuerpo:
            _procesar_twilio_webhook(self._post('Si', 'wamid.si1'))
        est.refresh_from_db()
        self.assertTrue(est.acepto_terminos)
        self.assertEqual(est.estado_chat, 'ESPERANDO_CEDULA')
        self.assertIn('cédula', envio.call_args[0][1].lower())
        cuerpo.assert_not_called()

    def test_si_de_la_cedula_abre_el_menu_y_no_el_curso(self):
        from core.models import ProgresoEstudiante
        from core.views.webhook_twilio import _procesar_twilio_webhook

        est = self._est()
        est.acepto_terminos = True
        est.estado_chat = 'CONFIRMANDO_DATOS'
        est.save(update_fields=['acepto_terminos', 'estado_chat'])
        with patch('core.sandbox_menu.enviar_menu_sandbox', return_value={'success': True}) as menu, \
                patch('core.views.webhook_twilio._procesar_twilio_webhook_cuerpo') as cuerpo:
            _procesar_twilio_webhook(self._post('si', 'wamid.datos1'))
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ACTIVO')
        self.assertEqual(est.estado_onboarding, 'completado')
        menu.assert_called_once()
        cuerpo.assert_not_called()
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=est).exists())
