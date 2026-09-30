"""Planes OP1/OP2/OP3 de la línea Meta, cupos del mes y racha dentro del mensaje."""
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.cursos_generales import NOMBRE_INNOVACION, NOMBRE_RIENDAS, NOMBRE_TIEMPO
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante, SandboxCanalSesion, WhatsappLog
from core.planes_linea import (
    PLAN_ASESOR_60,
    PLAN_CURSO_ASESOR,
    PLAN_DOS_CURSOS,
    TEXTO_PLAN_SIN_ASESOR,
    TEXTO_PLAN_SIN_CURSOS,
    TEXTO_SIN_PLAN,
    resolver_plan,
)
from core.sandbox_menu import dispatch_sandbox_menu

SANDBOX = '573009998888'
META = dict(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER=SANDBOX,
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    BOT_COMERCIAL_WHATSAPP_NUMBER='573001111111',
    SECURE_SSL_REDIRECT=False,
    LINEA_META_PLAN_DEFAULT='',
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


def _org(nombre, plan='', fin=None):
    return Cliente.objects.create(
        nombre=nombre,
        contacto_principal='x',
        email=f'{nombre.lower()}@eki.co',
        telefono='573000000000',
        plan_linea_meta=plan,
        fecha_fin_suscripcion=fin,
    )


def _cursos_catalogo():
    for nombre in (NOMBRE_RIENDAS, NOMBRE_INNOVACION, NOMBRE_TIEMPO):
        Curso.objects.create(nombre=nombre, descripcion='d', cliente=None, activo=True, catalogo_menu=True)


def _textos(send):
    salida = []
    for call in send.call_args_list:
        body = call.args[0]
        if body.get('type') == 'text':
            salida.append(body['text']['body'])
        elif body.get('type') == 'interactive':
            salida.append(body['interactive']['body']['text'])
    return salida


@override_settings(**META)
class ResolverPlanTests(TestCase):
    def setUp(self):
        self.tel = '573005550001'

    def test_sin_plan_ni_org_no_recibe_nada(self):
        plan = resolver_plan(self.tel)
        self.assertFalse(plan.activo)
        self.assertFalse(plan.incluye_cursos)
        self.assertFalse(plan.incluye_asesor)

    def test_plan_sale_de_la_organizacion(self):
        org = _org('Coop', PLAN_DOS_CURSOS)
        Estudiante.objects.create(nombre='A', cedula='P1', telefono=self.tel, cliente=org)
        plan = resolver_plan(self.tel)
        self.assertEqual((plan.cursos_mes, plan.preguntas_mes), (2, 0))

    @override_settings(SANDBOX_PROVEEDOR='twilio')
    def test_twilio_es_canal_de_demos_con_op1(self):
        plan = resolver_plan(self.tel)
        self.assertEqual(plan.clave, PLAN_CURSO_ASESOR)

    @override_settings(SANDBOX_PROVEEDOR='twilio')
    def test_twilio_demo_respeta_plan_de_la_persona(self):
        SandboxCanalSesion.objects.create(telefono=self.tel, plan=PLAN_DOS_CURSOS)
        self.assertEqual(resolver_plan(self.tel).clave, PLAN_DOS_CURSOS)

    def test_persona_manda_sobre_organizacion(self):
        org = _org('Coop', PLAN_DOS_CURSOS)
        Estudiante.objects.create(nombre='A', cedula='P2', telefono=self.tel, cliente=org)
        SandboxCanalSesion.objects.create(telefono=self.tel, plan=PLAN_ASESOR_60)
        plan = resolver_plan(self.tel)
        self.assertEqual((plan.cursos_mes, plan.preguntas_mes), (0, 60))

    def test_suscripcion_vencida_quita_el_plan(self):
        org = _org('Vieja', PLAN_CURSO_ASESOR, fin=date.today() - timedelta(days=1))
        Estudiante.objects.create(nombre='A', cedula='P3', telefono=self.tel, cliente=org)
        self.assertFalse(resolver_plan(self.tel).activo)

    @override_settings(LINEA_META_PLAN_DEFAULT=PLAN_CURSO_ASESOR)
    def test_default_configurable(self):
        plan = resolver_plan(self.tel)
        self.assertEqual((plan.cursos_mes, plan.preguntas_mes), (1, 30))


@override_settings(**META)
class MenuPorPlanTests(TestCase):
    def setUp(self):
        _cursos_catalogo()

    def _sesion(self, tel, plan=''):
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, plan=plan)

    def test_sin_plan_menu_sin_botones_y_todo_bloqueado(self):
        tel = '573005550010'
        self._sesion(tel)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(tel, 'hola'))
            dispatch_sandbox_menu(_payload(tel, 'formacion'))
            dispatch_sandbox_menu(_payload(tel, 'asesoria'))
            dispatch_sandbox_menu(_payload(tel, 'ver_riendas'))
        tipos = [c.args[0].get('type') for c in send.call_args_list]
        self.assertNotIn('interactive', tipos)
        self.assertEqual(_textos(send), [TEXTO_SIN_PLAN] * 4)
        self.assertFalse(Estudiante.objects.filter(telefono=tel).exists())

    def test_op2_solo_formacion_y_sin_asesor(self):
        tel = '573005550011'
        self._sesion(tel, PLAN_DOS_CURSOS)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(tel, 'hola'))
        botones = send.call_args.args[0]['interactive']['action']['buttons']
        self.assertEqual([b['reply']['id'] for b in botones], ['formacion'])
        self.assertIn('dos cursos', _textos(send)[0])
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(tel, 'asesoria'))
            dispatch_sandbox_menu(_payload(tel, 'nat'))
        self.assertEqual(_textos(send), [TEXTO_PLAN_SIN_ASESOR] * 2)

    def test_op3_solo_asesoria_y_sin_cursos(self):
        tel = '573005550012'
        self._sesion(tel, PLAN_ASESOR_60)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(tel, 'hola'))
        botones = send.call_args.args[0]['interactive']['action']['buttons']
        self.assertEqual([b['reply']['id'] for b in botones], ['asesoria'])
        self.assertIn('60', _textos(send)[0])
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(tel, 'formacion'))
            dispatch_sandbox_menu(_payload(tel, 'ver_tiempo'))
        self.assertEqual(_textos(send), [TEXTO_PLAN_SIN_CURSOS] * 2)
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante__telefono=tel).exists())

    def test_op3_muestra_60_preguntas_en_asesoria(self):
        tel = '573005550013'
        self._sesion(tel, PLAN_ASESOR_60)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(tel, 'asesoria'))
        self.assertIn('hasta 60 preguntas', _textos(send)[0])

    def test_sin_plan_puede_seguir_curso_que_ya_tenia(self):
        tel = '573005550014'
        self._sesion(tel)
        org = _org('SinPlan')
        est = Estudiante.objects.create(nombre='A', cedula='P4', telefono=tel, cliente=org)
        curso = Curso.objects.create(nombre='Curso finca', descripcion='d', cliente=org, activo=True)
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            out = dispatch_sandbox_menu(_payload(tel, 'curso'))
        self.assertEqual(out, 'handled')
        self.assertIn('Seguimos *Curso finca*', _textos(send)[0])


