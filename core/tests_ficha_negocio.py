"""Ficha del negocio: contexto para derivar y las tres preguntas de a una."""
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from core.lineas.principal.contexto_asesoria import contexto_persona, ultimo_agente
from core.lineas.principal.derivar_asesoria import CIERRE, derivar_detalle
from core.lineas.principal.ficha_negocio import (
    AGENTE_FICHA,
    GRACIAS,
    SALTADA,
    SIN_PREGUNTA_FINAL,
    siguiente_pregunta,
)
from core.models import DerivacionAsesoria, FichaNegocio, SandboxCanalSesion, WhatsappLog
from core.planes_linea import PLAN_CURSO_ASESOR
from core.sandbox_menu import dispatch_sandbox_menu
from core.tests_asesoria_pregunta import PREGUNTA
from core.tests_planes_linea import OK, _payload, _textos

CONTEXTO = dict(PREGUNTA, EKI_ASESORIA_CONTEXTO=True)


class ContextoPersonaTests(TestCase):
    tel = '573005558001'

    def test_sin_datos_no_hay_contexto(self):
        self.assertEqual(contexto_persona(self.tel), '')
        self.assertEqual(contexto_persona(''), '')

    def test_la_ficha_entra_en_lineas_cortas(self):
        FichaNegocio.objects.create(telefono=self.tel, dedica='café y plátano', etapa='vende', equipo='familia')
        self.assertEqual(
            contexto_persona(self.tel),
            '- Se dedica a: café y plátano\n- Su negocio: ya vende\n- Trabaja: con su familia',
        )

    def test_ultimo_asesor_sin_correo_ni_telefono(self):
        WhatsappLog.objects.create(
            telefono=self.tel,
            tipo='INCOMING',
            agente_usado='sandbox_finanzas',
            mensaje='debo dos cuotas, llámeme al 3001234567 o a pepe@correo.co',
        )
        texto = contexto_persona(self.tel)
        self.assertIn('Último asesor: Finanzas.', texto)
        self.assertNotIn('3001234567', texto)
        self.assertNotIn('pepe@correo.co', texto)

    def test_nat_cuenta_como_agronomo(self):
        WhatsappLog.objects.create(
            telefono=self.tel, tipo='INCOMING', agente_usado='BOT_COMERCIAL', mensaje='la broca',
        )
        self.assertEqual(ultimo_agente(self.tel), ('nat', 'la broca'))

    def test_lo_de_hace_mas_de_30_dias_no_cuenta(self):
        log = WhatsappLog.objects.create(
            telefono=self.tel, tipo='INCOMING', agente_usado='sandbox_ventas', mensaje='precio',
        )
        WhatsappLog.objects.filter(pk=log.pk).update(fecha=timezone.now() - timedelta(days=31))
        self.assertIsNone(ultimo_agente(self.tel))

    def test_los_mensajes_que_salen_no_cuentan(self):
        WhatsappLog.objects.create(
            telefono=self.tel, tipo='OUTGOING', agente_usado='sandbox_ventas', mensaje='respuesta',
        )
        self.assertIsNone(ultimo_agente(self.tel))


