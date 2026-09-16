"""Cuota diaria Nat (preguntas / 24h por teléfono)."""

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import WhatsappLog
from core.nat_cuota import evaluar_cuota_nat, mensaje_cuota_agotada


@override_settings(BOT_COMERCIAL_MAX_PREGUNTAS_DIA=3)
class NatCuotaTests(TestCase):
    def test_sin_mensajes_no_excede(self):
        excedida, usados, max_q = evaluar_cuota_nat('573001112233')
        self.assertFalse(excedida)
        self.assertEqual(usados, 0)
        self.assertEqual(max_q, 3)

    def test_excede_tras_max(self):
        tel = '573009998877'
        for i in range(4):
            WhatsappLog.objects.create(
                telefono=tel,
                mensaje=f'q{i}',
                tipo='INCOMING',
                agente_usado='BOT_COMERCIAL',
                fecha=timezone.now(),
            )
        excedida, usados, max_q = evaluar_cuota_nat(tel)
        self.assertTrue(excedida)
        self.assertEqual(usados, 4)
        self.assertEqual(max_q, 3)

    def test_mensaje_incluye_max(self):
        txt = mensaje_cuota_agotada(usados=5, max_q=3)
        self.assertIn('3', txt)
        self.assertIn('5', txt)


@override_settings(BOT_COMERCIAL_MAX_PREGUNTAS_DIA=0)
class NatCuotaDesactivadaTests(TestCase):
    def test_max_cero_nunca_excede(self):
        for i in range(10):
            WhatsappLog.objects.create(
                telefono='573001110000',
                mensaje=f'x{i}',
                tipo='INCOMING',
                agente_usado='BOT_COMERCIAL',
            )
        excedida, _, max_q = evaluar_cuota_nat('573001110000')
        self.assertFalse(excedida)
        self.assertEqual(max_q, 0)
