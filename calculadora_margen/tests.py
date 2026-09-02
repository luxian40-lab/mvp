from django.test import Client, TestCase, override_settings
from unittest.mock import patch

from calculadora_margen.models import CalculoMargen
from calculadora_margen.services.calculo import calcular_margen, margen_para_precio


class CalculoMargenServiceTests(TestCase):
    def test_formulas_ejemplo_tomate(self):
        r = calcular_margen(
            producto='Tomate cherry',
            cantidad_producida=100,
            unidad='kg',
            materias_primas=200_000,
            mano_obra=150_000,
            transporte=30_000,
            empaque=20_000,
            otros_costos=10_000,
            costos_fijos=100_000,
            precio_actual=8_000,
        )
        self.assertEqual(r['total_variable'], 410_000)
        self.assertAlmostEqual(r['costo_unitario'], 5100.0, places=0)
        self.assertAlmostEqual(r['margen_actual'], 36.25, places=1)
        self.assertEqual(r['nivel_alerta'], 'saludable')
        self.assertEqual(r['mayor_costo_clave'], 'materias_primas')

    def test_margen_bajo(self):
        r = calcular_margen(
            producto='Queso',
            cantidad_producida=50,
            unidad='unidades',
            materias_primas=500_000,
            mano_obra=200_000,
            transporte=0,
            empaque=0,
            otros_costos=0,
            costos_fijos=0,
            precio_actual=10_000,
        )
        self.assertEqual(r['nivel_alerta'], 'bajo')
        self.assertLess(r['margen_actual'], 15)

    def test_cantidad_cero_falla(self):
        with self.assertRaises(ValueError):
            calcular_margen(
                producto='X',
                cantidad_producida=0,
                unidad='kg',
                precio_actual=1000,
            )

    def test_simular_precio(self):
        m = margen_para_precio(5000, 8000)
        self.assertAlmostEqual(m, 37.5, places=1)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, EKI_DISABLE_HOST_ISOLATION=True)
class CalculadoraMargenAPITests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def _csrf(self):
        r = self.client.get('/calculadora-margen/', follow=True)
        token = r.cookies.get('csrftoken')
        return token.value if token else ''

    def test_landing_200(self):
        r = self.client.get('/calculadora-margen/', follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '¿Realmente estás ganando plata')
        self.assertContains(r, 'eki-logo.png')

    def test_api_calcular_sin_persistir(self):
        payload = {
            'producto': 'Miel',
            'cantidad_producida': 20,
            'unidad': 'litros',
            'materias_primas': 100000,
            'mano_obra': 50000,
            'transporte': 10000,
            'empaque': 5000,
            'otros_costos': 0,
            'costos_fijos': 20000,
            'precio_actual': 15000,
        }
        r = self.client.post(
            '/calculadora-margen/api/calcular/',
            data=payload,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self._csrf(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertNotIn('calculo_id', data)
        self.assertEqual(CalculoMargen.objects.count(), 0)

    @patch('calculadora_margen.views.generar_recomendaciones_ia')
    def test_api_recomendaciones_sin_persistir(self, mock_ia):
        mock_ia.return_value = {
            'resumen': 'Margen ajustado.',
            'recomendaciones': ['A', 'B', 'C', 'D', 'E'],
        }
        datos = calcular_margen(
            producto='Café',
            cantidad_producida=10,
            unidad='kg',
            materias_primas=50000,
            mano_obra=30000,
            transporte=0,
            empaque=0,
            otros_costos=0,
            costos_fijos=10000,
            precio_actual=20000,
        )
        r = self.client.post(
            '/calculadora-margen/api/recomendaciones/',
            data={'datos': datos},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self._csrf(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['recomendaciones']), 5)
        self.assertEqual(CalculoMargen.objects.count(), 0)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, EKI_DISABLE_HOST_ISOLATION=True)
class MargenEnlacesTests(TestCase):
    def setUp(self):
        from core.models import Cliente

        self.cliente = Cliente.objects.create(
            nombre='Cooperativa ACME Valle',
            contacto_principal='Ana',
            email='ana@acme.test',
            telefono='573000000001',
        )

    def test_crea_slug_y_urls(self):
        from calculadora_margen.links import obtener_o_crear_enlace, urls_margen_cliente

        enlace = obtener_o_crear_enlace(self.cliente)
        self.assertTrue(enlace.slug)
        self.assertTrue(enlace.token)
        urls = urls_margen_cliente(self.cliente, curso_id=22)
        self.assertIn(f'?org={enlace.slug}', urls['url_org'])
        self.assertIn('&curso=22', urls['url_org'])
        self.assertIn(f'?t={enlace.token}', urls['url_token'])

    def test_resolver_org_slug(self):
        from calculadora_margen.links import obtener_o_crear_enlace, resolver_cliente_id

        enlace = obtener_o_crear_enlace(self.cliente)
        self.assertEqual(resolver_cliente_id(org=enlace.slug), self.cliente.pk)

    def test_evento_con_org_en_query(self):
        from calculadora_margen.links import obtener_o_crear_enlace
        from calculadora_margen.models import MargenUsoEvento

        enlace = obtener_o_crear_enlace(self.cliente)
        c = Client(enforce_csrf_checks=True)
        r = c.get(f'/calculadora-margen/?org={enlace.slug}&curso=22', follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(MargenUsoEvento.objects.filter(cliente=self.cliente).count(), 1)
