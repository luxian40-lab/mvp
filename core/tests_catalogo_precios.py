from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.catalogo_precios import (
    buscar_precios,
    es_consulta_catalogo,
    formatear_contexto_precios,
)
from core.models import Cliente, ProductoComercial


class CatalogoPreciosTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Preserva Test')
        ProductoComercial.objects.create(
            cliente=self.cliente,
            sku='UREA-46',
            nombre='Urea 46% granular',
            presentacion='bulto 50 kg',
            unidad='bulto',
            precio=Decimal('185000'),
            categoria='fertilizante',
        )
        ProductoComercial.objects.create(
            cliente=None,
            sku='GLIF-360',
            nombre='Glifosato 360 g/L',
            presentacion='garrafa 1 L',
            unidad='litro',
            precio=Decimal('42000'),
            categoria='herbicida',
        )

    def test_detecta_consulta_catalogo(self):
        self.assertTrue(es_consulta_catalogo('¿Cuánto cuesta la urea?'))
        self.assertFalse(es_consulta_catalogo('¿Cómo controlar la roya?'))

    def test_buscar_precios_por_cliente(self):
        hits = buscar_precios([self.cliente.id, 0], 'precio urea')
        skus = {p.sku for p in hits}
        self.assertIn('UREA-46', skus)

    def test_formatear_contexto_incluye_cifra(self):
        hits = buscar_precios([self.cliente.id], 'urea')
        texto = formatear_contexto_precios(hits)
        self.assertIn('185.000', texto)
        self.assertIn('LISTA DE PRECIOS OFICIAL', texto)

    def test_vigencia_expirada_no_aparece(self):
        ProductoComercial.objects.create(
            cliente=self.cliente,
            sku='VENCIDO',
            nombre='Producto vencido',
            precio=Decimal('1000'),
            vigencia_hasta=timezone.localdate().replace(year=2020),
        )
        hits = buscar_precios([self.cliente.id], 'vencido')
        self.assertEqual([p.sku for p in hits], [])
