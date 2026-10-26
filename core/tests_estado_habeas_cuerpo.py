"""Caracterización de ESPERANDO_HABEAS_DATA en el cuerpo del webhook.

Cubre lo que HabeasWebhookBarrierTests no toca: la plantilla que se reenvía,
el texto de respaldo si la plantilla no sale, y el certificado pendiente,
que deja pasar el turno sin tocar el habeas.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.models import Cliente, Estudiante


@override_settings(SECURE_SSL_REDIRECT=False)
class HabeasCuerpoTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Habeas Cuerpo',
            contacto_principal='A',
            email='hcuerpo@t.com',
            telefono='573001111333',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='habeas_cuerpo',
            nombre='Cuerpo Habeas',
            telefono='573009993333',
            cliente=self.cliente,
            activo=True,
            estado_chat='ESPERANDO_HABEAS_DATA',
            acepto_terminos=False,
            contexto_temporal={},
        )

    def _post(self, body, sid):
        from core.views import _procesar_twilio_webhook

        _procesar_twilio_webhook({
            'From': 'whatsapp:+573009993333',
            'To': 'whatsapp:+573202948806',
            'MessageSid': sid,
            'Body': body,
        })

    @patch('twilio.rest.Client')
    @patch('core.whatsapp_service.enviar_habeas_data', return_value={'success': True})
    def test_texto_sin_respuesta_reenvia_la_plantilla_y_no_manda_texto(self, mock_tpl, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        self._post('quiero info', 'SM_hc_tpl_ok')
        mock_tpl.assert_called_once()
        self.assertEqual(mock_tpl.call_args.kwargs.get('cliente'), self.cliente)
        mock_client.messages.create.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        self.assertFalse(self.est.acepto_terminos)

    @patch('twilio.rest.Client')
    @patch('core.whatsapp_service.enviar_habeas_data', return_value={'success': False})
    def test_plantilla_que_no_sale_manda_el_texto_de_respaldo(self, mock_tpl, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        self._post('quiero info', 'SM_hc_tpl_falla')
        mock_tpl.assert_called_once()
        mock_client.messages.create.assert_called_once()
        enviado = mock_client.messages.create.call_args.kwargs
        self.assertIn('*¡Bienvenido a eki!*', enviado['body'])
        self.assertIn('Ley 1581 de 2012', enviado['body'])
        self.assertIn('👉 Escribe *Acepto* o *No acepto*', enviado['body'])
        self.assertEqual(enviado['to'], 'whatsapp:+573009993333')
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_HABEAS_DATA')

    @patch('twilio.rest.Client')
    def test_certificado_pendiente_deja_pasar_sin_tocar_el_habeas(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.messages.create.return_value.sid = 'SM_hc_cert_salida'
        mock_client_cls.return_value = mock_client
        pendiente = {'certificado_id': 999999}
        self.est.contexto_temporal = {'cert_envio_pendiente': pendiente}
        self.est.save(update_fields=['contexto_temporal'])
        with patch('core.habeas_respuestas.aplicar_respuesta_habeas') as mock_aplicar:
            # «listo» no libera el certificado, así que la marca sigue al llegar al habeas.
            self._post('listo', 'SM_hc_cert')
        mock_aplicar.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual((self.est.contexto_temporal or {}).get('cert_envio_pendiente'), pendiente)
