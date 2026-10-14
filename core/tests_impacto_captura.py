"""Cierres B de impacto en agentes. No se inventa el porcentaje."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.impacto_captura import anexar_cierre, capturar_si_pendiente
from core.models import Cliente, Estudiante, SandboxCanalSesion, WhatsappLog
from core.sandbox_menu import dispatch_sandbox_menu
from portal.impacto import impacto_nucleo

SANDBOX = '573009998888'
META = dict(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER=SANDBOX,
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=False,
    SECURE_SSL_REDIRECT=False,
)
OK = {'success': True, 'mensaje_id': 'wamid.x'}


def _payload(tel, body):
    return {
        'From': f'whatsapp:+{tel}',
        'To': f'whatsapp:+{SANDBOX}',
        'Body': body,
        '_eki_proveedor': 'meta',
        '_eki_phone_number_id': '111222333',
    }


@override_settings(**META)
class ImpactoCapturaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Cliente.objects.create(
            nombre='ImpCap',
            contacto_principal='x',
            email='impcap@eki.co',
            telefono='573000000077',
            activo=True,
            plan_linea_meta='curso_asesor',
        )
        self.tel = '573009992001'
        self.est = Estudiante.objects.create(
            nombre='Luz',
            cedula='IMP1',
            telefono=self.tel,
            cliente=self.org,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True)

    def test_finanzas_no_guarda_impacto_mientras_esta_pausada(self):
        with patch('core.sandbox_canal._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'finanzas'))
            with patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Revise el flujo de caja.'):
                dispatch_sandbox_menu(_payload(self.tel, 'cómo ordeno gastos'))
            dispatch_sandbox_menu(_payload(self.tel, 'sí'))
        self.est.refresh_from_db()
        self.assertNotIn('E1', self.est.impacto_respuestas or {})

    def test_tablero_usa_la_captura_sin_inventar(self):
        WhatsappLog.objects.create(
            telefono=self.tel, mensaje='hola', tipo='INCOMING', estudiante=self.est,
        )
        self.est.impacto_respuestas = {
            'E1': {'valor': 'si', 'positivo': True, 'evidencia': 'B'},
        }
        self.est.save(update_fields=['impacto_respuestas'])
        e1 = impacto_nucleo(self.org)['por_codigo']['E1']
        self.assertEqual(e1['estado'], 'ok')
        self.assertEqual(e1['numerador'], 1)
        self.assertEqual(e1['denominador'], 1)
        self.assertEqual(e1['evidencia'], 'B')
        self.assertIsNone(e1['pct'])

    def test_anexar_no_repite_si_ya_respondio(self):
        self.est.impacto_respuestas = {'E1': {'valor': 'no', 'positivo': False}}
        self.est.save(update_fields=['impacto_respuestas'])
        texto = anexar_cierre('finanzas', self.tel, 'Ok.')
        self.assertEqual(texto, 'Ok.')
        self.assertIsNone(capturar_si_pendiente(self.tel, 'sí'))

    def test_ningun_agente_pregunta_impacto_mientras_esta_pausada(self):
        with override_settings(PREGUNTA_IMPACTO_AGENTES=False):
            for agente in ('nat', 'finanzas', 'ventas', 'ia_campo'):
                texto = anexar_cierre(agente, self.tel, 'Revise el lote.')
                self.assertEqual(texto, 'Revise el lote.')
        self.assertIsNone(capturar_si_pendiente(self.tel, 'sí'))

    def test_finanzas_no_anexa_impacto_en_el_agente(self):
        with override_settings(PREGUNTA_IMPACTO_AGENTES=True):
            with patch('core.sandbox_canal._post_graph', return_value=OK):
                dispatch_sandbox_menu(_payload(self.tel, 'finanzas'))
            with patch(
                'core.sandbox_agentes.responder_agente_sandbox',
                return_value='Revise el flujo de caja.',
            ):
                with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
                    dispatch_sandbox_menu(_payload(self.tel, 'cómo ordeno gastos'))
        textos = []
        for call in send.call_args_list:
            body = call.args[0]
            if body.get('type') == 'text':
                textos.append((body.get('text') or {}).get('body') or '')
            inter = body.get('interactive') or {}
            if inter.get('body'):
                textos.append((inter.get('body') or {}).get('text') or '')
        junto = ' '.join(textos).lower()
        self.assertIn('flujo de caja', junto)
        self.assertNotIn('reporte de impacto', junto)
        self.assertNotIn('gastos del predio', junto)

    def test_nat_pregunta_impacto_si_se_reactiva(self):
        with override_settings(PREGUNTA_IMPACTO_AGENTES=True):
            texto = anexar_cierre('nat', self.tel, 'Revise el lote.')
        self.assertIn('clima o Nat', texto)

    def test_no_repite_pregunta_mientras_espera_respuesta(self):
        with override_settings(PREGUNTA_IMPACTO_AGENTES=True):
            primero = anexar_cierre('finanzas', self.tel, 'A')
            self.assertIn('gastos del predio', primero)
            self.assertEqual(anexar_cierre('finanzas', self.tel, 'B'), 'B')
