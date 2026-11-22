"""
Corte 1 — expediente de aprendizaje: caracterización (comportamiento actual).

docs/PLAN_EXPEDIENTE_APRENDIZAJE_EKI.md. Sin cambios de producto.
"""
from django.test import TestCase
from django.utils import timezone

from core.certificados.certificado_presencial_service import cerrar_curso_si_tramo_final
from core.certificados.certificado_service import calcular_calificacion_curso, evaluar_elegibilidad_certificado
from core.conversacion.claves_contexto import contexto_limpio
from core.conversacion.progreso_completado import marcar_progreso_curso_completado
from core.gamificacion_modo import MODO_CALIFICACION
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PreguntaAbiertaFinalCurso,
    ProgresoEstudiante,
)
from core.certificados.models_certificados import Certificado
from core.selector_curso import continuar_curso_seleccionado
from core.views.ventana_drip import _pregunta_abierta_final_pendiente


class ExpedienteCompletadoAntesPreguntaAbiertaTests(TestCase):
    """Al abrir la pregunta abierta final, completado ya es verdadero (con fecha)."""

    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Exp C1', activo=True, usar_gamificacion=False)
        self.curso = Curso.objects.create(
            nombre='Caracterización',
            cliente=self.cli,
            activo=True,
            usar_gamificacion=False,
            usar_agentes_ia=False,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='c',
            publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='EXP-C1-001',
            nombre='Ana',
            telefono='573009991401',
            cliente=self.cli,
            activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
            completado=False,
        )
        PreguntaAbiertaFinalCurso.objects.create(
            curso=self.curso,
            pregunta='¿Qué haría en campo?',
            activa=True,
        )

    def test_reto_final_marca_completado_antes_de_responder_pregunta(self):
        import logging

        from core.conversacion.estados.reto import _cerrar_reto_final

        _cerrar_reto_final(
            '',
            {'es_final': True},
            self.progreso,
            self.est,
            _pregunta_abierta_final_pendiente,
            logging.getLogger(__name__),
            contexto_limpio,
            'evaluación del reto',
            lambda *a, **k: '',
        )
        self.progreso.refresh_from_db()
        self.est.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertIsNotNone(self.progreso.fecha_completado)
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_pregunta_abierta_final')


class ExpedienteSelectorSinFechaTests(TestCase):
    """selector_curso marca completado sin fecha_completado.

    El 2º arg de ``continuar_curso_seleccionado`` es índice 1-based de la lista
    visible, no el pk del curso.
    """

    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Sel', activo=True)
        self.curso = Curso.objects.create(
            nombre='Fin selector', cliente=self.cli, activo=True, dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Único', descripcion='d', contenido='texto',
            publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='EXP-C1-002', nombre='Luis', telefono='573009991402',
            cliente=self.cli, activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.mod, completado=False,
            paso_actual_modulo=2,
        )

    def test_listo_en_ultimo_modulo_sin_fecha_completado(self):
        n_cert = Certificado.objects.count()
        continuar_curso_seleccionado(self.est.id, 1, 'listo')
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertIsNone(self.progreso.fecha_completado)
        self.assertEqual(Certificado.objects.count(), n_cert)


class ExpedienteCerrarTramoPresencialTests(TestCase):
    """cerrar_curso_si_tramo_final completa módulos y la bandera."""

    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Pres', activo=True)
        self.curso = Curso.objects.create(nombre='WA', cliente=self.cli, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c', publicado_wa=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='M2', descripcion='d', contenido='c', publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='EXP-C1-003', nombre='Pepe', telefono='573009991403', cliente=self.cli, activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.m1, completado=False,
        )

    def test_penultimo_modulo_cierra_curso(self):
        self.assertEqual(cerrar_curso_si_tramo_final(self.est, self.curso), 'cerrado')
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertIsNotNone(self.progreso.fecha_completado)
        self.assertEqual(ModuloCompletado.objects.filter(progreso=self.progreso).count(), 2)


class ExpedienteCalificacionCienSinPreguntasTests(TestCase):
    """calcular_calificacion_curso y elegibilidad tal como hoy."""

    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Nota',
            contacto_principal='X',
            email='n@test.com',
            telefono='573009991404',
            activo=True,
            exigir_nota_minima_certificado=False,
            modo_gamificacion=MODO_CALIFICACION,
        )
        self.curso = Curso.objects.create(nombre='Sin QA', cliente=self.cli, activo=True)
        self.est = Estudiante.objects.create(
            cedula='EXP-C1-004', nombre='Nota', telefono='573009991405', cliente=self.cli, activo=True,
        )

    def test_sin_preguntas_respondidas_devuelve_100(self):
        self.assertEqual(calcular_calificacion_curso(self.est, self.curso), 100.0)

    def test_exigir_nota_apagada_deja_emitir(self):
        ok, motivo = evaluar_elegibilidad_certificado(self.est, self.curso)
        self.assertTrue(ok)
        self.assertIsNone(motivo)


class ExpedienteMarcarProgresoIdempotenteTests(TestCase):
    def setUp(self):
        curso = Curso.objects.create(nombre='Idem', activo=True)
        est = Estudiante.objects.create(cedula='EXP-C1-005', nombre='I', telefono='573009991406')
        self.progreso = ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)

    def test_marcar_helper_setea_fecha_completado(self):
        marcar_progreso_curso_completado(self.progreso)
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertIsNotNone(self.progreso.fecha_completado)