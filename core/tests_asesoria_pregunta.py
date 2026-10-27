"""Asesoría por pregunta: «¿Qué quiere mejorar hoy?» y el modelo elige el agente."""
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.lineas.principal.derivar_asesoria import (
    AGENTE_PREGUNTA,
    AGENTE_REPREGUNTA,
    derivar,
    marcar_repregunta,
    olvidar_repregunta,
    temas,
    texto_pregunta,
    texto_repregunta,
)
from core.models import Cliente, SandboxCanalSesion, UsoLLM
from core.planes_linea import PLAN_CURSO_ASESOR
from core.sandbox_menu import dispatch_sandbox_menu
from core.tests_planes_linea import META, OK, _payload, _textos

TODOS = ['nat', 'coach', 'ia_campo', 'ventas', 'finanzas']
PREGUNTA = dict(META, EKI_ASESORIA_PREGUNTA=True, OPENAI_API_KEY='sk-test')


class TextosTests(TestCase):
    def test_temas_en_el_orden_de_la_pregunta(self):
        self.assertEqual(
            temas(TODOS),
            'su cultivo, sus ventas, sus cuentas, su ánimo o el uso de la tecnología',
        )

    def test_temas_solo_de_los_agentes_permitidos(self):
        self.assertEqual(temas(['finanzas', 'nat']), 'su cultivo o sus cuentas')
        self.assertEqual(temas(['coach']), 'su ánimo')

    def test_pregunta_con_cupo_y_salida_al_menu(self):
        texto = texto_pregunta(TODOS, 60)
        self.assertTrue(texto.startswith(
            '¿Qué quiere mejorar hoy: su cultivo, sus ventas, sus cuentas, su ánimo '
            'o el uso de la tecnología? Escríbalo con sus palabras.'
        ))
        self.assertIn('Tiene hasta 60 preguntas este mes.', texto)
        self.assertIn('*menu*', texto)
        self.assertNotIn('preguntas este mes', texto_pregunta(TODOS, 0))

    def test_repregunta_repite_los_temas(self):
        texto = texto_repregunta(['nat', 'ventas'])
        self.assertIn('No me quedó claro', texto)
        self.assertIn('¿Es sobre su cultivo o sus ventas?', texto)


@override_settings(OPENAI_API_KEY='sk-test', EKI_ASESORIA_MODELO='gpt-5-mini')
class DerivarTests(TestCase):
    def _derivar(self, respuesta, texto='la broca me está acabando el cafetal', permitidos=TODOS):
        with patch('core.presupuesto_llm.debe_degradar', return_value=False), \
                patch('core.openai_compat.cliente_openai', return_value='cli'), \
                patch('core.openai_compat.completar_chat', return_value=respuesta) as llm:
            salida = derivar(texto, telefono='573005559001', permitidos=permitidos)
        return salida, llm

    def test_el_modelo_elige_entre_los_permitidos(self):
        (agente, fuente), llm = self._derivar('nat')
        self.assertEqual((agente, fuente), ('nat', 'llm'))
        args = llm.call_args.args
        self.assertEqual(args[0], 'cli')
        self.assertEqual(args[1], 'gpt-5-mini')
        sistema = args[2][0]['content']
        self.assertIn('nat, ventas, finanzas, coach, ia_campo o ninguno', sistema)
        self.assertEqual(args[2][1]['content'], 'la broca me está acabando el cafetal')

    def test_lee_la_etiqueta_aunque_venga_con_adornos(self):
        self.assertEqual(self._derivar('Ventas.')[0], ('ventas', 'llm'))
        self.assertEqual(self._derivar('  ia_campo\n')[0], ('ia_campo', 'llm'))

    def test_ninguno_o_un_agente_no_permitido_es_none(self):
        self.assertEqual(self._derivar('ninguno')[0], (None, 'llm'))
        self.assertEqual(self._derivar('coach', permitidos=['nat', 'ventas'])[0], (None, 'llm'))

    def test_el_prompt_solo_ofrece_los_permitidos(self):
        _, llm = self._derivar('ventas', permitidos=['ventas', 'finanzas'])
        sistema = llm.call_args.args[2][0]['content']
        self.assertIn('ventas, finanzas o ninguno', sistema)
        self.assertNotIn('- nat:', sistema)

    def test_un_solo_agente_no_llama_al_modelo(self):
        (agente, fuente), llm = self._derivar('x', permitidos=['coach'])
        self.assertEqual((agente, fuente), ('coach', 'llm'))
        llm.assert_not_called()

    def test_texto_vacio_no_llama_al_modelo(self):
        (agente, fuente), llm = self._derivar('nat', texto='   ')
        self.assertEqual((agente, fuente), (None, 'llm'))
        llm.assert_not_called()

    def test_respuesta_vacia_es_sin_llm(self):
        self.assertEqual(self._derivar('')[0], (None, 'sin_llm'))

    def test_falla_de_la_api_es_sin_llm(self):
        def caida(**kwargs):
            raise RuntimeError('caída')

        cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=caida)))
        with patch('core.presupuesto_llm.debe_degradar', return_value=False), \
                patch('core.openai_compat.cliente_openai', return_value=cliente):
            self.assertEqual(derivar('precio', telefono='5730', permitidos=TODOS), (None, 'sin_llm'))

    def test_presupuesto_agotado_no_llama_al_modelo(self):
        with patch('core.presupuesto_llm.debe_degradar', return_value=True), \
                patch('core.openai_compat.completar_chat') as llm:
            self.assertEqual(derivar('precio', telefono='5730', permitidos=TODOS), (None, 'sin_llm'))
        llm.assert_not_called()

    @override_settings(OPENAI_API_KEY='')
    def test_sin_clave_no_llama_al_modelo(self):
        with patch('core.openai_compat.completar_chat') as llm:
            self.assertEqual(derivar('precio', telefono='5730', permitidos=TODOS), (None, 'sin_llm'))
        llm.assert_not_called()

    def test_el_costo_se_anota_a_la_derivacion_y_no_queda_pegado(self):
        from core.openai_compat import _uso

        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='finanzas'))],
            usage=None,
        )
        cliente = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: resp)),
        )
        with patch('core.presupuesto_llm.debe_degradar', return_value=False), \
                patch('core.openai_compat.cliente_openai', return_value=cliente):
            agente, _ = derivar('debo plata al banco', telefono='573005559002', permitidos=TODOS)
        self.assertEqual(agente, 'finanzas')
        self.assertEqual(UsoLLM.objects.get().agente, 'derivar_asesoria')
        self.assertIsNone(_uso.get())


class RepreguntaCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_solo_la_primera_vez(self):
        self.assertTrue(marcar_repregunta('5730'))
        self.assertFalse(marcar_repregunta('5730'))
        olvidar_repregunta('5730')
        self.assertTrue(marcar_repregunta('5730'))

    def test_si_la_cache_falla_sale_la_lista(self):
        from redis.exceptions import ConnectionError as RedisConnectionError

        with patch('django.core.cache.cache.add', side_effect=RedisConnectionError('redis')):
            self.assertFalse(marcar_repregunta('5730'))


@override_settings(**PREGUNTA)
class FlujoAsesoriaPreguntaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005559100'
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)

    def _modo(self):
        return SandboxCanalSesion.objects.get(telefono=self.tel).modo

    def _usadas(self):
        return SandboxCanalSesion.objects.get(telefono=self.tel).preguntas_mes

    def _abrir(self):
        with patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
        return send

    def test_asesoria_manda_la_pregunta_y_no_la_lista(self):
        send = self._abrir()
        textos = _textos(send)
        self.assertEqual(len(textos), 1)
        self.assertTrue(textos[0].startswith('¿Qué quiere mejorar hoy: su cultivo, sus ventas'))
        self.assertIn('hasta 60 preguntas', textos[0])
        self.assertNotEqual(send.call_args.args[0].get('type'), 'interactive')
        self.assertEqual(send.call_args.kwargs.get('agente'), AGENTE_PREGUNTA)
        self.assertEqual(self._modo(), 'asesoria')

    def test_el_dos_del_menu_tambien_manda_la_pregunta(self):
        with patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, '2'))
        self.assertTrue(_textos(send)[0].startswith('¿Qué quiere mejorar hoy'))

    def test_la_respuesta_va_al_agente_y_la_contesta_de_una(self):
        self._abrir()
        texto = 'quiero vender mi café a mejor precio'
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=('ventas', 'llm')) as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta ventas') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            ruta = dispatch_sandbox_menu(_payload(self.tel, texto))
        self.assertEqual(ruta, 'handled')
        self.assertEqual(der.call_args.args[0], texto)
        self.assertEqual(der.call_args.kwargs['permitidos'], TODOS)
        ag.assert_called_once()
        self.assertEqual(ag.call_args.args[:2], ('ventas', texto))
        self.assertIn('Respuesta ventas', _textos(send)[-1])
        self.assertEqual(self._modo(), 'ventas')
        self.assertEqual(self._usadas(), 1)

    def test_lo_que_sigue_se_queda_con_ese_agente(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=('finanzas', 'llm')), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R'), \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'tengo muchas deudas'))
        with patch('core.lineas.principal.derivar_asesoria.derivar') as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R2') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'y cómo ahorro'))
        der.assert_not_called()
        self.assertEqual(ag.call_args.args[0], 'finanzas')

    def test_cultivo_va_a_nat_que_responde_con_rag(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=('nat', 'llm')), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            ruta = dispatch_sandbox_menu(_payload(self.tel, 'las hojas del café se ponen amarillas'))
        self.assertEqual(ruta, 'nat')
        self.assertEqual(self._modo(), 'nat')
        self.assertEqual(self._usadas(), 1)
        self.assertEqual(_textos(send), [])

    def test_no_claro_repregunta_una_vez_y_despues_la_lista(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=(None, 'llm')), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'no sé'))
            repregunta = _textos(send)[-1]
            self.assertEqual(send.call_args.kwargs.get('agente'), AGENTE_REPREGUNTA)
            self.assertEqual(self._modo(), 'asesoria')
            dispatch_sandbox_menu(_payload(self.tel, 'pues lo de siempre'))
            lista = send.call_args.args[0]
        self.assertIn('No me quedó claro', repregunta)
        self.assertIn('su cultivo, sus ventas', repregunta)
        self.assertEqual(lista['interactive']['type'], 'list')
        self.assertEqual(self._modo(), 'agentes')
        self.assertEqual(self._usadas(), 0)

    def test_tras_la_repregunta_una_respuesta_clara_va_al_agente(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar', side_effect=[(None, 'llm'), ('coach', 'llm')]), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Ánimo') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'eh'))
            dispatch_sandbox_menu(_payload(self.tel, 'ando sin ganas de nada'))
        self.assertEqual(ag.call_args.args[:2], ('coach', 'ando sin ganas de nada'))
        self.assertEqual(self._modo(), 'coach')

    def test_volver_a_asesoria_reinicia_la_repregunta(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=(None, 'llm')), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'eh'))
            dispatch_sandbox_menu(_payload(self.tel, 'menu'))
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
            dispatch_sandbox_menu(_payload(self.tel, 'eh'))
        self.assertIn('No me quedó claro', _textos(send)[-1])

    def test_un_numero_suelto_no_abre_un_agente_ni_llama_al_modelo(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar') as der, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, '2'))
        der.assert_not_called()
        self.assertIn('No me quedó claro', _textos(send)[-1])
        self.assertEqual(self._modo(), 'asesoria')

    def test_el_nombre_del_agente_entra_con_su_saludo_sin_modelo(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar') as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'ventas'))
        der.assert_not_called()
        ag.assert_not_called()
        self.assertEqual(self._modo(), 'ventas')
        self.assertEqual(self._usadas(), 0)

    def test_menu_vuelve_al_menu(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar') as der, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'menu'))
        der.assert_not_called()
        self.assertEqual(self._modo(), 'menu')

    def test_sin_modelo_usa_las_palabras_clave(self):
        self._abrir()
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=(None, 'sin_llm')), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'tengo una deuda con el banco'))
        self.assertEqual(ag.call_args.args[0], 'finanzas')

    def test_sin_cupo_no_gasta_modelo_y_avisa(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(preguntas_mes=60)
        self._abrir()
        with patch('core.sandbox_agentes.excedio_cupo_ia_linea', return_value=True), \
                patch('core.lineas.principal.derivar_asesoria.derivar') as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'quiero subir el precio del café'))
        der.assert_not_called()
        ag.assert_not_called()
        self.assertEqual(self._modo(), 'ventas')
        self.assertTrue(_textos(send))


