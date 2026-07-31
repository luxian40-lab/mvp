"""Regresión: From Twilio no debe quedar en None si TWILIO_PHONE_NUMBER está vacío."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


class TwilioFromFallbackTests(SimpleTestCase):
    @override_settings(
        TWILIO_ACCOUNT_SID='ACtest',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_PHONE_NUMBER=None,
        TWILIO_WHATSAPP_NUMBER='whatsapp:+14155238886',
    )
    @patch('core.utils.WhatsappLog')
    @patch('twilio.rest.Client')
    def test_usa_whatsapp_number_si_phone_es_none(self, client_cls, _log):
        from core.utils import enviar_whatsapp_twilio

        msg = MagicMock()
        msg.sid = 'SMtest'
        client_cls.return_value.messages.create.return_value = msg

        r = enviar_whatsapp_twilio('573026480629', 'hola')
        self.assertTrue(r['success'])
        kwargs = client_cls.return_value.messages.create.call_args.kwargs
        self.assertEqual(kwargs['from_'], 'whatsapp:+14155238886')
        self.assertEqual(kwargs['to'], 'whatsapp:+573026480629')

    @override_settings(
        TWILIO_ACCOUNT_SID='ACtest',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_PHONE_NUMBER=None,
        TWILIO_WHATSAPP_NUMBER=None,
    )
    @patch('core.utils.WhatsappLog')
    @patch('twilio.rest.Client')
    def test_fallback_prod_si_ambos_vacios(self, client_cls, _log):
        from core.utils import enviar_whatsapp_twilio

        msg = MagicMock()
        msg.sid = 'SMtest2'
        client_cls.return_value.messages.create.return_value = msg

        r = enviar_whatsapp_twilio('573026480629', 'hola')
        self.assertTrue(r['success'])
        kwargs = client_cls.return_value.messages.create.call_args.kwargs
        self.assertEqual(kwargs['from_'], 'whatsapp:+573202948806')
