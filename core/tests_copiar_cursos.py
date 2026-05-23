"""Tests core.copiar_cursos — Alitic → Analytics (Pruebas)."""
from django.test import TestCase

from core.copiar_cursos import (
    ClienteOrigenNoEncontrado,
    copiar_cursos_a_pruebas,
    obtener_cliente_analytics_origen,
)
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante


class CopiarCursosCoreTest(TestCase):
    def test_copiar_cursos_desde_alitic(self):
        alitic = Cliente.objects.create(nombre='Alitic', nit='800100100-1', activo=True)
        Curso.objects.create(nombre='Crea y Vende', cliente=alitic, descripcion='D', activo=True)
        otro = Cliente.objects.create(nombre='Otro SA', nit='800100200-3', activo=True)
        c2 = Curso.objects.create(nombre='No copiar', cliente=otro, descripcion='X', activo=True)
        est = Estudiante.objects.create(
            nombre='Alumno', cedula='1', telefono='573001', cliente=alitic, activo=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=est, curso=Curso.objects.get(nombre='Crea y Vende'),
        )

        result = copiar_cursos_a_pruebas(reset=True)

        self.assertEqual(result.origen.pk, alitic.pk)
        self.assertEqual(result.destino.nombre, 'Analytics (Pruebas)')
        self.assertEqual(result.total_copiados, 1)
        self.assertTrue(
            Curso.objects.filter(cliente=result.destino, nombre__icontains='Crea y Vende').exists()
        )
        self.assertFalse(Estudiante.objects.filter(cliente=result.destino).exists())
        self.assertTrue(c2.pk)

    def test_origen_default_es_alitic_no_fallback(self):
        Cliente.objects.create(nombre='AGRONEXO', nit='900001-1', activo=True)
        with self.assertRaises(ClienteOrigenNoEncontrado):
            obtener_cliente_analytics_origen()
