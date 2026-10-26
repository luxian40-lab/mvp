"""Caracterización de la corrección de datos legado en el cuerpo del webhook.

ESPERANDO_CORRECCION_DATOS lo pone el intent «corregir_datos» del bloque ACTIVO;
ESPERANDO_AYUDA_MODIFICAR es el nombre viejo. El siguiente mensaje vuelve a
ACTIVO y responde «Listo», o abre un ticket si pide ayuda.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.models import Cliente, Estudiante, SolicitudSoporte


@override_settings(SECURE_SSL_REDIRECT=False)
class CorreccionLegadoCuerpoTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Correccion Cuerpo',
            contacto_principal='A',
            email='ccuerpo@t.com',
            telefono='573001111444',
            activo=True,
        )

    def _estudiante(self, estado_chat):
        return Estudiante.objects.create(
            cedula=f'corr_{estado_chat[:12]}',
            nombre='Cami Corrige',
            telefono='573009994444',
            cliente=self.cliente,
            activo=True,
            estado_chat=estado_chat,
            estado_onboarding='nuevo',
            acepto_terminos=True,
            contexto_temporal={},
        )

    def _post(self, body, sid):
        from core.views import _procesar_twilio_webhook

        mock_client = MagicMock()
        mock_client.messages.create.return_value.sid = f'{sid}_salida'
        with patch('twilio.rest.Client', return_value=mock_client):
            _procesar_twilio_webhook({
                'From': 'whatsapp:+573009994444',
                'To': 'whatsapp:+573202948806',
                'MessageSid': sid,
                'Body': body,
            })
        return mock_client

    def test_correccion_datos_vuelve_a_activo_y_dice_listo(self):
        est = self._estudiante('ESPERANDO_CORRECCION_DATOS')
        cliente_tw = self._post('ok gracias', 'SM_corr_ok')
        est.refresh_from_db()
        self.assertEqual((est.estado_chat, est.estado_onboarding), ('ACTIVO', 'completado'))
        cliente_tw.messages.create.assert_called_once()
        enviado = cliente_tw.messages.create.call_args.kwargs
        self.assertEqual(enviado['body'], '✅ *¡Listo, Cami Corrige!*\n\nContinuemos con tu curso.')
        self.assertEqual(enviado['to'], 'whatsapp:+573009994444')
        self.assertFalse(SolicitudSoporte.objects.filter(estudiante=est).exists())

    def test_ayuda_modificar_tambien_vuelve_a_activo(self):
        est = self._estudiante('ESPERANDO_AYUDA_MODIFICAR')
        cliente_tw = self._post('ok gracias', 'SM_corr_ayuda_mod')
        est.refresh_from_db()
        self.assertEqual((est.estado_chat, est.estado_onboarding), ('ACTIVO', 'completado'))
        self.assertIn('*¡Listo, Cami Corrige!*', cliente_tw.messages.create.call_args.kwargs['body'])

    def test_pedir_ayuda_abre_ticket_de_soporte(self):
        est = self._estudiante('ESPERANDO_CORRECCION_DATOS')
        cliente_tw = self._post('tengo un problema con mis datos', 'SM_corr_ticket')
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ACTIVO')
        ticket = SolicitudSoporte.objects.get(estudiante=est)
        self.assertEqual(ticket.keyword_usada, 'soporte_legacy')
        self.assertEqual(ticket.asunto, 'Soporte desde flujo legacy')
        self.assertEqual(ticket.mensaje_original, 'Solicitud de soporte: tengo un problema con mis datos')
        self.assertIn('🆘 *Solicitud Recibida*', cliente_tw.messages.create.call_args.kwargs['body'])