class PerfilEnElPromptTests(TestCase):
    tel = '573005558401'

    def setUp(self):
        cache.clear()
        FichaNegocio.objects.create(telefono=self.tel, dedica='cacao', equipo='trabajadores')

    def _sistema(self, **kwargs):
        from core.sandbox_agentes import responder_agente_sandbox

        with patch('core.presupuesto_llm.debe_degradar', return_value=False), \
                patch('openai.OpenAI'), \
                patch('core.openai_compat.completar_chat', return_value='R') as llm:
            responder_agente_sandbox('ventas', 'cómo vendo más', telefono=self.tel, **kwargs)
        return llm.call_args.args[2][0]['content']

    @override_settings(OPENAI_API_KEY='sk-test', EKI_ASESORIA_CONTEXTO=True)
    def test_cuando_toca_la_ficha_el_prompt_pide_cerrar_sin_pregunta(self):
        self.assertTrue(self._sistema(sin_pregunta_final=True).endswith(SIN_PREGUNTA_FINAL))
        self.assertNotIn(SIN_PREGUNTA_FINAL, self._sistema())

    @override_settings(EKI_ASESORIA_CONTEXTO=False)
    def test_sin_flag_no_hay_bloque(self):
        from core.lineas.principal.contexto_asesoria import bloque_perfil

        self.assertEqual(bloque_perfil(self.tel), '')

    @override_settings(EKI_ASESORIA_CONTEXTO=True)
    def test_con_flag_el_bloque_dice_que_no_lo_recite(self):
        from core.lineas.principal.contexto_asesoria import bloque_perfil

        bloque = bloque_perfil(self.tel)
        self.assertTrue(bloque.startswith('LO QUE SABEMOS DE LA PERSONA'))
        self.assertIn('no lo recite', bloque)
        self.assertIn('- Se dedica a: cacao', bloque)
        self.assertEqual(bloque_perfil('573009999999'), '')

    @override_settings(OPENAI_API_KEY='sk-test', EKI_ASESORIA_CONTEXTO=True)
    def test_los_agentes_leen_el_perfil(self):
        sistema = self._sistema()
        self.assertIn('LO QUE SABEMOS DE LA PERSONA', sistema)
        self.assertIn('- Trabaja: con trabajadores', sistema)

    @override_settings(OPENAI_API_KEY='sk-test', EKI_ASESORIA_CONTEXTO=False)
    def test_sin_flag_el_prompt_de_los_agentes_no_cambia(self):
        self.assertNotIn('LO QUE SABEMOS DE LA PERSONA', self._sistema())

    @override_settings(EKI_ASESORIA_CONTEXTO=True)
    def test_nat_tambien_lo_recibe(self):
        from core.bot_comercial.webhook import _perfil_para_nat

        self.assertIn('- Se dedica a: cacao', _perfil_para_nat(self.tel))


@override_settings(OPENAI_API_KEY='sk-test', EKI_ASESORIA_MODELO='gpt-5-mini')
class DerivarDetalleTests(TestCase):
    TODOS = ['nat', 'coach', 'ia_campo', 'ventas', 'finanzas']

    def _derivar(self, respuesta, **kwargs):
        with patch('core.presupuesto_llm.debe_degradar', return_value=False), \
                patch('core.openai_compat.cliente_openai', return_value='cli'), \
                patch('core.openai_compat.completar_chat', return_value=respuesta) as llm:
            salida = derivar_detalle('debo plata y no vendo', telefono='5730', permitidos=self.TODOS, **kwargs)
        return salida, llm.call_args.args[2][0]['content']

    def test_con_segundo_pide_y_lee_la_segunda_palabra(self):
        salida, sistema = self._derivar('ventas finanzas', con_segundo=True)
        self.assertEqual(salida, ('ventas', 'llm', 'finanzas'))
        self.assertIn('segunda palabra', sistema)

    def test_sin_segundo_el_prompt_y_la_salida_son_los_de_siempre(self):
        salida, sistema = self._derivar('ventas finanzas')
        self.assertEqual(salida, ('ventas', 'llm', ''))
        self.assertNotIn('segunda palabra', sistema)
        self.assertNotIn('Lo que ya sabemos', sistema)

    def test_el_contexto_va_para_desempatar(self):
        _, sistema = self._derivar('finanzas', contexto='- Se dedica a: tienda')
        self.assertIn('desempatar', sistema)
        self.assertIn('- Se dedica a: tienda', sistema)


