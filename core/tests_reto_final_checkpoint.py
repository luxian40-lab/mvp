"""Regresión anclada a fallos AgriCapital prod (2026-11-13/14), sin PII de campo.

Teléfono de fixture: solo el QA interno 573026480629 (3026480629).
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.intent_detector import (
    mensaje_indica_listo,
    mensaje_indica_listo_o_confirma_handoff,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent

# Regla eki: tests / smoke usan solo este número (ver .cursor/hooks/telefono_qa_tests.py).
TEL_QA = '573026480629'


def _cliente_curso_mods(*, cedula, nombre, gamificacion=True, numeros=(4, 5)):
    cli = Cliente.objects.create(nombre='AgriCapital QA', usar_gamificacion=gamificacion)
    curso = Curso.objects.create(
        nombre='Curso QA reto final',
        usar_gamificacion=gamificacion,
        usar_agentes_ia=True,
        cliente=cli,
    )
    mods = [
        Modulo.objects.create(
            curso=curso, numero=n, titulo=f'M{n}', descripcion='d', contenido=f'c{n}',
        )
        for n in numeros
    ]
    est = Estudiante.objects.create(
        cedula=cedula,
        nombre=nombre,
        telefono=TEL_QA,
        cliente=cli,
        activo=True,
        acepto_terminos=True,
        estado_chat='ACTIVO',
        estado_onboarding='esperando_respuesta_asistente',
    )
    return cli, curso, mods, est


class CierreSinCompletadoPrematuroTests(TestCase):
    """Caso prod: cierre con es_reto_final; continuemos/Ok deben lanzar Formador."""

    def setUp(self):
        _cli, self.curso, self.mods, self.est = _cliente_curso_mods(
            cedula='QA-CIERRE-001',
            nombre='QA Cierre Final',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mods[-1],
            completado=False,
        )
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'curso_activo_id': self.curso.id,
            'modulo_id': self.mods[-1].id,
            'progreso_id': self.prog.id,
            'modulos_reto_ids': [m.id for m in self.mods],
            'preguntas_hechas': 0,
            'es_reto_final': True,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def _continuar(self, trigger):
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador',
            return_value='RETO_FINAL_QA',
        ):
            return get_response_for_intent(
                'continuar_leccion',
                self.est.nombre,
                estudiante_id=self.est.id,
                mensaje_original=trigger,
            )

    def test_continuemos_lanza_formador_y_progreso_sigue_activo(self):
        out = self._continuar('continuemos')
        self.assertIn('RETO_FINAL_QA', out)
        self.assertNotIn('Ya completaste', out)
        self.est.refresh_from_db()
        self.prog.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        self.assertTrue((self.est.contexto_temporal or {}).get('es_final'))
        self.assertFalse(self.prog.completado)

    def test_ok_tambien_lanza_formador(self):
        out = self._continuar('Ok')
        self.assertIn('RETO_FINAL_QA', out)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')


class LegadoCompletadoPrematuroTests(TestCase):
    """Alumnos ya marcados completado=True en prod antes del refactor."""

    def setUp(self):
        _cli, self.curso, self.mods, self.est = _cliente_curso_mods(
            cedula='QA-CIERRE-LEG',
            nombre='QA Cierre Legado',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mods[-1],
            completado=True,
            fecha_completado=timezone.now(),
        )
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'curso_activo_id': self.curso.id,
            'modulo_id': self.mods[-1].id,
            'progreso_id': self.prog.id,
            'modulos_reto_ids': [m.id for m in self.mods],
            'preguntas_hechas': 1,
            'es_reto_final': True,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def test_bypass_no_responde_ya_completaste(self):
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador',
            return_value='RETO_LEGADO_QA',
        ):
            out = get_response_for_intent(
                'continuar_leccion',
                self.est.nombre,
                estudiante_id=self.est.id,
                mensaje_original='continuemos',
            )
        self.assertIn('RETO_LEGADO_QA', out)
        self.assertNotIn('Ya completaste', out)


class CheckpointMidCursoTests(TestCase):
    """Caso prod: checkpoint mid-curso; Ok debe lanzar Formador."""

    def setUp(self):
        _cli, self.curso, mods, self.est = _cliente_curso_mods(
            cedula='QA-MID-001',
            nombre='QA Checkpoint Mid',
            numeros=(1, 2, 3),
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=mods[-1],
            completado=False,
        )
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'curso_activo_id': self.curso.id,
            'modulo_id': mods[-1].id,
            'progreso_id': self.prog.id,
            'modulos_reto_ids': [m.id for m in mods],
            'preguntas_hechas': 0,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def test_ok_lanza_formador_mid_curso(self):
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador',
            return_value='RETO_MID_QA',
        ):
            out = get_response_for_intent(
                'continuar_leccion',
                self.est.nombre,
                estudiante_id=self.est.id,
                mensaje_original='Ok',
            )
        self.assertIn('RETO_MID_QA', out)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        self.assertFalse((self.est.contexto_temporal or {}).get('es_final', False))


class ConfirmaCortaSoloHandoffTests(TestCase):
    def test_ok_no_ensancha_listo_global(self):
        for msg in ('Ok', 'dale', 'si', 'sí'):
            with self.subTest(msg=msg):
                self.assertFalse(mensaje_indica_listo(msg))
                self.assertTrue(mensaje_indica_listo_o_confirma_handoff(msg))

    def test_listo_sigue_en_ambos(self):
        self.assertTrue(mensaje_indica_listo('listo'))
        self.assertTrue(mensaje_indica_listo_o_confirma_handoff('listo'))
