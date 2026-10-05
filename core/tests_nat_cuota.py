"""Cuota Nat: el módulo existe y no tumba el webhook si falla."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import SandboxCanalSesion, WhatsappLog
from core.nat_cuota import evaluar_cuota_nat, mensaje_cuota_agotada
from core.views.webhook_meta import _aplicar_sandbox_menu


@override_settings(BOT_COMERCIAL_MAX_PREGUNTAS_DIA=0, SECURE_SSL_REDIRECT=False)
class NatCuotaTests(TestCase):
    def test_tope_cero_no_bloquea(self):
        excedida, usados, tope = evaluar_cuota_nat('573001110040')
        self.assertFalse(excedida)
        self.assertEqual(usados, 0)
        self.assertEqual(tope, 0)

    def test_cuenta_incoming_bot_comercial(self):
        with override_settings(BOT_COMERCIAL_MAX_PREGUNTAS_DIA=2):
            WhatsappLog.objects.create(
                telefono='573001110041',
                mensaje='q',
                tipo='INCOMING',
                agente_usado='BOT_COMERCIAL',
            )
            WhatsappLog.objects.create(
                telefono='573001110041',
                mensaje='q2',
                tipo='INCOMING',
                agente_usado='BOT_COMERCIAL',
            )
            excedida, usados, tope = evaluar_cuota_nat('573001110041')
        self.assertEqual(tope, 2)
        self.assertEqual(usados, 2)
        self.assertFalse(excedida)

    def test_mensaje_no_lleva_telefono(self):
        texto = mensaje_cuota_agotada(usados=41, max_q=40)
        self.assertIn('40', texto)
        self.assertNotIn('573', texto)


@override_settings(
    SANDBOX_MENU_ENABLED=True,
    SANDBOX_PROVEEDOR='meta',
    BOT_COMERCIAL_SANDBOX_NUMBER='14155238886',
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=False,
    SANDBOX_CELERY_ASYNC=False,
    NAT_WEBHOOK_CELERY_ASYNC=False,
    SECURE_SSL_REDIRECT=False,
)
class NatSandboxRespuestaTests(TestCase):
    def test_si_nat_explota_igual_contesta(self):
        tel = '573001110042'
        SandboxCanalSesion.objects.create(
            telefono=tel, habeas_aceptado=True, modo='nat', plan='asesor_60',
        )
        inbound = {
            'From': f'whatsapp:+{tel}',
            'To': 'whatsapp:+14155238886',
            'Body': 'mi platano tiene manchas',
            'MessageSid': 'wamid.nat-test-1',
        }
        with patch(
            'core.bot_comercial.webhook._procesar_bot_comercial_twilio_webhook',
            side_effect=RuntimeError('nat_cuota missing'),
        ), patch(
            'core.sandbox_menu._reaccion_espera',
        ), patch(
            'core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}
        ) as send:
            resp = _aplicar_sandbox_menu(inbound)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(send.called)
        self.assertIn('agrónomo', send.call_args.args[2])
