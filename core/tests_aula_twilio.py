"""*aula* en Twilio emite código aunque el chat esté en habeas."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Estudiante
from core.views.webhook_twilio import (
    _intentar_aula_twilio_fuera_de_activo,
    _procesar_twilio_webhook,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class AulaTwilioWrapTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(
            nombre='Ana',
            cedula='AULA1',
            telefono='573001110001',
            estado_chat='ESPERANDO_HABEAS_DATA',
            estado_onboarding='',
            activo=True,
        )

    def _post(self, body='aula', **extra):
        data = {
            'From': 'whatsapp:+573001110001',
            'To': 'whatsapp:+573202948806',
            'Body': body,
            'MessageSid': 'SMabc123',
        }
        data.update(extra)
        return data

    def test_emite_si_espera_habeas(self):
        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}) as send:
            ok = _intentar_aula_twilio_fuera_de_activo(self._post())
        self.assertTrue(ok)
        texto = send.call_args.args[1]
        self.assertIn('/aprende/estudiante/login/', texto)
        self.assertRegex(texto, r'\*\d{6}\*')

    def test_no_emite_si_activo_para_no_duplicar_el_cuerpo(self):
        self.est.estado_chat = 'ACTIVO'
        self.est.save(update_fields=['estado_chat'])
        with patch('core.utils.enviar_whatsapp_twilio') as send:
            self.assertFalse(_intentar_aula_twilio_fuera_de_activo(self._post()))
        send.assert_not_called()

    def test_meta_no_usa_este_wrap(self):
        with patch('core.utils.enviar_whatsapp_twilio') as send:
            ok = _intentar_aula_twilio_fuera_de_activo(self._post(**{
                '_eki_proveedor': 'meta',
            }))
        self.assertFalse(ok)
        send.assert_not_called()

    def test_webhook_twilio_corta_antes_del_cuerpo(self):
        with patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True}) as send:
            with patch('core.views.webhook_twilio._procesar_twilio_webhook_cuerpo') as cuerpo:
                r = _procesar_twilio_webhook(self._post())
        self.assertIsNone(r)
        cuerpo.assert_not_called()
        send.assert_called_once()