class SiguientePreguntaTests(TestCase):
    tel = '573005558101'

    def test_empieza_por_a_que_se_dedica(self):
        pregunta = siguiente_pregunta(self.tel)
        self.assertEqual(pregunta.campo, 'dedica')
        self.assertTrue(pregunta.mensaje.startswith('Para ayudarle mejor la próxima vez: ¿a qué se dedica?'))
        self.assertIn('audio', pregunta.mensaje)
        self.assertIn('*seguir*', pregunta.mensaje)

    def test_sin_botones_las_opciones_van_en_el_texto(self):
        FichaNegocio.objects.create(telefono=self.tel, preguntadas='dedica')
        pregunta = siguiente_pregunta(self.tel)
        self.assertEqual(pregunta.campo, 'etapa')
        self.assertIn('Responda: Apenas empezando, Ya vendo o Quiero crecer.', pregunta.mensaje_sin_botones)

    def test_lo_que_ya_se_sabe_no_se_pregunta(self):
        FichaNegocio.objects.create(telefono=self.tel, dedica='café', etapa='crecer')
        self.assertEqual(siguiente_pregunta(self.tel).campo, 'equipo')

    def test_con_las_tres_hechas_no_hay_mas(self):
        FichaNegocio.objects.create(telefono=self.tel, preguntadas='dedica,etapa,equipo')
        self.assertIsNone(siguiente_pregunta(self.tel))

    def test_no_mas_de_una_cada_20_horas(self):
        FichaNegocio.objects.create(
            telefono=self.tel, preguntadas='dedica', pendiente_desde=timezone.now() - timedelta(hours=19),
        )
        self.assertIsNone(siguiente_pregunta(self.tel))
        FichaNegocio.objects.filter(telefono=self.tel).update(pendiente_desde=timezone.now() - timedelta(hours=21))
        self.assertEqual(siguiente_pregunta(self.tel).campo, 'etapa')


