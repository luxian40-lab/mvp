"""El teléfono no sale en Sentry. /health/deep/ no es público."""
from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.sentry_eki import limpiar_evento


class ScrubTests(SimpleTestCase):
    def test_el_telefono_no_sale(self):
        evento = {
            'exception': {'values': [{'value': 'fallo del 573009993001 al enviar'}]},
            'request': {
                'data': 'cuerpo con 573009993001',
                'headers': {'Authorization': 'Bearer secreto', 'Accept': 'json'},
            },
        }
        limpio = limpiar_evento(evento)
        texto = str(limpio)
        self.assertNotIn('573009993001', texto)
        self.assertNotIn('secreto', texto)
        self.assertEqual(limpio['request']['data'], '[omitido]')
        self.assertEqual(limpio['request']['headers']['Authorization'], '[omitido]')
        self.assertIn('[telefono]', limpio['exception']['values'][0]['value'])


@override_settings(SECURE_SSL_REDIRECT=False, EKI_INFRA_HEALTH_TOKEN='token-de-prueba')
class HealthDeepTests(TestCase):
    def setUp(self):
        self.http = Client()
        User.objects.create_user('obs_staff', 'o@t.com', 'pass', is_staff=True)

    def test_anonimo_recibe_403(self):
        self.assertEqual(self.http.get('/health/deep/').status_code, 403)

    def test_staff_entra(self):
        self.http.login(username='obs_staff', password='pass')
        respuesta = self.http.get('/health/deep/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('latido', respuesta.json())
        self.assertIn('canal_vacio_24h', respuesta.json())

    def test_token_de_infra_entra(self):
        respuesta = self.http.get(
            '/health/deep/',
            HTTP_X_EKI_INFRA_TOKEN='token-de-prueba',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('token-de-prueba', respuesta.content.decode())