@override_settings(**PREGUNTA)
class AgentesDeLaLineaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005559200'
        self.org = Cliente.objects.create(
            nombre='Coop asesoría',
            contacto_principal='x',
            email='coop-asesoria@eki.co',
            telefono='573000000000',
            phone_id_meta='111222333',
            agentes_linea='nat,ventas',
        )
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)

    def test_la_pregunta_solo_nombra_los_temas_de_la_linea(self):
        with patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
        self.assertIn('¿Qué quiere mejorar hoy: su cultivo o sus ventas?', _textos(send)[0])

    def test_el_modelo_solo_elige_entre_los_de_la_linea(self):
        with patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=('nat', 'llm')) as der, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'mis vacas no comen'))
        self.assertEqual(der.call_args.kwargs['permitidos'], ['nat', 'ventas'])

    def test_un_agente_fuera_de_la_linea_no_se_abre(self):
        with patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=('coach', 'llm')), \
                patch('core.sandbox_agentes.responder_agente_sandbox') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'ando desanimado'))
        ag.assert_not_called()
        self.assertIn('No me quedó claro', _textos(send)[-1])

    def test_linea_sin_agentes_muestra_el_aviso_de_siempre(self):
        Cliente.objects.filter(pk=self.org.pk).update(agentes_linea='ninguno_valido')
        with patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
        self.assertIn('En esta línea no hay agentes', _textos(send)[0])


@override_settings(**META, OPENAI_API_KEY='sk-test')
class FlagApagadoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005559300'
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)

    def test_sin_flag_sigue_la_lista_y_las_palabras_clave(self):
        with patch('core.lineas.principal.derivar_asesoria.derivar') as der, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
            self.assertEqual(send.call_args.args[0]['interactive']['type'], 'list')
            dispatch_sandbox_menu(_payload(self.tel, 'cómo subo el precio a mis clientes'))
        der.assert_not_called()
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, 'ventas')
