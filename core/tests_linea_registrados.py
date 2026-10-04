"""Un número sin programa no llama al modelo. La campaña sí llega a la cédula."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.habeas_respuestas import aplicar_respuesta_habeas
from core.linea_registrados import debe_cortar, permitir_numero_nuevo
from core.models import Cliente, Estudiante
from core.planes_linea import resolver_plan
from core.sandbox_menu import dispatch_sandbox_menu

SANDBOX = '573009998888'


def _payload(tel, body):
    return {
        'From': f'whatsapp:+{tel}',
        'To': f'whatsapp:+{SANDBOX}',
        'Body': body,
        '_eki_proveedor': 'meta',
        '_eki_phone_number_id': '111222333',
    }


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER=SANDBOX,
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=True,
    LINEA_MAX_NUEVOS_DIA=2,
)
class SoloRegistradosTests(TestCase):
    def test_desconocido_no_llama_al_modelo(self):
        tel = '573009990001'
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as envio:
            with patch('core.openai_compat.completar_chat') as chat:
                salida = dispatch_sandbox_menu(_payload(tel, 'quiero el curso'))
        self.assertEqual(salida, 'handled')
        chat.assert_not_called()
        self.assertIn('programas eki', envio.call_args.args[2])
        self.assertFalse(Estudiante.objects.filter(telefono=tel).exists())
        self.assertFalse(resolver_plan(tel).activo)

    def test_campana_sigue_hasta_la_cedula(self):
        org = Cliente.objects.create(
            nombre='Campa',
            contacto_principal='x',
            email='campa@eki.co',
            telefono='573000000099',
        )
        est = Estudiante.objects.create(
            nombre='Ana',
            cedula='100200300',
            telefono='573009990002',
            cliente=org,
            estado_chat='ESPERANDO_HABEAS_DATA',
        )
        self.assertFalse(debe_cortar(est.telefono))
        aplicar_respuesta_habeas(est, 'acepto')
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ESPERANDO_CEDULA')

    def test_el_tercer_numero_nuevo_no_entra(self):
        class Redis:
            def __init__(self):
                self.miembros = set()

            def sismember(self, clave, marca):
                return marca in self.miembros

            def scard(self, clave):
                return len(self.miembros)

            def sadd(self, clave, marca):
                self.miembros.add(marca)

            def expire(self, clave, segundos):
                return True

        falso = Redis()
        with patch('core.linea_registrados._cliente_redis', return_value=falso):
            self.assertTrue(permitir_numero_nuevo('573009990011'))
            self.assertTrue(permitir_numero_nuevo('573009990012'))
            self.assertFalse(permitir_numero_nuevo('573009990013'))
