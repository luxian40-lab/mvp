"""Regresión: No acepto ≠ Acepto; confirmación de rechazo; botones sin Body."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.habeas_respuestas import (
    CTX_CONFIRMA_RECHAZO,
    aplicar_respuesta_habeas,
    clasificar_respuesta_habeas,
    texto_desde_webhook_twilio,
)
from core.models import Cliente, Estudiante


class ClasificarHabeasTests(TestCase):
    def test_no_acepto_es_rechazo_no_acepto(self):
        self.assertEqual(clasificar_respuesta_habeas('No acepto'), 'rechazo')
        self.assertEqual(clasificar_respuesta_habeas('no acepto'), 'rechazo')
        self.assertEqual(clasificar_respuesta_habeas('NO ACEPTO'), 'rechazo')
        self.assertEqual(clasificar_respuesta_habeas('no_acepto'), 'rechazo')

    def test_acepto_es_acepto(self):
        self.assertEqual(clasificar_respuesta_habeas('Acepto'), 'acepto')
        self.assertEqual(clasificar_respuesta_habeas('sí'), 'acepto')
        self.assertEqual(clasificar_respuesta_habeas('si'), 'acepto')
        self.assertEqual(clasificar_respuesta_habeas('de acuerdo'), 'acepto')

    def test_solo_no_es_rechazo(self):
        self.assertEqual(clasificar_respuesta_habeas('No'), 'rechazo')

    def test_texto_irrelevante_none(self):
        self.assertIsNone(clasificar_respuesta_habeas('hola'))
        self.assertIsNone(clasificar_respuesta_habeas(''))
        self.assertIsNone(clasificar_respuesta_habeas('quiero info'))

    def test_button_payload_sin_body(self):
        self.assertEqual(
            texto_desde_webhook_twilio({'ButtonPayload': 'No acepto'}, ''),
            'No acepto',
        )
        self.assertEqual(
            texto_desde_webhook_twilio({'ButtonText': 'Acepto', 'Body': ''}, ''),
            'Acepto',
        )


class FlujoConfirmacionRechazoTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Habeas Conf',
            contacto_principal='A',
            email='hc@t.com',
            telefono='573001111223',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='habeas_conf',
            nombre='Conf Habeas',
            telefono='573009991112',
            cliente=self.cliente,
            activo=True,
            estado_chat='ESPERANDO_HABEAS_DATA',
            acepto_terminos=False,
            contexto_temporal={},
        )

    def test_no_acepto_pide_confirmacion_no_cierra(self):
        r = aplicar_respuesta_habeas(self.est, 'No acepto')
        self.est.refresh_from_db()
        self.assertEqual(r['accion'], 'pide_confirmacion')
        self.assertIn('Seguro', r['texto'])
        self.assertFalse(self.est.acepto_terminos)
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        self.assertTrue((self.est.contexto_temporal or {}).get(CTX_CONFIRMA_RECHAZO))

    def test_confirma_no_cierra_flujo(self):
        aplicar_respuesta_habeas(self.est, 'No acepto')
        r2 = aplicar_respuesta_habeas(self.est, 'No')
        self.est.refresh_from_db()
        self.assertEqual(r2['accion'], 'rechazo_final')
        self.assertIn('Entendemos tu decisión', r2['texto'])
        self.assertFalse(self.est.acepto_terminos)
        self.assertFalse((self.est.contexto_temporal or {}).get(CTX_CONFIRMA_RECHAZO))

    def test_tras_no_acepto_puede_aceptar(self):
        aplicar_respuesta_habeas(self.est, 'No acepto')
        r2 = aplicar_respuesta_habeas(self.est, 'Acepto')
        self.est.refresh_from_db()
        self.assertEqual(r2['accion'], 'acepto')
        self.assertTrue(self.est.acepto_terminos)
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_CEDULA')


@override_settings(SECURE_SSL_REDIRECT=False)
class HabeasWebhookBarrierTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Habeas',
            contacto_principal='A',
            email='h@t.com',
            telefono='573001111222',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='habeas1',
            nombre='Test Habeas',
            telefono='573009991111',
            cliente=self.cliente,
            activo=True,
            estado_chat='ESPERANDO_HABEAS_DATA',
            acepto_terminos=False,
            contexto_temporal={},
        )

    def _post(self, **extra):
        from core.views import _procesar_twilio_webhook

        data = {
            'From': 'whatsapp:+573009991111',
            'To': 'whatsapp:+573202948806',
            'MessageSid': f'SM_habeas_{extra.get("Body") or extra.get("ButtonPayload") or "x"}_{extra.get("_n", "0")}',
            'Body': '',
        }
        data.update(extra)
        data.pop('_n', None)
        _procesar_twilio_webhook(data)

    @patch('twilio.rest.Client')
    def test_no_acepto_pide_confirmacion(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        self._post(Body='No acepto', _n='1')
        self.est.refresh_from_db()
        self.assertFalse(self.est.acepto_terminos)
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        sent = mock_client.messages.create.call_args.kwargs.get('body') or ''
        self.assertIn('Seguro', sent)
        self.assertNotIn('cédula', sent.lower())

    @patch('twilio.rest.Client')
    def test_confirma_no_cierra(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        self._post(Body='No acepto', _n='a')
        self._post(Body='No', _n='b')
        self.est.refresh_from_db()
        self.assertFalse(self.est.acepto_terminos)
        sent = mock_client.messages.create.call_args.kwargs.get('body') or ''
        self.assertIn('Entendemos tu decisión', sent)

    @patch('twilio.rest.Client')
    def test_acepto_pide_cedula(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        self._post(Body='Acepto', _n='2')
        self.est.refresh_from_db()
        self.assertTrue(self.est.acepto_terminos)
        self.assertEqual(self.est.estado_chat, 'ESPERANDO_CEDULA')
        sent = mock_client.messages.create.call_args.kwargs.get('body') or ''
        self.assertIn('cédula', sent.lower())

    @patch('twilio.rest.Client')
    def test_button_payload_no_acepto_sin_body(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        self._post(Body='', ButtonPayload='No acepto', MessageSid='SM_btn_no')
        self.est.refresh_from_db()
        self.assertFalse(self.est.acepto_terminos)
        sent = mock_client.messages.create.call_args.kwargs.get('body') or ''
        self.assertIn('Seguro', sent)
