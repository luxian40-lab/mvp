"""
Corte 3 — el diploma lee reglas (flag EKI_DIPLOMA_LEE_REGLAS).

docs/PLAN_EXPEDIENTE_APRENDIZAJE_EKI.md.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.conversacion.claves_contexto import contexto_limpio
from core.conversacion.progreso_completado import marcar_progreso_curso_completado
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PreguntaAbiertaFinalCurso,
    ProgresoEstudiante,
    RespuestaAbiertaFinal,
)
from core.models_certificados import Certificado
from core.views.ventana_drip import _pregunta_abierta_final_pendiente


def _fixtures(nombre_curso='C3', con_pregunta=True):
    cli = Cliente.objects.create(nombre=f'Exp {nombre_curso}', activo=True, usar_gamificacion=False)
    curso = Curso.objects.create(
        nombre=nombre_curso,
        cliente=cli,
        activo=True,
        usar_gamificacion=False,
        usar_agentes_ia=False,
        habilitar_pregunta_abierta_final=True,
    )
    mod = Modulo.objects.create(
        curso=curso,
        numero=1,
        titulo='M1',
        descripcion='d',
        contenido='c',
        publicado_wa=True,
    )
    est = Estudiante.objects.create(
        cedula=f'EXP-C3-{nombre_curso}',
        nombre='Ana',
        telefono=f'57300999{abs(hash(nombre_curso)) % 10000:04d}',
        cliente=cli,
        activo=True,
    )
    progreso = ProgresoEstudiante.objects.create(
        estudiante=est,
        curso=curso,
        modulo_actual=mod,
        completado=False,
    )
    ModuloCompletado.objects.create(progreso=progreso, modulo=mod)
    pregunta = None
    if con_pregunta:
        pregunta = PreguntaAbiertaFinalCurso.objects.create(
            curso=curso,
            pregunta='¿Qué haría en campo?',
            activa=True,
        )
    return cli, curso, mod, est, progreso, pregunta


@override_settings(EKI_CERTIFICADO_ASYNC=False)
class ExpedienteDiplomaFlagOffTests(TestCase):
    """Flag apagado: cierre de hoy sigue generando diploma."""

    @patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
    def test_cierre_con_fecha_crea_certificado(self, _gen):
        _cli, _curso, _mod, _est, progreso, _pregunta = _fixtures('Off')
        n = Certificado.objects.count()
        marcar_progreso_curso_completado(progreso)
        self.assertEqual(Certificado.objects.count(), n + 1)


@override_settings(EKI_DIPLOMA_LEE_REGLAS=True, EKI_CERTIFICADO_ASYNC=False)
class ExpedienteDiplomaFlagOnTests(TestCase):
    """Flag prendido: llegar a la pregunta abierta final no crea Certificado."""

    @patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
    def test_abrir_pregunta_abierta_no_crea_certificado(self, _gen):
        import logging

        from core.conversacion.estados.reto import _cerrar_reto_final

        _cli, _curso, _mod, est, progreso, _pregunta = _fixtures('OnPend')
        n = Certificado.objects.count()
        _cerrar_reto_final(
            '',
            {'es_final': True},
            progreso,
            est,
            _pregunta_abierta_final_pendiente,
            logging.getLogger(__name__),
            contexto_limpio,
            'evaluación del reto',
            lambda *a, **k: '',
        )
        progreso.refresh_from_db()
        est.refresh_from_db()
        self.assertTrue(progreso.completado)
        self.assertIsNotNone(progreso.fecha_completado)
        self.assertEqual(est.estado_onboarding, 'esperando_respuesta_pregunta_abierta_final')
        self.assertEqual(Certificado.objects.count(), n)

    @patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
    def test_sin_pregunta_y_modulos_hechos_si_emite(self, _gen):
        _cli, _curso, _mod, _est, progreso, _pregunta = _fixtures('OnOk', con_pregunta=False)
        n = Certificado.objects.count()
        marcar_progreso_curso_completado(progreso)
        self.assertEqual(Certificado.objects.count(), n + 1)

    @patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
    def test_tras_responder_pregunta_cumple_reglas(self, _gen):
        from core.certificados.diploma_reglas import cumple_reglas_diploma, emitir_diploma_si_cumple

        _cli, curso, _mod, est, progreso, pregunta = _fixtures('OnAns')
        marcar_progreso_curso_completado(progreso)
        est.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
        est.save(update_fields=['estado_onboarding'])
        progreso.refresh_from_db()
        ok, motivo = cumple_reglas_diploma(progreso)
        self.assertFalse(ok)
        self.assertIn(motivo, ('pregunta_abierta_pendiente', 'evaluacion_abierta_sin_responder'))

        RespuestaAbiertaFinal.objects.create(
            pregunta=pregunta,
            estudiante=est,
            curso=curso,
            progreso=progreso,
            respuesta_texto='haría X',
            fecha_respuesta=timezone.now(),
            estado='pendiente',
        )
        est.estado_onboarding = 'curso_finalizado'
        est.save(update_fields=['estado_onboarding'])
        progreso.refresh_from_db()
        ok, motivo = cumple_reglas_diploma(progreso)
        self.assertTrue(ok, motivo)
        n = Certificado.objects.count()
        self.assertIsNotNone(emitir_diploma_si_cumple(progreso))
        self.assertEqual(Certificado.objects.count(), n + 1)
