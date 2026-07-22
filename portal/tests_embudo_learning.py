"""Tests embudo Learning Analytics (avance por módulo)."""

from django.test import TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante
from portal.curso_flujo_service import embudo_avance_por_curso


class EmbudoLearningTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org Embudo',
            contacto_principal='A',
            email='e@t.com',
            telefono='573001111111',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso Embudo', cliente=self.org, activo=True)
        self.m1 = Modulo.objects.create(curso=self.curso, numero=1, titulo='Uno', descripcion='d', contenido='c')
        self.m2 = Modulo.objects.create(curso=self.curso, numero=2, titulo='Dos', descripcion='d', contenido='c')
        self.m3 = Modulo.objects.create(curso=self.curso, numero=3, titulo='Tres', descripcion='d', contenido='c')

        def est(ced, tel, nombre):
            return Estudiante.objects.create(
                cedula=ced, telefono=tel, nombre=nombre, cliente=self.org, activo=True,
            )

        e1 = est('e1', '573001000001', 'A')
        e2 = est('e2', '573001000002', 'B')
        e3 = est('e3', '573001000003', 'C')
        ProgresoEstudiante.objects.create(estudiante=e1, curso=self.curso, modulo_actual=self.m1)
        p2 = ProgresoEstudiante.objects.create(estudiante=e2, curso=self.curso, modulo_actual=self.m2)
        ModuloCompletado.objects.create(progreso=p2, modulo=self.m1)
        p3 = ProgresoEstudiante.objects.create(
            estudiante=e3, curso=self.curso, modulo_actual=self.m3, completado=True,
        )
        ModuloCompletado.objects.create(progreso=p3, modulo=self.m1)
        ModuloCompletado.objects.create(progreso=p3, modulo=self.m2)
        ModuloCompletado.objects.create(progreso=p3, modulo=self.m3)

    def test_embudo_cuentas_por_modulo(self):
        data = embudo_avance_por_curso(curso_id=self.curso.id, cliente_id=self.org.id)
        self.assertIsNotNone(data)
        self.assertEqual(data['total_inscritos'], 3)
        by_n = {float(p['numero']): p['estudiantes'] for p in data['pasos']}
        self.assertEqual(by_n[1.0], 3)
        self.assertEqual(by_n[2.0], 2)
        self.assertEqual(by_n[3.0], 1)
        self.assertEqual(data['completados'], 1)