@override_settings(**CONTEXTO)
class FlujoFichaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005558200'
        SandboxCanalSesion.objects.create(
            telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR, modo='ventas',
        )

    def _ficha(self):
        return FichaNegocio.objects.filter(telefono=self.tel).first()

    def _turno_agente(self, texto='cómo subo el precio'):
        return self._mandar(texto)

    def _mandar(self, texto):
        with patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta ventas') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            ruta = dispatch_sandbox_menu(_payload(self.tel, texto))
        return ruta, ag, send

    def _pasar_horas(self, horas=21):
        FichaNegocio.objects.filter(telefono=self.tel).update(
            pendiente_desde=timezone.now() - timedelta(hours=horas),
        )

    def test_despues_de_ayudar_pregunta_a_que_se_dedica(self):
        ruta, _, send = self._turno_agente()
        self.assertEqual(ruta, 'handled')
        textos = _textos(send)
        self.assertEqual(len(textos), 2)
        self.assertIn('Respuesta ventas', textos[0])
        self.assertIn('¿a qué se dedica?', textos[1])
        self.assertEqual(send.call_args.kwargs.get('agente'), AGENTE_FICHA)
        ficha = self._ficha()
        self.assertEqual((ficha.preguntadas, ficha.pendiente), ('dedica', 'dedica'))

    def test_solo_cuando_toca_la_ficha_se_pide_cerrar_sin_pregunta(self):
        _, ag, _ = self._turno_agente()
        self.assertTrue(ag.call_args.kwargs['sin_pregunta_final'])
        _, ag, _ = self._mandar('¿cómo consigo clientes?')
        self.assertFalse(ag.call_args.kwargs['sin_pregunta_final'])

    def test_en_el_turno_de_la_derivacion_no_se_pide(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('ventas', 'llm', '')), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, 'quiero vender mi café a mejor precio'))
        self.assertFalse(ag.call_args.kwargs['sin_pregunta_final'])

    def test_si_el_asesor_manda_a_otro_no_pregunta_la_ficha(self):
        from core.lineas.principal.ficha_negocio import remite_a_otro_asesor

        self.assertTrue(remite_a_otro_asesor('Escriba *menu* para elegir *Agrónomo* ahora.'))
        self.assertTrue(remite_a_otro_asesor('Eso lo ve mejor el *Agrónomo*: que escriba *agronomo*.'))
        self.assertFalse(remite_a_otro_asesor('Escriba en un papel *cuánto vende* cada día.'))
        with patch('core.sandbox_agentes.responder_agente_sandbox',
                   return_value='Para cultivos lo mejor es el *Agrónomo*: escriba *agronomo*.'), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'necesito saber de cultivos'))
        self.assertEqual(len(_textos(send)), 1)
        self.assertIsNone(self._ficha())

    def test_si_el_asesor_deja_una_pregunta_la_ficha_espera(self):
        with patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Suba poco a poco.\n\n¿A cuánto vende hoy?'), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'cómo subo el precio'))
        self.assertEqual(len(_textos(send)), 1)
        self.assertIsNone(self._ficha())
        _, ag, send = self._mandar('a 8000 la libra')
        ag.assert_called_once()
        self.assertIn('¿a qué se dedica?', ' '.join(_textos(send)))

    def test_la_respuesta_se_guarda_sin_datos_personales_y_no_va_al_agente(self):
        self._turno_agente()
        ruta, ag, send = self._mandar('cultivo café, escríbame a pepe@correo.co o al 3001234567')
        self.assertEqual(ruta, 'handled')
        ag.assert_not_called()
        self.assertEqual(_textos(send), [GRACIAS])
        ficha = self._ficha()
        self.assertTrue(ficha.dedica.startswith('cultivo café'))
        self.assertNotIn('pepe@correo.co', ficha.dedica)
        self.assertNotIn('3001234567', ficha.dedica)
        self.assertEqual(ficha.pendiente, '')

    def test_una_pregunta_nueva_va_al_agente_y_no_a_la_ficha(self):
        self._turno_agente()
        ruta, ag, _ = self._mandar('cómo controlo la broca')
        self.assertEqual(ruta, 'handled')
        ag.assert_called_once()
        ficha = self._ficha()
        self.assertEqual((ficha.dedica, ficha.pendiente, ficha.saltadas), ('', '', 1))

    def test_seguir_salta_y_no_se_vuelve_a_preguntar(self):
        self._turno_agente()
        ruta, ag, send = self._mandar('seguir')
        self.assertEqual(ruta, 'handled')
        ag.assert_not_called()
        self.assertEqual(_textos(send), [SALTADA])
        self._pasar_horas()
        _, _, send = self._turno_agente()
        self.assertNotIn('¿a qué se dedica?', ' '.join(_textos(send)))
        self.assertEqual(self._ficha().pendiente, 'etapa')

    def test_una_sola_por_conversacion(self):
        self._turno_agente()
        self._mandar('vendo arepas')
        _, _, send = self._turno_agente('y cómo consigo clientes')
        self.assertEqual(_textos(send), ['Respuesta ventas'])

    def test_etapa_con_botones_y_el_boton_guarda(self):
        FichaNegocio.objects.create(telefono=self.tel, dedica='arepas', preguntadas='dedica')
        _, _, send = self._turno_agente()
        cuerpo = send.call_args.args[0]
        self.assertEqual(cuerpo['interactive']['type'], 'button')
        self.assertIn('¿Cómo va su negocio hoy?', cuerpo['interactive']['body']['text'])
        botones = [b['reply'] for b in cuerpo['interactive']['action']['buttons']]
        self.assertEqual(
            [(b['id'], b['title']) for b in botones],
            [('ficha_etapa_empezando', 'Apenas empezando'), ('ficha_etapa_vende', 'Ya vendo'),
             ('ficha_etapa_crecer', 'Quiero crecer')],
        )
        ruta, ag, send = self._mandar('ficha_etapa_vende')
        self.assertEqual(ruta, 'handled')
        ag.assert_not_called()
        self.assertEqual(_textos(send), [GRACIAS])
        self.assertEqual(self._ficha().etapa, 'vende')

    def test_equipo_tambien_se_responde_escribiendo(self):
        FichaNegocio.objects.create(telefono=self.tel, dedica='arepas', etapa='vende', preguntadas='dedica,etapa')
        self._turno_agente()
        self._mandar('Con mi familia')
        self.assertEqual(self._ficha().equipo, 'familia')
        self._pasar_horas()
        _, _, send = self._turno_agente()
        self.assertEqual(_textos(send), ['Respuesta ventas'])

    def test_otra_cosa_con_botones_pendientes_sigue_su_camino(self):
        FichaNegocio.objects.create(telefono=self.tel, dedica='arepas', preguntadas='dedica')
        self._turno_agente()
        ruta, ag, _ = self._mandar('y el precio del maíz')
        self.assertEqual(ruta, 'handled')
        ag.assert_called_once()
        ficha = self._ficha()
        self.assertEqual((ficha.etapa, ficha.pendiente), ('', ''))

    def test_menu_sale_de_la_ficha_y_muestra_el_menu(self):
        self._turno_agente()
        self._mandar('menu')
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, 'menu')
        self.assertEqual(self._ficha().pendiente, '')

    def test_el_nombre_de_otro_asesor_cambia_de_asesor(self):
        self._turno_agente()
        self._mandar('finanzas')
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, 'finanzas')
        ficha = self._ficha()
        self.assertEqual((ficha.dedica, ficha.pendiente), ('', ''))

    def test_cafe_si_es_respuesta(self):
        self._turno_agente()
        ruta, ag, _ = self._mandar('Café')
        ag.assert_not_called()
        self.assertEqual(self._ficha().dedica, 'Café')

    def test_pasadas_24_horas_la_respuesta_ya_no_es_de_la_ficha(self):
        self._turno_agente()
        self._pasar_horas(25)
        ruta, ag, _ = self._mandar('vendo arepas')
        self.assertEqual(ruta, 'handled')
        ag.assert_called_once()
        self.assertEqual(self._ficha().dedica, '')

    def _derivar(self, salida, texto='quiero vender mi café a mejor precio'):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=salida) as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta ventas'), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, texto))
        return der, _textos(send)

    def test_no_pregunta_en_el_turno_de_la_derivacion(self):
        _, textos = self._derivar(('ventas', 'llm', ''))
        self.assertEqual(len(textos), 1)
        self.assertIsNone(self._ficha())

    def test_la_primera_respuesta_tras_derivar_cierra_con_la_salida(self):
        _, textos = self._derivar(('ventas', 'llm', ''))
        self.assertTrue(textos[0].startswith('Respuesta ventas'))
        self.assertIn(CIERRE, textos[0])
        self.assertNotIn('Esto también tiene que ver', textos[0])
        _, _, send = self._turno_agente('y a quién le vendo')
        self.assertNotIn(CIERRE, ' '.join(_textos(send)))

    def test_el_cierre_lleva_a_asesor_y_no_al_menu(self):
        _, textos = self._derivar(('ventas', 'llm', ''))
        self.assertTrue(textos[0].endswith('¿Era esto lo que necesitaba? Si no, escriba *asesor*.'))

    def test_si_el_asesor_ya_pregunto_el_cierre_no_pregunta_otra_vez(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('ventas', 'llm', '')), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Elija un cliente.\n\n¿Cuál elige?'), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'no entiendo lo de ventas'))
        texto = _textos(send)[0]
        self.assertTrue(texto.endswith('¿Cuál elige?\n\nSi no era esto, escriba *asesor*.'))
        self.assertNotIn(CIERRE, texto)

    def test_asesor_tras_la_pregunta_de_la_ficha_vuelve_a_la_asesoria(self):
        self._turno_agente()
        _, ag, send = self._mandar('asesor')
        ag.assert_not_called()
        self.assertIn('¿Qué quiere mejorar hoy', ' '.join(_textos(send)))
        self.assertEqual(SandboxCanalSesion.objects.get(telefono=self.tel).modo, 'asesoria')
        ficha = self._ficha()
        self.assertEqual((ficha.dedica, ficha.pendiente), ('', ''))

    def test_necesidad_mixta_menciona_al_otro_asesor(self):
        _, textos = self._derivar(('ventas', 'llm', 'finanzas'))
        self.assertIn(
            'Esto también tiene que ver con sus cuentas; si quiere, lo vemos con Finanzas: escriba *finanzas*.',
            textos[0],
        )
        self.assertIn(CIERRE, textos[0])

    def test_el_segundo_debe_ser_otro_y_de_la_linea(self):
        _, textos = self._derivar(('ventas', 'llm', 'ventas'))
        self.assertNotIn('Esto también tiene que ver', textos[0])

    def test_el_que_deriva_recibe_lo_que_se_sabe(self):
        FichaNegocio.objects.create(telefono=self.tel, dedica='tienda de abarrotes', preguntadas='dedica')
        der, _ = self._derivar(('finanzas', 'llm', ''), texto='no me alcanza la plata del negocio')
        kwargs = der.call_args.kwargs
        self.assertIn('Se dedica a: tienda de abarrotes', kwargs['contexto'])
        self.assertTrue(kwargs['con_segundo'])

    def test_elegido_por_nombre_no_lleva_cierre(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle') as der, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'ventas'))
        der.assert_not_called()
        self.assertNotIn(CIERRE, ' '.join(_textos(send)))

    def test_sin_cupo_no_pregunta(self):
        with patch('core.sandbox_agentes.excedio_cupo_ia_linea', return_value=True):
            _, ag, send = self._turno_agente()
        ag.assert_not_called()
        self.assertEqual(len(_textos(send)), 1)
        self.assertIsNone(self._ficha())


@override_settings(**CONTEXTO)
class NatFichaTests(TestCase):
    """Nat responde por el bot comercial; la pregunta de la ficha y el cierre salen después, aparte."""

    def setUp(self):
        cache.clear()
        self.tel = '573005558300'
        SandboxCanalSesion.objects.create(
            telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR, modo='nat',
        )

    def _ficha(self):
        return FichaNegocio.objects.filter(telefono=self.tel).first()

    def _turno(self, texto='tengo roya en el café'):
        payload = _payload(self.tel, texto)
        with patch('core.lineas.envio._post_graph', return_value=OK):
            self.assertEqual(dispatch_sandbox_menu(payload), 'nat')
        return payload

    def _nat(self, payload, respuesta='Para la roya, aplique cobre.', llama_modelo=True):
        from core.bot_comercial import webhook

        def cuerpo(post_data, forzar_canal=False):
            self.perfil = webhook._perfil_para_nat(self.tel)
            if llama_modelo:
                webhook._completar_nat(None, 'gpt-5-mini', [], 100, 0.2, None)

        with patch('core.bot_comercial.webhook._procesar_bot_comercial_twilio_webhook_cuerpo', side_effect=cuerpo), \
                patch('core.openai_compat.completar_chat', return_value=respuesta), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            webhook._procesar_bot_comercial_twilio_webhook(payload, forzar_canal=True)
        return _textos(send)

    def test_tras_responder_nat_pregunta_a_que_se_dedica(self):
        textos = self._nat(self._turno())
        self.assertEqual(len(textos), 1)
        self.assertIn('¿a qué se dedica?', textos[0])
        self.assertEqual(self._ficha().pendiente, 'dedica')

    def test_cuando_toca_la_ficha_nat_cierra_sin_pregunta(self):
        from core.bot_comercial.webhook import _perfil_para_nat

        self._nat(self._turno())
        self.assertTrue(self.perfil.endswith(SIN_PREGUNTA_FINAL))
        self.assertNotIn(SIN_PREGUNTA_FINAL, _perfil_para_nat(self.tel))
        self._nat(self._turno('¿y el cobre cada cuánto?'))
        self.assertNotIn(SIN_PREGUNTA_FINAL, self.perfil)

    def test_numero_comercial_y_derivacion_no_piden_cerrar_sin_pregunta(self):
        self._nat(_payload(self.tel, 'tengo roya en el café'))
        self.assertNotIn(SIN_PREGUNTA_FINAL, self.perfil)
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        payload = _payload(self.tel, 'las hojas del café tienen manchas amarillas')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('nat', 'llm', '')), \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(payload)
        self._nat(payload)
        self.assertNotIn(SIN_PREGUNTA_FINAL, self.perfil)

    def test_la_respuesta_a_la_ficha_no_va_a_nat(self):
        self._nat(self._turno())
        with patch('core.lineas.envio._post_graph', return_value=OK) as send:
            ruta = dispatch_sandbox_menu(_payload(self.tel, 'cultivo café'))
        self.assertEqual(ruta, 'handled')
        self.assertEqual(_textos(send), [GRACIAS])
        self.assertEqual(self._ficha().dedica, 'cultivo café')

    def test_si_nat_termina_preguntando_la_ficha_espera(self):
        textos = self._nat(self._turno(), respuesta='Puede ser roya.\n\n¿Qué variedad tiene sembrada?')
        self.assertEqual(textos, [])
        self.assertIsNone(self._ficha())

    def test_si_nat_manda_a_otro_asesor_no_pregunta(self):
        textos = self._nat(self._turno(), respuesta='Eso lo ve mejor *Ventas*: escriba *ventas*.')
        self.assertEqual(textos, [])
        self.assertIsNone(self._ficha())

    def test_derivado_a_nat_cierra_en_un_mensaje_aparte(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        payload = _payload(self.tel, 'las hojas del café tienen manchas amarillas')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('nat', 'llm', 'ventas')), \
                patch('core.lineas.envio._post_graph', return_value=OK):
            self.assertEqual(dispatch_sandbox_menu(payload), 'nat')
        textos = self._nat(payload)
        self.assertEqual(len(textos), 1)
        self.assertIn('Ventas', textos[0])
        self.assertTrue(textos[0].endswith(CIERRE))
        self.assertIsNone(self._ficha())

    def test_derivado_a_nat_que_ya_pregunto_cierra_sin_otra_pregunta(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        payload = _payload(self.tel, 'las hojas del café tienen manchas amarillas')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('nat', 'llm', '')), \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(payload)
        textos = self._nat(payload, respuesta='Puede ser roya.\n\n¿Qué variedad tiene?')
        self.assertEqual(textos, ['Si no era esto, escriba *asesor*.'])

    def test_el_numero_comercial_no_pregunta(self):
        self.assertEqual(self._nat(_payload(self.tel, 'tengo roya en el café')), [])
        self.assertIsNone(self._ficha())

    def test_sin_respuesta_del_modelo_no_pregunta(self):
        self.assertEqual(self._nat(self._turno(), llama_modelo=False), [])
        self.assertIsNone(self._ficha())

    def test_un_fallo_despues_de_nat_no_sube(self):
        with patch('core.lineas.principal.asesores.despues_de_nat', side_effect=OSError('graph')):
            self.assertEqual(self._nat(self._turno()), [])

    @override_settings(EKI_ASESORIA_CONTEXTO=False)
    def test_apagado_no_marca_ni_pregunta(self):
        payload = self._turno()
        self.assertNotIn('_eki_linea_principal', payload)
        payload['_eki_linea_principal'] = '1'
        self.assertEqual(self._nat(payload), [])
        self.assertIsNone(self._ficha())


