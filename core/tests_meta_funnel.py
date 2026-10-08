"""Embudo Meta: cualquier número → habeas (política eki) → Formación | Asesoría."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Cliente, Estudiante, SandboxCanalSesion
from core.planes_linea import PLAN_CURSO_ASESOR, resolver_plan
from core.sandbox_canal import _TEXTO_HABEAS_SANDBOX
from core.sandbox_menu import dispatch_sandbox_menu, es_destino_sandbox

SANDBOX = '573009998888'
META = dict(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER=SANDBOX,
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    LINEA_META_PLAN_DEFAULT='curso_asesor',
    LINEA_META_SOLO_REGISTRADOS=True,
    SECURE_SSL_REDIRECT=False,
)


def _payload(tel, body, **extra):
    data = {
        'From': f'whatsapp:+{tel}',
        'To': f'whatsapp:+{SANDBOX}',
        'Body': body,
        '_eki_proveedor': 'meta',
        '_eki_phone_number_id': '111222333',
    }
    data.update(extra)
    return data


@override_settings(**META)
class MetaFunnelTests(TestCase):
    def test_habeas_incluye_politica_eki(self):
        self.assertIn('https://www.eki.com.co/habeas-data', _TEXTO_HABEAS_SANDBOX)
        self.assertIn('Ley 1581', _TEXTO_HABEAS_SANDBOX)
        self.assertLessEqual(len(_TEXTO_HABEAS_SANDBOX), 1024)

    def test_inbound_meta_es_destino_aunque_el_to_no_coincida(self):
        self.assertTrue(es_destino_sandbox({
            'To': 'whatsapp:+573001111111',
            '_eki_proveedor': 'meta',
            '_eki_phone_number_id': '999',
        }))
        self.assertFalse(es_destino_sandbox({
            'To': 'whatsapp:+573001111111',
        }))

    def test_numero_nuevo_recibe_habeas_aunque_el_flag_pida_solo_registrados(self):
        tel = '573009991001'
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas:
            with patch('core.openai_compat.completar_chat') as chat:
                ruta = dispatch_sandbox_menu(_payload(tel, 'hola'))
        self.assertEqual(ruta, 'handled')
        habeas.assert_called_once()
        chat.assert_not_called()

    def test_acepto_abre_menu_formacion_asesoria(self):
        tel = '573009991002'
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=False)
        with patch('core.sandbox_canal._post_graph', return_value={'success': True, 'mensaje_id': 'w'}) as send:
            dispatch_sandbox_menu(_payload(tel, 'acepto'))
        titulos = []
        for call in send.call_args_list:
            body = call.args[0]
            inter = body.get('interactive') or {}
            if inter.get('type') == 'button':
                titulos = [b['reply']['title'] for b in inter['action']['buttons']]
        self.assertEqual(titulos, ['Formación', 'Asesoría'])

    def test_inscrito_con_telefono_local_toma_plan_de_la_org(self):
        org = Cliente.objects.create(
            nombre='OrgVar',
            contacto_principal='x',
            email='orgvar@eki.co',
            telefono='573000000088',
            activo=True,
            plan_linea_meta=PLAN_CURSO_ASESOR,
        )
        Estudiante.objects.create(
            nombre='Inscrita',
            cedula='V100',
            telefono='3005550199',
            cliente=org,
        )
        plan = resolver_plan('573005550199')
        self.assertEqual(plan.clave, PLAN_CURSO_ASESOR)
        self.assertTrue(plan.activo)
