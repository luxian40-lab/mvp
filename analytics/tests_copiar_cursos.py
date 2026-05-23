"""Tests comando copiar_cursos."""
from django.test import TestCase

from core.copiar_cursos import copiar_cursos_a_pruebas
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante


class CopiarCursosCommandTest(TestCase):
    def test_copiar_cursos_sin_estudiantes(self):
        alitic = Cliente.objects.create(nombre='Alitic', nit='800100200-3', activo=True)
        Curso.objects.create(
            nombre='Crea y Vende',
            cliente=alitic,
            descripcion='Desc',
            activo=True,
        )
        est = Estudiante.objects.create(
            nombre='Alumno', cedula='1', telefono='573001', cliente=alitic, activo=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=est, curso=Curso.objects.get(nombre='Crea y Vende'),
        )

        copiar_cursos_a_pruebas(reset=True)

        prueba = Cliente.objects.get(nit='900000002-0')
        self.assertEqual(prueba.nombre, 'Analytics (Pruebas)')
        self.assertTrue(Curso.objects.filter(cliente=prueba).exists())
        self.assertFalse(Estudiante.objects.filter(cliente=prueba).exists())
