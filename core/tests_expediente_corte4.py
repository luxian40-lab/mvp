"""
Corte 4 — origen del cierre (expand: chat / operacion / presencial).

docs/PLAN_EXPEDIENTE_APRENDIZAJE_EKI.md. No toca listados calientes.
"""
from __future__ import annotations

from django.test import TestCase

from core.certificados.certificado_presencial_service import cerrar_curso_si_tramo_final
from core.conversacion.progreso_completado import (
    ORIGEN_CHAT,
    ORIGEN_PRESENCIAL,
    marcar_progreso_curso_completado,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


class ExpedienteOrigenCierreChatTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre='C4 chat', activo=True)
        self.curso = Curso.objects.create(nombre='Chat', cliente=self.cli, activo=True)
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c', publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='EXP-C4-001', nombre='Ana', telefono='573009991501', cliente=self.cli, activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.mod, completado=False,
        )

    def test_cierre_chat_escribe_origen_chat(self):
        marcar_progreso_curso_completado(self.progreso)
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertEqual(self.progreso.origen_cierre, ORIGEN_CHAT)

    def test_fila_previa_sin_origen_sigue_null_y_completado(self):
        self.progreso.completado = True
        self.progreso.origen_cierre = None
        self.progreso.save(update_fields=['completado', 'origen_cierre'])
        marcar_progreso_curso_completado(self.progreso)  # idempotente
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertIsNone(self.progreso.origen_cierre)


class ExpedienteOrigenCierrePresencialTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre='C4 pres', activo=True)
        self.curso = Curso.objects.create(nombre='WA', cliente=self.cli, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c', publicado_wa=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='M2', descripcion='d', contenido='c', publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='EXP-C4-002', nombre='Pepe', telefono='573009991502', cliente=self.cli, activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.m1, completado=False,
        )

    def test_cierre_presencial_escribe_origen_presencial(self):
        self.assertEqual(cerrar_curso_si_tramo_final(self.est, self.curso), 'cerrado')
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertEqual(self.progreso.origen_cierre, ORIGEN_PRESENCIAL)
