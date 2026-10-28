"""Ficha del negocio: contexto para derivar y las tres preguntas de a una."""
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from core.lineas.principal.contexto_asesoria import contexto_persona, ultimo_agente
from core.lineas.principal.ficha_negocio import (
    AGENTE_FICHA,
    GRACIAS,
    SALTADA,
    siguiente_pregunta,
)
from core.models import FichaNegocio, SandboxCanalSesion, WhatsappLog
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

    def test_no_pregunta_en_el_turno_de_la_derivacion(self):
        SandboxCanalSesion.objects.filter(telefono=self.tel).update(modo='asesoria')
        with patch('core.lineas.principal.derivar_asesoria.derivar', return_value=('ventas', 'llm')), \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta ventas'), \
                patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'quiero vender mi café a mejor precio'))
        self.assertEqual(len(_textos(send)), 1)
        self.assertIsNone(self._ficha())

    def test_sin_cupo_no_pregunta(self):
        with patch('core.sandbox_agentes.excedio_cupo_ia_linea', return_value=True):
            _, ag, send = self._turno_agente()
        ag.assert_not_called()
        self.assertEqual(len(_textos(send)), 1)
        self.assertIsNone(self._ficha())


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
