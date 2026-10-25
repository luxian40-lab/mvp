"""La ventana de 24 h abre con cualquier entrante de Meta, también si se queda en el menú."""
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Estudiante, WhatsappLog
from core.models_meta_webhook import MetaWebhookEvento
from core.reenganche_meta import ventana_abierta

SECRET = 'sekreto-test'
TEL = '573001234593'


def _evento(wamid, resultado='respondido', telefono=TEL, hace=None):
    evento = MetaWebhookEvento.objects.create(wamid=wamid, telefono=telefono, resultado=resultado)
    if hace is not None:
        MetaWebhookEvento.objects.filter(pk=evento.pk).update(recibido_en=timezone.now() - hace)
    return evento


@override_settings(WA_VENTANA_HORAS=23)
class VentanaPorEventoMetaTests(TestCase):
    def setUp(self):
        self.estudiante = Estudiante.objects.create(cedula='CC1234593', nombre='Ana', telefono=TEL)

    def test_evento_reciente_abre_ventana_sin_log_entrante(self):
        _evento('wamid.ev1')
        self.assertFalse(WhatsappLog.objects.filter(tipo='INCOMING').exists())
        self.assertTrue(ventana_abierta(self.estudiante))

    def test_evento_viejo_no_abre_ventana(self):
        _evento('wamid.ev2', hace=timedelta(hours=30))
        self.assertFalse(ventana_abierta(self.estudiante))

    def test_reaccion_no_abre_ventana(self):
        _evento('wamid.ev3', resultado='ignorado')
        self.assertFalse(ventana_abierta(self.estudiante))

    def test_twilio_hacia_linea_meta_no_abre_ventana(self):
        _evento('wamid.ev4', resultado='ignorado_twilio')
        self.assertFalse(ventana_abierta(self.estudiante))

    def test_entrante_twilio_trazado_no_abre_ventana(self):
        _evento('SMventana2', resultado='sin_plan')
        _evento('SMaula3', resultado='aula')
        self.assertFalse(ventana_abierta(self.estudiante))

    def test_evento_sin_wamid_no_abre_ventana(self):
        _evento('noid-abc123')
        self.assertFalse(ventana_abierta(self.estudiante))

    def test_telefono_con_mas_en_la_ficha(self):
        self.estudiante.telefono = f'+{TEL}'
        self.estudiante.save(update_fields=['telefono'])
        _evento('wamid.ev5')
        self.assertTrue(ventana_abierta(self.estudiante))

    def test_evento_de_otro_telefono_no_cuenta(self):
        _evento('wamid.ev6', telefono='573009999999')
        self.assertFalse(ventana_abierta(self.estudiante))


def _firma(raw: bytes) -> str:
    digest = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def _meta_texto(body):
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
                        'id': 'wamid.menu1',
                        'type': 'text',
                        'text': {'body': body},
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
    WEBHOOK_CELERY_ASYNC=False,
    SANDBOX_CELERY_ASYNC=False,
    NAT_WEBHOOK_CELERY_ASYNC=False,
    SECURE_SSL_REDIRECT=False,
    WA_VENTANA_HORAS=23,
)
class VentanaMenuMetaWebhookTests(TestCase):
    def test_mensaje_que_se_queda_en_el_menu_abre_ventana(self):
        estudiante = Estudiante.objects.create(
            cedula='CC1234594', nombre='Ana', telefono=TEL, acepto_terminos=True, estado_chat='ACTIVO',
        )
        raw = json.dumps(_meta_texto('menu')).encode()
        with patch('core.sandbox_canal.poner_reaccion_espera'):
            resp = self.client.post(
                '/webhook/whatsapp/',
                data=raw,
                content_type='application/json',
                secure=True,
                HTTP_HOST='testserver',
                HTTP_X_HUB_SIGNATURE_256=_firma(raw),
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MetaWebhookEvento.objects.filter(wamid='wamid.menu1').exists())
        self.assertTrue(ventana_abierta(estudiante))
