"""Inbound Meta: cada tipo deja evento, y el teléfono colombiano se normaliza igual."""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Estudiante
from core.models_meta_webhook import MetaWebhookEvento
from core.utils_telefono import normalizar_e164_co

SECRET = 'sekreto-test'
TEL = '573009990795'


def _firma(raw: bytes) -> str:
    digest = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def _mensaje(tipo, extra, wamid):
    base = {'from': TEL, 'id': wamid, 'type': tipo}
    base.update(extra)
    return {
        'object': 'whatsapp_business_account',
        'entry': [{
            'id': 'WABA',
            'changes': [{
                'field': 'messages',
                'value': {
                    'messaging_product': 'whatsapp',
                    'metadata': {
                        'display_phone_number': '573009998888',
                        'phone_number_id': '111222333',
                    },
                    'messages': [base],
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
    WHATSAPP_APP_SECRET=SECRET,
    WHATSAPP_REQUIRE_SIGNATURE=True,
    TWILIO_VALIDATE_SIGNATURE=False,
    WEBHOOK_CELERY_ASYNC=False,
    SANDBOX_CELERY_ASYNC=False,
    NAT_WEBHOOK_CELERY_ASYNC=False,
    SECURE_SSL_REDIRECT=False,
    LINEA_META_PLAN_DEFAULT='',
    LINEA_META_SOLO_REGISTRADOS=True,
)
class MetaInboundEventoTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = Cliente.objects.create(
            nombre='Org 795',
            contacto_principal='a',
            email='org795@example.com',
            telefono='573000000795',
            plan_linea_meta='curso_asesor',
        )
        self.est = Estudiante.objects.create(
            cedula='CC795',
            nombre='Luisa',
            telefono=TEL,
            cliente=self.org,
            activo=True,
        )

    def _post(self, payload):
        raw = json.dumps(payload).encode()
        return self.client.post(
            '/webhook/whatsapp/',
            data=raw,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_firma(raw),
        )

    def test_firma_invalida_no_deja_evento(self):
        payload = _mensaje('text', {'text': {'body': 'hola'}}, 'wamid.mala')
        raw = json.dumps(payload).encode()
        resp = self.client.post(
            '/webhook/whatsapp/',
            data=raw,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=00',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(MetaWebhookEvento.objects.filter(wamid='wamid.mala').exists())

    @patch('core.sandbox_canal.requests.post')
    def test_cada_tipo_deja_evento_con_resultado(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'messages': [{'id': 'wamid.out'}]}
        casos = [
            ('text', {'text': {'body': 'hola'}}, 'wamid.text'),
            ('interactive', {'interactive': {'list_reply': {'id': 'formacion', 'title': 'Formación'}}}, 'wamid.list'),
            ('interactive', {'interactive': {'button_reply': {'id': 'acepto', 'title': 'Acepto'}}}, 'wamid.btn'),
            ('button', {'button': {'payload': 'seguir', 'text': 'Seguir'}}, 'wamid.qr'),
            ('audio', {'audio': {'id': 'media1', 'mime_type': 'audio/ogg'}}, 'wamid.audio'),
            ('reaction', {'reaction': {'message_id': 'wamid.text', 'emoji': '👍'}}, 'wamid.react'),
            ('sticker', {'sticker': {'id': 'stk1'}}, 'wamid.stk'),
            ('unsupported', {}, 'wamid.uns'),
        ]
        with patch('core.sandbox_canal.transcribir_audio_meta', return_value='hola'):
            for tipo, extra, wamid in casos:
                resp = self._post(_mensaje(tipo, extra, wamid))
                self.assertEqual(resp.status_code, 200, wamid)
                evento = MetaWebhookEvento.objects.get(wamid=wamid)
                self.assertTrue(evento.resultado, wamid)
                self.assertNotEqual(evento.resultado, 'recibido', wamid)

    @patch('core.sandbox_menu.dispatch_sandbox_menu', side_effect=RuntimeError('boom'))
    @patch('core.sandbox_canal.requests.post')
    def test_excepcion_responde_fallback_y_guarda_error(self, post, _dispatch):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'messages': [{'id': 'wamid.fb'}]}
        resp = self._post(_mensaje('text', {'text': {'body': 'hola'}}, 'wamid.boom'))
        self.assertEqual(resp.status_code, 200)
        evento = MetaWebhookEvento.objects.get(wamid='wamid.boom')
        self.assertEqual(evento.resultado, 'error')
        cuerpo = json.dumps(post.call_args.kwargs.get('json') or post.call_args[1].get('json') or {})
        if not cuerpo or cuerpo == '{}':
            enviado = post.call_args[0][1] if len(post.call_args[0]) > 1 else post.call_args.kwargs.get('json')
            cuerpo = json.dumps(enviado or {})
        self.assertIn('problema', cuerpo)


class NormalizarE164CoTests(TestCase):
    def test_formatos_de_colombia(self):
        self.assertEqual(normalizar_e164_co('+57 300-648-0629'), '573006480629')
        self.assertEqual(normalizar_e164_co('573006480629'), '573006480629')
        self.assertEqual(normalizar_e164_co('00573006480629'), '573006480629')
        self.assertEqual(normalizar_e164_co('300 648 0629'), '573006480629')


class DiagnosticarTelefonoTests(TestCase):
    def test_avisa_si_hay_mas_de_una_ficha(self):
        org = Cliente.objects.create(
            nombre='Org dup',
            contacto_principal='a',
            email='dup@example.com',
            telefono='573000000111',
        )
        Estudiante.objects.create(cedula='D1', nombre='A', telefono='573001110795', cliente=org)
        Estudiante.objects.create(cedula='D2', nombre='B', telefono='573009990795', cliente=org)
        from io import StringIO

        out = StringIO()
        call_command('diagnosticar_telefono', '0795', stdout=out)
        texto = out.getvalue()
        self.assertIn('fichas coinciden', texto)
        self.assertIn('ninguno: el webhook no vio', texto)


class GraphReintentoTests(TestCase):
    @override_settings(WHATSAPP_TOKEN='test-token', WHATSAPP_PHONE_ID='111222333')
    @patch('core.sandbox_canal.requests.post')
    def test_130429_reintenta_una_vez_y_131026_no(self, post):
        from core.sandbox_canal import _post_graph

        class Resp:
            def __init__(self, status, code):
                self.status_code = status
                self.text = ''
                self._code = code

            def json(self):
                if self.status_code == 200:
                    return {'messages': [{'id': 'wamid.ok'}]}
                return {'error': {'code': self._code, 'message': 'x', 'error_data': {'details': 'd'}}}

        post.side_effect = [Resp(400, 130429), Resp(200, None)]
        ok = _post_graph({'to': '573001110000', 'type': 'text', 'text': {'body': 'a'}})
        self.assertTrue(ok['success'])
        self.assertEqual(post.call_count, 2)

        post.reset_mock()
        post.side_effect = [Resp(400, 131026)]
        mal = _post_graph({'to': '573001110000', 'type': 'text', 'text': {'body': 'a'}})
        self.assertFalse(mal['success'])
        self.assertEqual(post.call_count, 1)
        from core.models import WhatsappLog
        log = WhatsappLog.objects.filter(error_codigo='131026').first()
        self.assertIsNotNone(log)
        self.assertIn('d', log.error_detalle or '')
