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
        with patch('core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': 'w'}) as send:
            dispatch_sandbox_menu(_payload(tel, 'acepto'))
        titulos = []
        for call in send.call_args_list:
            body = call.args[0]
            inter = body.get('interactive') or {}
            if inter.get('type') == 'button':
                titulos = [b['reply']['title'] for b in inter['action']['buttons']]
        self.assertEqual(titulos, ['Formación', 'Asesoría'])

    def test_acepto_con_ficha_pide_la_cedula_y_no_el_curso(self):
        tel = '573009991003'
        Estudiante.objects.create(
            nombre='Julian',
            cedula='1014',
            telefono=tel,
            acepto_terminos=False,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, modo='cursos')
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as texto, \
                patch('core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': 'w'}) as send:
            ruta = dispatch_sandbox_menu(_payload(tel, 'acepto'))
        self.assertEqual(ruta, 'handled')
        self.assertIn('cédula', texto.call_args.args[2].lower())
        send.assert_not_called()
        est = Estudiante.objects.get(telefono=tel)
        self.assertEqual(est.estado_chat, 'ESPERANDO_CEDULA')
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=tel).modo, 'cursos')

    def test_iniciar_sin_habeas_pide_botones_aunque_el_modo_sea_formacion(self):
        tel = '573009991010'
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=False, modo='formacion')
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas:
            ruta = dispatch_sandbox_menu(_payload(tel, 'Iniciar'))
        self.assertEqual(ruta, 'handled')
        habeas.assert_called_once()

    def test_iniciar_citando_la_plantilla_pide_habeas(self):
        tel = '573009991011'
        citado = 'Bienvenida al curso.\nToque el botón para empezar.\nIniciar'
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas:
            ruta = dispatch_sandbox_menu(_payload(tel, citado))
        self.assertEqual(ruta, 'handled')
        habeas.assert_called_once()

    def test_iniciar_ya_activo_abre_menu_y_no_el_aviso_de_sin_curso(self):
        tel = '573009991012'
        Estudiante.objects.create(
            nombre='Julian',
            cedula='1016',
            telefono=tel,
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, modo='formacion')
        with patch('core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': 'w'}) as send, \
                patch('core.sandbox_menu.entrar_cursos_inscrito') as boot:
            ruta = dispatch_sandbox_menu(_payload(tel, 'Iniciar'))
        self.assertEqual(ruta, 'handled')
        boot.assert_not_called()
        titulos = []
        for call in send.call_args_list:
            body = call.args[0]
            inter = body.get('interactive') or {}
            if inter.get('type') == 'button':
                titulos = [b['reply']['title'] for b in inter['action']['buttons']]
        self.assertEqual(titulos, ['Formación', 'Asesoría'])
        textos = []
        for call in send.call_args_list:
            body = call.args[0]
            if body.get('type') == 'text':
                textos.append((body.get('text') or {}).get('body') or '')
            inter = body.get('interactive') or {}
            if inter.get('body'):
                textos.append((inter.get('body') or {}).get('text') or '')
        self.assertFalse(any('no abre cursos' in t.lower() for t in textos))

    def test_iniciar_esperando_cedula_vuelve_a_pedirla(self):
        tel = '573009991013'
        Estudiante.objects.create(
            nombre='Julian',
            cedula='1017',
            telefono=tel,
            acepto_terminos=True,
            estado_chat='ESPERANDO_CEDULA',
        )
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, modo='formacion')
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as texto, \
                patch('core.sandbox_menu.entrar_cursos_inscrito') as boot:
            ruta = dispatch_sandbox_menu(_payload(tel, 'Iniciar'))
        self.assertEqual(ruta, 'handled')
        boot.assert_not_called()
        self.assertIn('cédula', texto.call_args.args[2].lower())

    def test_continuemos_con_curso_abierto_entra_a_la_leccion(self):
        from core.models import Curso, ProgresoEstudiante

        tel = '573009991004'
        curso = Curso.objects.create(nombre='Innovación', activo=True, catalogo_menu=True)
        est = Estudiante.objects.create(
            nombre='Julian',
            cedula='1015',
            telefono=tel,
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, modo='formacion')
        ruta = dispatch_sandbox_menu(_payload(tel, 'continuemos'))
        self.assertEqual(ruta, 'cursos')
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=tel).modo, 'cursos')

    def test_continuemos_sin_aceptar_en_la_ficha_pide_habeas(self):
        from core.models import Curso, ProgresoEstudiante
        from core.views.webhook_meta import _aplicar_sandbox_menu

        tel = '573009991014'
        curso = Curso.objects.create(nombre='Tome las riendas de su dinero', activo=True)
        est = Estudiante.objects.create(
            nombre='Julian',
            cedula='1018',
            telefono=tel,
            acepto_terminos=False,
            estado_chat='ESPERANDO_HABEAS_DATA',
            estado_onboarding='nuevo',
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, modo='formacion')
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas, \
                patch('core.views.webhook_twilio._procesar_twilio_webhook_cuerpo') as cuerpo:
            resp = _aplicar_sandbox_menu(_payload(tel, 'continuemos', MessageSid='wamid.cont3'))
        self.assertEqual(resp.status_code, 200)
        habeas.assert_called_once()
        cuerpo.assert_not_called()
        est.refresh_from_db()
        self.assertFalse(est.acepto_terminos)
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')

    def test_listo_de_campana_pide_habeas_cedula_numero_y_menu(self):
        from core.campana_audiencia import poner_en_inicio_de_flujo

        tel = '573009991020'
        est = Estudiante.objects.create(
            nombre='Julian',
            cedula='1020',
            telefono=tel,
            tipo_documento='CC',
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, modo='cafe')
        poner_en_inicio_de_flujo(est)
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value={'success': True}) as habeas:
            ruta = dispatch_sandbox_menu(_payload(tel, 'Listo'))
        self.assertEqual(ruta, 'handled')
        habeas.assert_called_once()
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        self.assertFalse(est.acepto_terminos)

        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as texto:
            dispatch_sandbox_menu(_payload(tel, 'acepto'))
        self.assertIn('cédula', texto.call_args.args[2].lower())
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ESPERANDO_CEDULA')

        with patch('core.sandbox_canal.enviar_meta_botones', return_value={'success': True}) as botones:
            dispatch_sandbox_menu(_payload(tel, '1020'))
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'CONFIRMANDO_DATOS')
        cuerpo = botones.call_args.args[1]
        self.assertIn('1020', cuerpo)
        self.assertIn('573009991020', cuerpo.replace(' ', '').replace('+', ''))
        self.assertEqual([b[0] for b in botones.call_args.args[2]], ['si', 'no'])

        with patch('core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': 'w'}) as send:
            dispatch_sandbox_menu(_payload(tel, 'si'))
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ACTIVO')
        self.assertEqual(est.estado_onboarding, 'completado')
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