@override_settings(**CONTEXTO)
class DerivacionesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005558500'
        SandboxCanalSesion.objects.create(
            telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR, modo='asesoria',
        )

    def _mandar(self, texto, derivacion=('ventas', 'llm', '')):
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=derivacion), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R'), \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, texto))

    def _derivar(self, derivacion=('ventas', 'llm', '')):
        self._mandar('quiero vender más, escríbame al 3001234567', derivacion)
        return DerivacionAsesoria.objects.get()

    def test_se_anota_sin_telefono_ni_numeros(self):
        d = self._derivar(('ventas', 'llm', 'finanzas'))
        self.assertEqual((d.agente, d.agente_secundario, d.fuente), ('ventas', 'finanzas', 'llm'))
        self.assertNotIn('3001234567', d.frase)
        self.assertNotEqual(d.telefono_hash, self.tel)
        self.assertEqual(len(d.telefono_hash), 16)
        self.assertFalse(d.con_contexto)
        self.assertFalse(d.corregida)

    def test_anota_si_uso_lo_que_se_sabia(self):
        FichaNegocio.objects.create(telefono=self.tel, dedica='arepas', preguntadas='dedica')
        self.assertTrue(self._derivar().con_contexto)

    def test_por_nombre_no_es_derivacion(self):
        self._mandar('ventas')
        self.assertFalse(DerivacionAsesoria.objects.exists())

    def test_volver_al_menu_justo_despues_la_corrige(self):
        self._derivar()
        self._mandar('menu')
        d = DerivacionAsesoria.objects.get()
        self.assertEqual((d.corregida, d.corregida_a), (True, 'menu'))

    def test_escribir_asesor_justo_despues_la_corrige(self):
        self._derivar()
        self._mandar('asesor')
        d = DerivacionAsesoria.objects.get()
        self.assertEqual((d.corregida, d.corregida_a), (True, 'asesoria'))

    def test_cambiar_de_asesor_justo_despues_la_corrige(self):
        self._derivar()
        self._mandar('coach')
        d = DerivacionAsesoria.objects.get()
        self.assertEqual((d.corregida, d.corregida_a), (True, 'coach'))

    def test_ir_al_segundo_asesor_ofrecido_no_es_error(self):
        self._derivar(('ventas', 'llm', 'finanzas'))
        self._mandar('finanzas')
        self.assertFalse(DerivacionAsesoria.objects.get().corregida)

    def test_si_siguio_preguntando_ya_no_es_correccion(self):
        self._derivar()
        self._mandar('y a quién le vendo')
        self._mandar('menu')
        self.assertFalse(DerivacionAsesoria.objects.get().corregida)

    def test_pasados_10_minutos_ya_no_es_correccion(self):
        d = self._derivar()
        DerivacionAsesoria.objects.filter(pk=d.pk).update(creada_en=timezone.now() - timedelta(minutes=11))
        self._mandar('menu')
        self.assertFalse(DerivacionAsesoria.objects.get().corregida)

    def test_resumen_de_la_semana(self):
        from core.lineas.principal.derivaciones import resumen_semana

        self._derivar()
        self._mandar('menu')
        self._mandar('asesoria')
        self._mandar('necesito ánimo', ('coach', 'llm', ''))
        vieja = DerivacionAsesoria.objects.create(telefono_hash='x', frase='f', agente='nat', fuente='llm')
        DerivacionAsesoria.objects.filter(pk=vieja.pk).update(creada_en=timezone.now() - timedelta(days=8))
        self.assertEqual(resumen_semana(), (2, 1))

    def test_admin_de_solo_lectura_con_la_tasa(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        self._derivar()
        self._mandar('menu')
        admin = get_user_model().objects.create_superuser('revisor', 'revisor@eki.co', 'x')
        self.client.force_login(admin)
        resp = self.client.get(reverse('admin:core_derivacionasesoria_changelist'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '7 días: 1, corregidas 1 (100 %)')
        resp = self.client.get(reverse('admin:core_derivacionasesoria_add'))
        self.assertEqual(resp.status_code, 403)


@override_settings(**PREGUNTA)
class FichaApagadaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005558300'
        SandboxCanalSesion.objects.create(
            telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR, modo='ventas',
        )

    def test_sin_flag_no_pregunta_ni_intercepta(self):
        with patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'cómo subo el precio'))
            dispatch_sandbox_menu(_payload(self.tel, 'seguir'))
        ag.assert_called_once()
        textos = _textos(send)
        self.assertNotIn(SALTADA, textos)
        self.assertFalse([t for t in textos if '¿a qué se dedica?' in t])
        self.assertFalse(FichaNegocio.objects.exists())

    def test_sin_flag_no_se_anotan_derivaciones_ni_hay_cierre(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=('ventas', 'llm')), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='R'), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'quiero vender más'))
            dispatch_sandbox_menu(_payload(self.tel, 'menu'))
        self.assertFalse(DerivacionAsesoria.objects.exists())
        self.assertNotIn(CIERRE, ' '.join(_textos(send)))
