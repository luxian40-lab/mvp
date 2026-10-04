"""Statuses de Cloud API: orden, duplicado, desconocido, firma y webhook liviano."""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from core.meta_estados import aplicar_statuses
from core.models import WhatsappLog


def _log(mid, estado='sent'):
    return WhatsappLog.objects.create(
        telefono='57300***',
        mensaje_id=mid,
        tipo='SENT',
        canal='meta',
        estado=estado,
        mensaje='hola',
    )


class OrdenEstadosTests(TestCase):
    def test_sent_delivered_read_no_retrocede(self):
        log = _log('wamid.orden')
        aplicar_statuses([{'id': 'wamid.orden', 'status': 'delivered', 'timestamp': '1'}])
        log.refresh_from_db()
        self.assertEqual(log.estado, 'delivered')
        aplicar_statuses([{'id': 'wamid.orden', 'status': 'sent', 'timestamp': '2'}])
        log.refresh_from_db()
        self.assertEqual(log.estado, 'delivered')
        aplicar_statuses([{'id': 'wamid.orden', 'status': 'read', 'timestamp': '3'}])
        log.refresh_from_db()
        self.assertEqual(log.estado, 'read')

    def test_evento_duplicado_no_cambia(self):
        log = _log('wamid.dup', estado='delivered')
        aplicar_statuses([{'id': 'wamid.dup', 'status': 'delivered', 'timestamp': '9'}])
        log.refresh_from_db()
        self.assertEqual(log.estado, 'delivered')

    def test_status_desconocido_se_ignora(self):
        with self.assertLogs('core.meta_estados', level='DEBUG') as logs:
            n = aplicar_statuses([{'id': 'wamid.nadie', 'status': 'sent'}])
        self.assertEqual(n, 0)
        self.assertFalse(WhatsappLog.objects.filter(mensaje_id='wamid.nadie').exists())
        self.assertTrue(any('meta_status_desconocido' in linea for linea in logs.output))

    def test_failed_guarda_el_codigo_y_sobrescribe_sent(self):
        log = _log('wamid.fail')
        aplicar_statuses([{
            'id': 'wamid.fail',
            'status': 'failed',
            'timestamp': '4',
            'errors': [{'code': 131047, 'title': 'Re-engagement message'}],
        }])
        log.refresh_from_db()
        self.assertEqual(log.estado, 'failed')
        self.assertEqual(log.error_codigo, '131047')
        self.assertIn('ventana_cerrada', log.error_detalle)
        aplicar_statuses([{'id': 'wamid.fail', 'status': 'sent', 'timestamp': '5'}])
        log.refresh_from_db()
        self.assertEqual(log.estado, 'failed')


def _payload_statuses():
    return {
        'object': 'whatsapp_business_account',
        'entry': [{
            'changes': [{
                'field': 'messages',
                'value': {'statuses': [{'id': 'wamid.solo', 'status': 'delivered', 'timestamp': '1'}]},
            }],
        }],
    }


@override_settings(
    SECURE_SSL_REDIRECT=False,
    WHATSAPP_APP_SECRET='',
    WHATSAPP_REQUIRE_SIGNATURE=False,
    SANDBOX_MENU_ENABLED=False,
)
class WebhookStatusesTests(TestCase):
    def test_solo_statuses_responde_200_sin_curso(self):
        with patch('core.tasks.procesar_statuses_meta_async.delay') as delay, \
                patch('core.views.entrada._procesar_meta_webhook') as curso:
            resp = Client().post(
                '/webhook/whatsapp/',
                data=json.dumps(_payload_statuses()),
                content_type='application/json',
                secure=True,
                HTTP_HOST='testserver',
            )
        self.assertEqual(resp.status_code, 200)
        curso.assert_not_called()
        delay.assert_called_once()

    @override_settings(WHATSAPP_APP_SECRET='sekreto-test', WHATSAPP_REQUIRE_SIGNATURE=True)
    def test_firma_invalida_no_procesa(self):
        log = _log('wamid.solo', estado='sent')
        body = json.dumps(_payload_statuses()).encode('utf-8')
        mala = hmac.new(b'otro', body, hashlib.sha256).hexdigest()
        with patch('core.tasks.procesar_statuses_meta_async.delay') as delay:
            resp = Client().post(
                '/webhook/whatsapp/',
                data=body,
                content_type='application/json',
                secure=True,
                HTTP_HOST='testserver',
                HTTP_X_HUB_SIGNATURE_256=f'sha256={mala}',
            )
        self.assertEqual(resp.status_code, 403)
        delay.assert_not_called()
        log.refresh_from_db()
        self.assertEqual(log.estado, 'sent')
        self.assertFalse(log.error_codigo)
