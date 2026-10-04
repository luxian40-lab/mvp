"""El entrante de Meta queda canal=meta aunque lo cree el camino educativo."""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from core.models import Estudiante, WhatsappLog
from core.reenganche_meta import ventana_abierta
from core.sandbox_menu import MODO_CURSOS

SECRET = 'sekreto-test'
TEL = '573001234592'


def _firma(raw: bytes) -> str:
    digest = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def _meta_listo():
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
                    'messages': [{
                        'from': TEL,
                        'id': 'wamid.ventana1',
                        'type': 'text',
                        'text': {'body': 'listo'},
                    }],
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
    WA_VENTANA_HORAS=23,
)
class VentanaCanalWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.estudiante = Estudiante.objects.create(
            cedula='CC1234592',
            nombre='Ana',
            telefono=TEL,
        )
        from core.models import SandboxCanalSesion

        SandboxCanalSesion.objects.create(
            telefono=TEL, modo=MODO_CURSOS, habeas_aceptado=True,
        )

    def test_payload_meta_firmado_marca_entrante_y_abre_ventana(self):
        raw = json.dumps(_meta_listo()).encode()
        with patch(
            'core.views.webhook_twilio._intentar_responder_envio_certificado',
            return_value=True,
        ), patch('core.sandbox_canal.poner_reaccion_espera'):
            resp = self.client.post(
                '/webhook/whatsapp/',
                data=raw,
                content_type='application/json',
                secure=True,
                HTTP_HOST='testserver',
                HTTP_X_HUB_SIGNATURE_256=_firma(raw),
            )
        self.assertEqual(resp.status_code, 200)
        log = WhatsappLog.objects.get(mensaje_id='wamid.ventana1', tipo='INCOMING')
        self.assertEqual(log.canal, 'meta')
        self.assertTrue(ventana_abierta(self.estudiante))

    def test_post_twilio_no_abre_ventana_meta(self):
        with patch(
            'core.views.webhook_twilio._intentar_responder_envio_certificado',
            return_value=True,
        ):
            resp = self.client.post(
                '/webhook/whatsapp/',
                data={
                    'From': f'whatsapp:+{TEL}',
                    'To': 'whatsapp:+14155238886',
                    'Body': 'hola',
                    'MessageSid': 'SMventana1',
                },
                secure=True,
                HTTP_HOST='testserver',
            )
        self.assertEqual(resp.status_code, 200)
        log = WhatsappLog.objects.get(mensaje_id='SMventana1', tipo='INCOMING')
        self.assertEqual(log.canal, 'twilio')
        self.assertFalse(ventana_abierta(self.estudiante))
