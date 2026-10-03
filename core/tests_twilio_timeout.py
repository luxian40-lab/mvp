"""El cliente Twilio sale con timeout y sin reintentos añadidos."""
from pathlib import Path

from django.test import SimpleTestCase, override_settings


@override_settings(TWILIO_HTTP_TIMEOUT=15)
class TwilioHttpTimeoutTests(SimpleTestCase):
    def test_client_http_timeout_es_15(self):
        from twilio.rest import Client

        cliente = Client('ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'x')
        self.assertEqual(cliente.http_client.timeout, 15)
        self.assertIsNone(cliente.http_client.session.adapters['https://'].max_retries.total or None)

    def test_media_y_correo_tienen_timeout(self):
        media = Path('core/views/media.py').read_text(encoding='utf-8')
        correo = Path('core/email_service.py').read_text(encoding='utf-8')
        self.assertIn('timeout=(5, 30)', media)
        self.assertEqual(correo.count('timeout=15'), 3)