@override_settings(**META)
class CupoCursosTests(TestCase):
    def setUp(self):
        _cursos_catalogo()

    def _ver(self, tel, clave):
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(tel, f'ver_{clave}'))
        return _textos(send)[0]

    def test_op2_dos_cursos_y_el_tercero_espera(self):
        tel = '573005550020'
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, plan=PLAN_DOS_CURSOS)
        self.assertIn('Quedó en', self._ver(tel, 'riendas'))
        self.assertIn('Quedó en', self._ver(tel, 'tiempo'))
        tercero = self._ver(tel, 'innovacion')
        self.assertIn('2 por mes', tercero)
        self.assertEqual(ProgresoEstudiante.objects.filter(estudiante__telefono=tel).count(), 2)

    def test_curso_de_la_organizacion_cuenta_en_el_cupo(self):
        tel = '573005550021'
        org = _org('Coop1', PLAN_CURSO_ASESOR)
        est = Estudiante.objects.create(nombre='A', cedula='P5', telefono=tel, cliente=org)
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True)
        propio = Curso.objects.create(nombre='Curso de la coop', descripcion='d', cliente=org, activo=True)
        ProgresoEstudiante.objects.create(estudiante=est, curso=propio, completado=False)
        texto = self._ver(tel, 'riendas')
        self.assertIn('Curso de la coop', texto)
        self.assertIn('uno por mes', texto)

    def test_mes_anterior_no_cuenta(self):
        tel = '573005550022'
        SandboxCanalSesion.objects.create(telefono=tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)
        self._ver(tel, 'riendas')
        ProgresoEstudiante.objects.filter(estudiante__telefono=tel).update(
            fecha_inicio=timezone.now() - timedelta(days=40)
        )
        self.assertIn('Quedó en', self._ver(tel, 'tiempo'))


