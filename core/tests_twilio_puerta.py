"""Twilio cerrado: solo *aula* y el código. El curso no entra por ese número."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Estudiante
from core.twilio_puerta import TEXTO_CERRADO, aplicar_puerta_twilio, responder_aula_meta


@override_settings(SECURE_SSL_REDIRECT=False)
class PuertaTwilioTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(
            nombre='Ana',
            cedula='PUERTA1',
            telefono='573001110001',
            estado_chat='ACTIVO',
            estado_onboarding='completado',
            activo=True,
        )

    def _post(self, body='aula', **extra):
        data = {
            'From': 'whatsapp:+573001110001',
            'To': 'whatsapp:+573202948806',
            'Body': body,
            'MessageSid': 'SMpuerta1',
        }
        data.update(extra)
        return data

    def test_aula_activo_manda_codigo_y_no_entra_al_curso(self):
        from core.views.entrada import _procesar_twilio_reclamado

        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}) as send:
            with patch('core.views.entrada._procesar_twilio_webhook') as curso:
                r = _procesar_twilio_reclamado(self._post(), ['SMpuerta1'], lambda _d: False)
        self.assertIsNone(r)
        curso.assert_not_called()
        texto = send.call_args.args[1]
        self.assertIn('/aprende/estudiante/login/', texto)
        self.assertRegex(texto, r'\*\d{6}\*')

    def test_listo_no_avanza_el_curso(self):
        from core.views.entrada import _procesar_twilio_reclamado

        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}) as send:
            with patch('core.views.entrada._procesar_twilio_webhook') as curso:
                _procesar_twilio_reclamado(self._post('listo'), ['SMpuerta2'], lambda _d: False)
        curso.assert_not_called()
        self.assertIn('aula', send.call_args.args[1])
        self.assertEqual(send.call_args.args[1], TEXTO_CERRADO)

    def test_callback_de_estado_sigue_al_registrador(self):
        from core.views.entrada import _procesar_twilio_reclamado

        data = self._post('', MessageStatus='delivered', SmsStatus='delivered')
        with patch('core.utils.enviar_whatsapp_twilio') as send:
            with patch('core.views.entrada._procesar_twilio_webhook', return_value=None) as curso:
                _procesar_twilio_reclamado(data, ['SMpuerta3'], lambda _d: False)
        send.assert_not_called()
        curso.assert_called_once()

    def test_aula_en_meta_sale_por_meta(self):
        data = self._post(_eki_proveedor='meta')
        with patch('core.sandbox_canal.enviar_meta', return_value={'success': True}) as meta:
            with patch('core.utils.enviar_whatsapp_twilio') as twilio:
                ok = responder_aula_meta(data)
        self.assertTrue(ok)
        meta.assert_called_once()
        self.assertEqual(meta.call_args.kwargs['canal_evento'], 'aprende')
        twilio.assert_not_called()
        self.assertRegex(meta.call_args.args[1], r'\*\d{6}\*')

    def test_aplicar_puerta_aula_no_es_seguir(self):
        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}):
            self.assertEqual(aplicar_puerta_twilio(self._post()), 'aula')
