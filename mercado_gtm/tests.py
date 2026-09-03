"""Tests capa determinística mercado_gtm."""
import json

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from mercado_gtm.services.calculos import (
    calcular_escenario_completo,
    calcular_sam,
    calcular_som,
    calcular_tam,
    simular,
)


class CalculosMercadoTests(SimpleTestCase):
    def test_tam_basico(self):
        r = calcular_tam(ticket_mensual=100_000, alcance='local')
        self.assertGreater(r['tam'], 0)
        self.assertEqual(r['trazabilidad']['tipo'], 'supuesto')

    def test_tam_con_clientes_dato(self):
        r = calcular_tam(ticket_mensual=50_000, alcance='local', clientes_estimados=10)
        self.assertEqual(r['tam'], 500_000.0)
        self.assertEqual(r['trazabilidad']['tipo'], 'dato')

    def test_sam_crece_con_segmentos(self):
        a = calcular_sam(tam=1_000_000, segmentos=['tiendas'])
        b = calcular_sam(tam=1_000_000, segmentos=['tiendas', 'hoteles', 'asociaciones'])
        self.assertGreater(b['sam'], a['sam'])

    def test_som_no_supera_capacidad(self):
        r = calcular_som(sam=1_000_000, precio=1000, capacidad_unidades=10)
        self.assertEqual(r['som_ambicioso'], 10_000.0)
        self.assertEqual(r['som_base'], 10_000.0)
        self.assertEqual(r['capacidad_valor'], 10_000.0)

    def test_escenario_completo(self):
        r = calcular_escenario_completo(
            producto='Panela pulverizada',
            precio=8000,
            ticket_mensual=120_000,
            alcance='departamental',
            segmentos=['tiendas saludables', 'cafés'],
            capacidad_unidades=200,
            mercado_objetivo='Bogotá',
        )
        self.assertEqual(r['producto'], 'Panela pulverizada')
        self.assertGreater(r['tam'], r['sam'])
        self.assertGreaterEqual(r['sam'], r['som_ambicioso'])
        self.assertIn(r['confianza_estimacion'], ('alta', 'media', 'baja'))

    def test_simular_espejo(self):
        s = simular(
            sam=500_000,
            clientes=5,
            ticket=100_000,
            precio=8000,
            participacion_pct=3,
            capacidad_unidades=1000,
        )
        self.assertEqual(s['ventas_mensuales'], 500_000.0)
        self.assertGreater(s['som'], 0)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, EKI_DISABLE_HOST_ISOLATION=True)
class ApiCalcularSmokeTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def _csrf(self):
        r = self.client.get('/mercado-gtm/', follow=True)
        token = r.cookies.get('csrftoken')
        return token.value if token else ''

    def test_calcular_sin_ia(self):
        token = self._csrf()
        url = reverse('mercado_gtm_calcular')
        resp = self.client.post(
            url,
            data=json.dumps({
                'producto': 'Huevos',
                'precio': 500,
                'ticket_mensual_estimado': 80000,
                'alcance': 'local',
                'segmentos_cliente': ['vecinos', 'plaza'],
                'guardar': False,
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(resp.status_code, 200, resp.content[:500])
        body = resp.json()
        self.assertTrue(body.get('success'))
        self.assertGreater(body['tam'], 0)
