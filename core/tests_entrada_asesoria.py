"""Charla de entrada: cómo está, de dónde es y a qué se dedica, y qué quiere entender.

El contexto no suma las 60 preguntas. El lugar del registro no se usa.
No se repite lo que la persona acaba de escribir.
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
_RETO = '¿Cuál es el principal reto que tiene el día de hoy?'
_PLATA = '¿La plata no entra porque no se vende, o entra y no le cubre lo que gasta?'


def _luna(_client, modelo, messages, _max_out, temperature=None):
    user = messages[-1]['content']
    if 'Última frase:' not in user:
        return '¿Qué se le está complicando?'
    frase = user.split('Última frase:', 1)[1].lower()
    if 'plata' in frase:
        return _PLATA
    return 'DERIVAR'


@override_settings(**ENTRADA)
class EntradaAsesoriaTests(TestCase):
    def setUp(self):
        cache.clear()
        parche = patch('core.openai_compat.completar_chat', side_effect=_luna)
        self.luna = parche.start()
        self.addCleanup(parche.stop)
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
        self.assertEqual(textos, ['Cuénteme de usted: de dónde es y a qué se dedica.'])
        self.assertNotIn('Bien', textos[0])
        self.assertEqual(self._usadas(), 0)
        _, textos = self._enviar('Soy de Bogotá y vendo aguacate')
        self.assertEqual(textos, [f'{_RETO}\n\n_*agentes* = ver la lista · *menu* = menú principal._'])
        self.assertNotIn('¿De dónde es?', textos[0])
        self.assertNotIn('¿Qué duda tiene', textos[0])
        self.assertNotIn('Soy de Bogotá', textos[0])
        self.luna.assert_not_called()
        ficha = self._ficha()
        self.assertEqual((ficha.lugar, ficha.dedica, ficha.entrada), ('Bogotá', 'vendo aguacate', 'indaga1'))
        self.assertEqual(self._usadas(), 0)
        self.assertNotIn('Líbano', contexto_persona(self.tel))
        self.assertNotIn('Zona Cafetera', contexto_persona(self.tel))
        self.assertIn('Es de: Bogotá', contexto_persona(self.tel))
        self.assertIn('Nombre: María', contexto_persona(self.tel))

    def test_si_falta_un_dato_pregunta_solo_ese(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        _, textos = self._enviar('Bogotá')
        self.assertEqual(textos, ['¿A qué se dedica?'])
        _, textos = self._enviar('vendo aguacate')
        self.assertEqual(textos[0], f'{_RETO}\n\n_*agentes* = ver la lista · *menu* = menú principal._')
        self.assertEqual((self._ficha().lugar, self._ficha().dedica), ('Bogotá', 'vendo aguacate'))

    def test_la_duda_se_deriva_y_ahi_cuenta_una_pregunta(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        self._enviar('Soy de Bogotá y vendo aguacate')
        duda = 'las hojas se están poniendo amarillas'
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('ventas', 'llm', '')) as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta') as ag, \
                patch('core.lineas.envio._post_graph', return_value=OK):
            ruta = dispatch_sandbox_menu(_payload(self.tel, duda))
        self.assertEqual(ruta, 'handled')
        self.assertEqual(der.call_args.args[0], duda)
        self.assertIn('Es de: Bogotá', der.call_args.kwargs['contexto'])
        self.assertNotIn('Líbano', der.call_args.kwargs['contexto'])
        self.assertEqual(ag.call_args.args[:2], ('ventas', duda))
        self.assertEqual(self._usadas(), 1)
        self.assertEqual(self._ficha().entrada, '')

    def test_seguir_salta_a_la_duda_sin_gastar_cupo(self):
        self._enviar('asesoria')
        _, textos = self._enviar('seguir')
        self.assertEqual(
            textos[0],
            'De lo que me contó, ¿qué quiere entender mejor?\n\n'
            '_*agentes* = ver la lista · *menu* = menú principal._',
        )
        self.assertEqual(self._usadas(), 0)
        self.assertEqual(self._ficha().entrada, 'duda')

    def test_con_la_ficha_llena_no_repite_el_lugar_ni_la_dedica(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        self._enviar('Soy de Bogotá y vendo aguacate')
        self._enviar('asesoria')
        _, textos = self._enviar('Ahí vamos')
        self.assertEqual(textos[0], f'{_RETO}\n\n_*agentes* = ver la lista · *menu* = menú principal._')
        self.assertEqual(self._usadas(), 0)

    def test_sin_plata_pregunta_el_detalle_y_no_deriva_todavia(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        self._enviar('Soy de Bogotá y vendo aguacate')
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle') as der:
            _, textos = self._enviar('me quedo sin plata')
        self.assertEqual(textos, [f'{_PLATA}\n\n_*agentes* = ver la lista · *menu* = menú principal._'])
        der.assert_not_called()
        self.assertEqual(self._usadas(), 0)
        self.assertEqual(self._ficha().entrada, 'indaga2')
        frase = 'entra y no me cubre lo que gasto'
        with patch('core.lineas.principal.derivar_asesoria.derivar_detalle', return_value=('finanzas', 'llm', '')) as der, \
                patch('core.sandbox_agentes.responder_agente_sandbox', return_value='Respuesta'), \
                patch('core.lineas.envio._post_graph', return_value=OK):
            dispatch_sandbox_menu(_payload(self.tel, frase))
        self.assertEqual(der.call_args.args[0], frase)
        self.assertEqual(self.luna.call_args.args[1], 'gpt-6-luna')
        self.assertEqual(self._usadas(), 1)
        self.assertEqual(self._ficha().entrada, '')

    def test_el_lugar_dicho_en_la_misma_frase_no_se_vuelve_a_pedir(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        _, textos = self._enviar('Profesor y dicto clase en Subachoque')
        self.assertEqual(textos, [f'{_RETO}\n\n_*agentes* = ver la lista · *menu* = menú principal._'])
        self.assertNotIn('¿De dónde es?', textos[0])
        self.assertEqual(self._ficha().lugar, 'Subachoque')
        self.assertIn('Profesor', self._ficha().dedica)
        self.assertEqual(self._usadas(), 0)

    def test_si_luna_no_contesta_el_reto_sigue_y_luego_deriva(self):
        self._enviar('asesoria')
        self._enviar('Bien')
        self._enviar('Soy de Bogotá y vendo aguacate')
        with patch('core.openai_compat.completar_chat', return_value=''):
            _, textos = self._enviar('no sé')
        self.assertFalse(any('¿De dónde es?' in t for t in textos))
        self.assertEqual(self._usadas(), 0)
        self.assertEqual(self._ficha().entrada, '')


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
