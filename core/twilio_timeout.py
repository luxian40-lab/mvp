"""Timeout del cliente HTTP de Twilio. No añade reintentos."""
from __future__ import annotations


def aplicar_timeout_twilio() -> None:
    """TwilioHttpClient.__init__ acepta timeout (twilio 9.9 / 9.10). Lo fija al setting."""
    from twilio.http.http_client import TwilioHttpClient

    actual = TwilioHttpClient.__init__
    if getattr(actual, '_eki_timeout', False):
        return
    original = actual

    def __init__(self, *args, **kwargs):
        from django.conf import settings

        kwargs['timeout'] = getattr(settings, 'TWILIO_HTTP_TIMEOUT', 15)
        return original(self, *args, **kwargs)

    __init__._eki_timeout = True
    TwilioHttpClient.__init__ = __init__
