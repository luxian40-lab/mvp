"""Inscripción segura + defaults modulo_actual para Aprende."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from core.inscripcion_curso import (
    defaults_progreso_nuevo,
    inscribir_estudiante_en_curso,
    primer_modulo_curso,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


class InscripcionCursoTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Org Insc',
            contacto_principal='C',
            email='i@t.com',
            telefono='573001110001',
        )
        self.curso = Curso.objects.create(nombre='Curso C Info', cliente=self.cli, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Clase 1', descripcion='', contenido='hola',
        )
        Modulo.objects.create(
            curso=self.curso, numero=2, titulo='Clase 2', descripcion='', contenido='hola2',
        )
        self.est = Estudiante.objects.create(
            cedula='INSC1',
            nombre='Est Insc',
            telefono='573001110002',
            cliente=self.cli,
            activo=True,
        )

    def test_defaults_incluye_primer_modulo(self):
        d = defaults_progreso_nuevo(self.curso)
        self.assertFalse(d['completado'])
        self.assertEqual(d['modulo_actual'].pk, self.m1.pk)

    def test_inscribir_crea_con_modulo_actual(self):
        prog, creado = inscribir_estudiante_en_curso(self.est, self.curso)
        self.assertTrue(creado)
        self.assertEqual(prog.modulo_actual_id, self.m1.id)

    def test_inscribir_segunda_vez_idempotente(self):
        inscribir_estudiante_en_curso(self.est, self.curso)
        prog, creado = inscribir_estudiante_en_curso(self.est, self.curso)
        self.assertFalse(creado)
        self.assertEqual(prog.modulo_actual_id, self.m1.id)

    def test_repara_progreso_sin_modulo_actual(self):
        prog = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, completado=False, modulo_actual=None,
        )
        self.assertIsNone(prog.modulo_actual_id)
        prog2, creado = inscribir_estudiante_en_curso(self.est, self.curso)
        self.assertFalse(creado)
        prog2.refresh_from_db()
        self.assertEqual(prog2.modulo_actual_id, self.m1.id)


class PrimerModuloTests(SimpleTestCase):
    def test_nombre_helper(self):
        self.assertTrue(callable(primer_modulo_curso))