@override_settings(**META)
class ContadorAsesorTests(TestCase):
    def setUp(self):
        self.tel = '573005550030'
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)

    def _usadas(self):
        return SandboxCanalSesion.objects.get(telefono=self.tel).preguntas_mes

    def test_saludo_no_cuenta_y_pregunta_si(self):
        with patch('core.sandbox_canal._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'coach'))
            self.assertEqual(self._usadas(), 0)
            with patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta'):
                dispatch_sandbox_menu(_payload(self.tel, 'no tengo tiempo para estudiar'))
        self.assertEqual(self._usadas(), 1)

    def test_nat_cuenta_al_enrutar(self):
        with patch('core.sandbox_canal._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'nat'))
        self.assertEqual(dispatch_sandbox_menu(_payload(self.tel, 'tengo roya en el café')), 'nat')
        self.assertEqual(self._usadas(), 1)

    def test_tope_agotado_no_llama_ia(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(
            preguntas_mes=30, preguntas_mes_desde=timezone.localdate().replace(day=1)
        )
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'ventas'))
            with patch('core.sandbox_agentes.responder_agente_sandbox') as llm:
                dispatch_sandbox_menu(_payload(self.tel, 'cómo cobro más'))
        llm.assert_not_called()
        self.assertIn('ya usó las 30 preguntas', _textos(send)[-1])

    def test_memoria_del_agente_guarda_pregunta_y_respuesta(self):
        from core.sandbox_agentes import _historial_sandbox

        with patch('core.sandbox_canal.requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'w1'}]}
            dispatch_sandbox_menu(_payload(self.tel, 'coach'))
            with patch('core.sandbox_agentes.responder_agente_sandbox', side_effect=['R1', 'R2']):
                dispatch_sandbox_menu(_payload(self.tel, 'no tengo tiempo para estudiar'))
                dispatch_sandbox_menu(_payload(self.tel, 'y los fines de semana tampoco'))
        historial = [(m['role'], m['content']) for m in _historial_sandbox(self.tel, 'coach')]
        self.assertEqual(
            historial[-4:],
            [
                ('user', 'no tengo tiempo para estudiar'),
                ('assistant', 'R1'),
                ('user', 'y los fines de semana tampoco'),
                ('assistant', 'R2'),
            ],
        )

    def _posts(self, post):
        return [c.kwargs['json'] for c in post.call_args_list]

    def test_reaccion_espera_mientras_el_asesor_responde(self):
        from django.core.cache import cache

        cache.clear()
        with patch('core.sandbox_canal.requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'w1'}]}
            dispatch_sandbox_menu(_payload(self.tel, 'coach'))
            post.reset_mock()
            with patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R1'):
                pregunta = dict(_payload(self.tel, 'no tengo tiempo'), MessageSid='wamid.PREG1')
                dispatch_sandbox_menu(pregunta)
        tipos = [(p['type'], (p.get('reaction') or {}).get('emoji')) for p in self._posts(post)]
        self.assertEqual(tipos, [('reaction', '⏳'), ('text', None), ('reaction', '')])
        self.assertEqual(self._posts(post)[0]['reaction']['message_id'], 'wamid.PREG1')

    def test_menu_no_lleva_reaccion(self):
        with patch('core.sandbox_canal.requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'w1'}]}
            dispatch_sandbox_menu(dict(_payload(self.tel, 'hola'), MessageSid='wamid.HOLA'))
        self.assertNotIn('reaction', [p['type'] for p in self._posts(post)])

    @override_settings(SANDBOX_REACCION_ESPERA='')
    def test_reaccion_desactivable(self):
        with patch('core.sandbox_canal.requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'w1'}]}
            dispatch_sandbox_menu(_payload(self.tel, 'coach'))
            with patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R1'):
                dispatch_sandbox_menu(dict(_payload(self.tel, 'no tengo tiempo'), MessageSid='wamid.P2'))
        self.assertNotIn('reaction', [p['type'] for p in self._posts(post)])

    def test_nat_deja_reaccion_para_quitar_con_su_respuesta(self):
        from django.core.cache import cache

        from core.sandbox_canal import enviar_meta

        cache.clear()
        with patch('core.sandbox_canal.requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'w1'}]}
            dispatch_sandbox_menu(_payload(self.tel, 'nat'))
            ruta = dispatch_sandbox_menu(dict(_payload(self.tel, 'tengo roya en el café'), MessageSid='wamid.NAT1'))
            self.assertEqual(ruta, 'nat')
            self.assertEqual(self._posts(post)[-1]['reaction'], {'message_id': 'wamid.NAT1', 'emoji': '⏳'})
            enviar_meta(self.tel, 'Respuesta de Nat', agente_evento='sandbox_nat')
        self.assertEqual(self._posts(post)[-1]['reaction'], {'message_id': 'wamid.NAT1', 'emoji': ''})

    def test_mensajes_de_curso_no_gastan_preguntas(self):
        from core.sandbox_canal import enviar_meta

        with patch('core.sandbox_canal.requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'messages': [{'id': 'w1'}]}
            for _ in range(5):
                enviar_meta(self.tel, 'Clase 1', agente_evento='sandbox_cursos')
        self.assertEqual(self._usadas(), 0)
        self.assertEqual(
            WhatsappLog.objects.filter(telefono=self.tel, agente_usado='sandbox_cursos').count(), 5
        )


@override_settings(**META)
class RachaEnMensajeTests(TestCase):
    def setUp(self):
        self.tel = '573005550040'
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)

    def _ayer(self, dias):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(
            racha_actual=dias, racha_ultimo_dia=timezone.localdate() - timedelta(days=1)
        )

    def test_primer_mensaje_del_dia_lleva_racha_sin_mensaje_extra(self):
        self._ayer(3)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'hola'))
        self.assertEqual(send.call_count, 1)
        cuerpo = _textos(send)[0]
        self.assertTrue(cuerpo.startswith('🔥 Racha: 4 días seguidos'))
        self.assertIn('Elija una opción', cuerpo)
        ses = SandboxCanalSesion.objects.get(telefono=self.tel)
        self.assertEqual((ses.racha_actual, ses.racha_maxima, ses.aviso_pendiente), (4, 4, ''))

    def test_segundo_mensaje_del_dia_sin_racha(self):
        self._ayer(3)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'hola'))
            dispatch_sandbox_menu(_payload(self.tel, 'menu'))
        segundo = _textos(send)[1]
        self.assertNotIn('Racha', segundo)
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).racha_actual, 4)

    def test_dia_perdido_reinicia_sin_aviso(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(
            racha_actual=9, racha_maxima=9, racha_ultimo_dia=timezone.localdate() - timedelta(days=3)
        )
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'hola'))
        self.assertNotIn('Racha', _textos(send)[0])
        ses = SandboxCanalSesion.objects.get(telefono=self.tel)
        self.assertEqual((ses.racha_actual, ses.racha_maxima), (1, 9))

    def test_hito_de_racha_da_insignia_al_estudiante_en_el_mismo_mensaje(self):
        from core.gamificacion import Badge, BadgeEstudiante

        est = self._estudiante_con_racha_ayer(6)
        badge = Badge.objects.create(
            nombre='Semana firme', descripcion='7 días', icono='🌟', tipo='RACHA', valor_requerido=7
        )
        self._ayer(6)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'hola'))
        self.assertEqual(send.call_count, 1)
        cuerpo = _textos(send)[0]
        self.assertIn('🔥 Racha: 7 días', cuerpo)
        self.assertIn('Nueva insignia: *Semana firme*', cuerpo)
        self.assertTrue(BadgeEstudiante.objects.filter(estudiante=est, badge=badge).exists())

    def _estudiante_con_racha_ayer(self, dias):
        from core.gamificacion import PerfilGamificacion

        est = Estudiante.objects.create(nombre='A', cedula='R1', telefono=self.tel)
        PerfilGamificacion.objects.update_or_create(
            estudiante=est,
            defaults={
                'racha_dias_actual': dias,
                'racha_dias_maxima': dias,
                'ultima_actividad': timezone.now() - timedelta(days=1),
            },
        )
        return est

    def test_racha_del_estudiante_manda_sobre_el_contador_de_la_linea(self):
        self._estudiante_con_racha_ayer(10)
        self._ayer(2)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'hola'))
        self.assertTrue(_textos(send)[0].startswith('🔥 Racha: 11 días seguidos'))
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).racha_actual, 11)

    def test_hitos_salen_de_los_badges_del_admin(self):
        from core.gamificacion import Badge, BadgeEstudiante

        est = self._estudiante_con_racha_ayer(4)
        cinco = Badge.objects.create(nombre='Cinco', descripcion='5', icono='✋', tipo='RACHA', valor_requerido=5)
        Badge.objects.create(
            nombre='Apagado', descripcion='5', icono='x', tipo='RACHA', valor_requerido=5, activo=False, orden=-1
        )
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'hola'))
        self.assertIn('Nueva insignia: *Cinco*', _textos(send)[0])
        self.assertEqual(list(BadgeEstudiante.objects.filter(estudiante=est).values_list('badge', flat=True)), [cinco.pk])

    def test_sin_insignia_nueva_muestra_la_proxima(self):
        from core.gamificacion import Badge

        self._estudiante_con_racha_ayer(3)
        Badge.objects.create(nombre='Semana firme', descripcion='7', icono='🌟', tipo='RACHA', valor_requerido=7)
        with patch('core.sandbox_canal._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'hola'))
        self.assertIn('Próxima insignia: Semana firme (faltan 3 días)', _textos(send)[0])

    def test_sin_habeas_no_registra_actividad(self):
        tel = '573005550041'
        with patch('core.sandbox_canal.enviar_sandbox_habeas', return_value=OK):
            dispatch_sandbox_menu(_payload(tel, 'hola'))
        self.assertIsNone(SandboxCanalSesion.objects.get(telefono=tel).racha_ultimo_dia)
