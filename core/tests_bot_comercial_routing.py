"""Tests enrutado Nat comercial vs bot educativo."""

from django.test import SimpleTestCase, TestCase, override_settings

from core.bot_comercial_routing import (
    es_destino_bot_comercial,
    es_numero_comercial_conocido,
    numeros_destino_comercial,
)
from core.models import Cliente
from core.nati import resolver_cliente_desde_numero_whatsapp


@override_settings(
    BOT_COMERCIAL_WHATSAPP_NUMBER='573001111111',
    BOT_COMERCIAL_SANDBOX_NUMBER='14155238886',
    BOT_COMERCIAL_FORCE_ROUTING=False,
    BOT_COMERCIAL_CLIENTE_ID=0,
)
class BotComercialRoutingTests(TestCase):
    def setUp(self):
        self.org_a = Cliente.objects.create(
            nombre='Org Nat A',
            contacto_principal='A',
            email='a@t.com',
            telefono='573000000001',
            activo=True,
            numero_whatsapp_nat='573009990001',
        )
        self.org_b = Cliente.objects.create(
            nombre='Org Nat B',
            contacto_principal='B',
            email='b@t.com',
            telefono='573000000002',
            activo=True,
            numero_whatsapp_nat='573009990002',
        )

    def test_global_es_comercial(self):
        self.assertTrue(es_destino_bot_comercial('whatsapp:+573001111111'))
        self.assertTrue(es_destino_bot_comercial({'To': 'whatsapp:+573001111111'}))

    def test_sandbox_es_comercial(self):
        self.assertTrue(es_destino_bot_comercial('whatsapp:+14155238886'))
        self.assertTrue(es_numero_comercial_conocido('14155238886'))

    def test_numero_org_es_comercial(self):
        self.assertTrue(es_destino_bot_comercial('whatsapp:+573009990001'))
        self.assertTrue(es_destino_bot_comercial({'To': '573009990002'}))

    def test_numero_educativo_no_es_comercial(self):
        self.assertFalse(es_destino_bot_comercial('whatsapp:+573008888888'))
        self.assertFalse(es_numero_comercial_conocido('573008888888'))

    def test_to_vacio_no_es_comercial(self):
        self.assertFalse(es_destino_bot_comercial(''))
        self.assertFalse(es_destino_bot_comercial({}))

    def test_numeros_destino_incluye_orgs(self):
        nums = numeros_destino_comercial()
        self.assertIn('573001111111', nums)
        self.assertIn('14155238886', nums)
        self.assertIn('573009990001', nums)
        self.assertIn('573009990002', nums)

    def test_resuelve_cliente_por_org(self):
        self.assertEqual(
            resolver_cliente_desde_numero_whatsapp('whatsapp:+573009990001').pk,
            self.org_a.pk,
        )
        self.assertEqual(
            resolver_cliente_desde_numero_whatsapp('573009990002').pk,
            self.org_b.pk,
        )


@override_settings(BOT_COMERCIAL_FORCE_ROUTING=True)
class BotComercialForceRoutingTests(SimpleTestCase):
    def test_force_routing_siempre_comercial(self):
        self.assertTrue(es_destino_bot_comercial('whatsapp:+573008888888'))
        self.assertTrue(es_destino_bot_comercial(''))
