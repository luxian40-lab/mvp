"""Charla de entrada: cómo está, ficha con lo que ella dice, y recién ahí la duda.

El contexto no suma las 60 preguntas. El lugar del registro no se usa.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.lineas.principal.contexto_asesoria import contexto_persona
from core.models import Estudiante, FichaNegocio, SandboxCanalSesion
from core.planes_linea import PLAN_CURSO_ASESOR
from core.sandbox_menu import dispatch_sandbox_menu
from core.tests_asesoria_pregunta import PREGUNTA
from core.tests_planes_linea import OK, _payload, _textos

ENTRADA = dict(PREGUNTA, EKI_ASESORIA_ENTRADA=True, EKI_ASESORIA_CONTEXTO=True)


@override_settings(**ENTRADA)
class EntradaAsesoriaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005559180'
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)
        Estudiante.objects.create(
            nombre='María López',
            cedula='ENT180',
            telefono=self.tel,
            municipio='Líbano',
            region='Zona Cafetera',
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )

    def _usadas(self):
        return SandboxCanalSesion.objects.get(telefono=self.tel).preguntas_mes

    def _ficha(self):
        return FichaNegocio.objects.get(telefono=self.tel)

    def _enviar(self, body):
        with patch('core.lineas.envio._post_graph', return_value=OK) as send:
            ruta = dispatch_sandbox_menu(_payload(self.tel, body))
        return ruta, _textos(send)

    def test_el_saludo_pregunta_como_esta_y_no_usa_el_lugar_del_registro(self):
        _, textos = self._enviar('asesoria')
        self.assertEqual(textos, [
            'Hola, María. ¿Cómo está?\n\n_*agentes* = ver la lista · *menu* = menú principal._',
        ])
        self.assertNotIn('no la conozco', textos[0].lower())
        self.assertNotIn('Líbano', textos[0])
        self.assertNotIn('tú', textos[0].lower())
        self.assertEqual(self._usadas(), 0)
        self.assertEqual(self._ficha().entrada, 'como_esta')

    def test_el_contexto_no_gasta_cupo_y_una_respuesta_llena_lugar_y_dedica(self):
        self._enviar('asesoria')
        _, textos = self._enviar('Bien')
        self.assertEqual(textos, ['Bien. ¿De dónde es?'])
        self.assertEqual(self._usadas(), 0)
        _, textos = self._enviar('De Armero, cultivo café')
        self.assertEqual(
            textos,
            ['Cultivo café, en Armero. ¿Qué duda tiene, o qué le gustaría hacer?\n\n'
             '_*agentes* = ver la lista · *menu* = menú principal._'],
        )
        ficha = self._ficha()
        self.assertEqual((ficha.lugar, ficha.dedica, ficha.entrada), ('Armero', 'cultivo café', 'duda'))
        self.assertEqual(self._usadas(), 0)
        self.assertNotIn('Líbano', contexto_persona(self.tel))
        self.assertNotIn('Zona Cafetera', contexto_persona(self.tel))
        self.assertIn('Es de: Armero', contexto_persona(self.tel))
        self.assertIn('Nombre: María', contexto_persona(self.tel))

    def test_la_duda_se_deriva_y_ahi_cuenta_una_pregunta(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        self._enviar('De Armero, cultivo café')
        duda = 'las hojas se están poniendo amarillas'
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('ventas', 'llm', '')) as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            ruta = dispatch_sandbox_menu(_payload(self.tel, duda))
        self.assertEqual(ruta, 'handled')
        self.assertEqual(der.call_args.args[0], duda)
        self.assertIn('Es de: Armero', der.call_args.kwargs['contexto'])
        self.assertNotIn('Líbano', der.call_args.kwargs['contexto'])
        self.assertEqual(ag.call_args.args[:2], ('ventas', duda))
        self.assertEqual(self._usadas(), 1)
        self.assertEqual(self._ficha().entrada, '')

    def test_seguir_salta_a_la_duda_sin_gastar_cupo(self):
        self._enviar('asesoria')
        _, textos = self._enviar('seguir')
        self.assertIn('¿Qué duda tiene, o qué le gustaría hacer?', textos[0])
        self.assertEqual(self._usadas(), 0)
        self.assertEqual(self._ficha().entrada, 'duda')

    def test_con_la_ficha_llena_no_repite_el_lugar_ni_la_dedica(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        self._enviar('De Armero, cultivo café')
        self._enviar('asesoria')
        _, textos = self._enviar('Ahí vamos')
        self.assertEqual(
            textos[0],
            'Cultivo café, en Armero. ¿Qué duda tiene, o qué le gustaría hacer?\n\n'
            '_*agentes* = ver la lista · *menu* = menú principal._',
        )
        self.assertEqual(self._usadas(), 0)


@override_settings(**PREGUNTA)
class EntradaApagadaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tel = '573005559181'
        SandboxCanalSesion.objects.create(telefono=self.tel, habeas_aceptado=True, plan=PLAN_CURSO_ASESOR)
        Estudiante.objects.create(
            nombre='Ana',
            cedula='ENT181',
            telefono=self.tel,
            region='Zona Cafetera',
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )

    def test_sin_el_flag_sigue_la_pregunta_de_siempre(self):
        with patch('core.lineas.envio._post_graph', return_value=OK) as send:
            dispatch_sandbox_menu(_payload(self.tel, 'asesoria'))
        self.assertTrue(_textos(send)[0].startswith('¿Qué quiere mejorar hoy'))
        self.assertFalse(FichaNegocio.objects.filter(telefono=self.tel).exists())

    def test_sin_el_flag_el_contexto_sigue_trayendo_la_region(self):
        self.assertIn('Región: Zona Cafetera', contexto_persona(self.tel))
