"""Tests: pasos internos por módulo (entrega progresiva)."""
from django.test import TestCase

from core.models import Curso, Estudiante, Modulo, PasoModulo, ProgresoEstudiante
from core.module_steps import (
    modulo_tiene_pasos_activos,
    reset_progreso_pasos_modulo,
    entregar_paso_indice,
    procesar_respuesta_evaluacion_paso,
)
from core.response_templates import get_response_for_intent


class ModuleStepsModelTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso pasos',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='Contenido legacy del módulo entero',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='10998877',
            nombre='Ana Pasos',
            telefono='573009990011',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
        )

    def test_sin_pasos_modulo_legacy(self):
        self.assertFalse(modulo_tiene_pasos_activos(self.mod))

    def test_entregar_paso_contenido_avanza_indice(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            orden=1,
            titulo='Paso uno',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Solo este bloque',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        self.assertEqual(self.prog.paso_actual_modulo, 1)
        msg = entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.paso_actual_modulo, 2)
        self.assertIn('Paso uno', msg)
        self.assertIn('[MULTI_MSG]', msg)

    def test_evaluacion_opciones_espera_respuesta(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            orden=1,
            titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Elige bien',
            opciones_json={'A': 'Uno', 'B': 'Dos', 'correcta': 'B'},
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertTrue(self.prog.esperando_respuesta_evaluacion_paso)
        self.assertEqual(self.prog.paso_actual_modulo, 1)

        out = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'a')
        self.assertIsNotNone(out)
        self.assertIn('No es correcto', out)

        out2 = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'b')
        self.assertIsNotNone(out2)
        self.prog.refresh_from_db()
        self.assertFalse(self.prog.esperando_respuesta_evaluacion_paso)


class ModuleStepsLegacyRegressionTests(TestCase):
    """Sin pasos activos: continuar_leccion con listo sigue cerrando módulo (curso 2 mod, sin IA)."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso legacy drip0',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='A',
            descripcion='d',
            contenido='c1',
            duracion_dias=7,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='B',
            descripcion='d',
            contenido='c2',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='20887766',
            nombre='Bob Legacy',
            telefono='573001112233',
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_listo_sin_pasos_avanza_a_modulo_2(self):
        r = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('Módulo 2', r)
        self.assertIn('B', r)


class SelectorCursoPasosTests(TestCase):
    """selector_curso alineado a pasos (sin volcar contenido legacy)."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso selector pasos',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Mod uno',
            descripcion='d',
            contenido='TEXTO_LEGACY_NO_DEBE_APARECER_EN_SELECTOR_CON_PASOS',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='33445566',
            nombre='Chooser',
            telefono='5730011998877',
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_selector_solo_numero_con_pasos_entrega_paso_no_legacy(self):
        from core.models import PasoModulo
        from core.selector_curso import continuar_curso_seleccionado

        PasoModulo.objects.create(
            modulo=self.m1,
            orden=1,
            titulo='Micro paso',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Contenido solo paso 1',
        )
        r = continuar_curso_seleccionado(self.est.id, 1, '1')
        self.assertNotIn('TEXTO_LEGACY_NO_DEBE_APARECER', r)
        self.assertIn('Micro paso', r)
        self.assertIn('[MULTI_MSG]', r)
