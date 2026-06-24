"""Tests de helpers Nat (routing cliente, scope RAG)."""

from django.test import TestCase, override_settings

from core.models import Cliente
from core.nati import armar_cliente_ids_rag, resolver_cliente_desde_numero_whatsapp


class NatiResolverClienteTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Finca Nat',
            contacto_principal='A',
            email='nat@test.co',
            telefono='573001110000',
            numero_whatsapp_nat='573009998877',
            activo=True,
        )

    @override_settings(BOT_COMERCIAL_CLIENTE_ID=0, BOT_COMERCIAL_WHATSAPP_NUMBER='')
    def test_resuelve_por_numero_whatsapp_nat(self):
        found = resolver_cliente_desde_numero_whatsapp('whatsapp:+573009998877')
        self.assertEqual(found, self.cliente)

    def test_resuelve_por_numero_global_bot(self):
        fallback = Cliente.objects.create(
            nombre='Global Nat',
            contacto_principal='B',
            email='g@test.co',
            telefono='573001112233',
            activo=True,
        )
        with self.settings(
            BOT_COMERCIAL_CLIENTE_ID=fallback.id,
            BOT_COMERCIAL_WHATSAPP_NUMBER='573001112233',
        ):
            found = resolver_cliente_desde_numero_whatsapp('573001112233')
        self.assertEqual(found, fallback)


class NatiRagScopeTests(TestCase):
    @override_settings(BOT_COMERCIAL_CLIENTE_ID=5)
    def test_armar_ids_incluye_cliente_y_general(self):
        cliente = Cliente(id=3, nombre='X')
        ids = armar_cliente_ids_rag(cliente)
        self.assertIn(3, ids)
        self.assertIn(0, ids)

    @override_settings(BOT_COMERCIAL_CLIENTE_ID=0)
    def test_armar_ids_solo_general_sin_cliente(self):
        ids = armar_cliente_ids_rag(None)
        self.assertEqual(ids, [0])
