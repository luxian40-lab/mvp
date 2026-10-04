"""Límite HTTP por IP: proxy de confianza, webhooks exentos, 429 con cache limpio."""
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.middleware import RateLimitMiddleware


def _middleware():
    return RateLimitMiddleware(lambda request: HttpResponse('ok'))


_LIMITE = dict(
    RATE_LIMIT_ENABLED=True,
    RATE_LIMIT_REQUESTS=2,
    RATE_LIMIT_PERIOD=60,
    EKI_BEHIND_CLOUDFLARE=False,
    EKI_TRUSTED_PROXY_COUNT=1,
)


@override_settings(**_LIMITE)
class RateLimitHttpTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()
        self.mw = _middleware()

    def test_ip_es_el_enesimo_salto_desde_la_derecha(self):
        req = self.rf.get(
            '/portal/',
            HTTP_X_FORWARDED_FOR='198.51.100.4, 203.0.113.9',
            REMOTE_ADDR='10.0.0.1',
        )
        self.assertEqual(self.mw.get_client_ip(req), '203.0.113.9')

    def test_webhook_y_health_no_entran_al_limite(self):
        for path in ('/webhook/whatsapp/', '/webhook/ia-bot-comercial/', '/health/'):
            for _ in range(5):
                resp = self.mw.process_request(self.rf.post(path, REMOTE_ADDR='192.0.2.8'))
                self.assertIsNone(resp)

    def test_supera_el_limite_responde_429(self):
        for _ in range(2):
            self.assertIsNone(
                self.mw.process_request(self.rf.get('/portal/', REMOTE_ADDR='192.0.2.9'))
            )
        resp = self.mw.process_request(self.rf.get('/portal/', REMOTE_ADDR='192.0.2.9'))
        self.assertEqual(resp.status_code, 429)
