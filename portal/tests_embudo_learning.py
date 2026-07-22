"""Tests embudo Learning Analytics (posición hoy + histórico portal)."""

from django.test import TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante
from portal.curso_flujo_service import (
    _pct_label,
    embudo_avance_por_curso,
    embudo_posicion_hoy_por_curso,
)


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
        e4 = est('e4', '573001000004', 'D')
        ProgresoEstudiante.objects.create(estudiante=e1, curso=self.curso, modulo_actual=self.m1)
        p2 = ProgresoEstudiante.objects.create(estudiante=e2, curso=self.curso, modulo_actual=self.m2)
        ModuloCompletado.objects.create(progreso=p2, modulo=self.m1)
        ProgresoEstudiante.objects.create(
            estudiante=e3, curso=self.curso, modulo_actual=self.m3, completado=True,
        )
        ProgresoEstudiante.objects.create(estudiante=e4, curso=self.curso)  # sin iniciar

    def test_embudo_historico_acumulado(self):
        data = embudo_avance_por_curso(curso_id=self.curso.id, cliente_id=self.org.id)
        self.assertIsNotNone(data)
        self.assertEqual(data['total_inscritos'], 4)
        by_n = {float(p['numero']): p['estudiantes'] for p in data['pasos']}
        # e1 en M1, e2 alcanzó M2, e3 completó (cuenta en todos), e4 sin iniciar
        self.assertEqual(by_n[1.0], 3)
        self.assertEqual(by_n[2.0], 2)
        self.assertEqual(by_n[3.0], 1)
        self.assertEqual(data['completados'], 1)

    def test_embudo_posicion_hoy(self):
        data = embudo_posicion_hoy_por_curso(curso_id=self.curso.id, cliente_id=self.org.id)
        self.assertIsNotNone(data)
        self.assertEqual(data['modo'], 'hoy')
        self.assertEqual(data['total_inscritos'], 4)
        self.assertEqual(data['sin_iniciar'], 1)
        self.assertEqual(data['completados'], 1)
        by_n = {float(p['numero']): p['estudiantes'] for p in data['pasos']}
        self.assertEqual(by_n[1.0], 1)
        self.assertEqual(by_n[2.0], 1)
        self.assertEqual(by_n[3.0], 0)  # el de M3 ya está en completados
        # 1+1+0 + sin_iniciar 1 + completados 1 = 4
        self.assertEqual(
            sum(by_n.values()) + data['sin_iniciar'] + data['completados'],
            data['total_inscritos'],
        )
        # % tipo 1,0 … 1,888; barras = % del total de inscritos
        self.assertEqual(data['sin_iniciar_pct'], 25.0)
        self.assertEqual(data['sin_iniciar_pct_label'], '25,0')
        self.assertEqual(data['sin_iniciar_bar_pct'], 25.0)
        self.assertEqual(data['max_bucket'], 1)
        m3 = next(p for p in data['pasos'] if float(p['numero']) == 3.0)
        self.assertEqual(m3['pct_label'], '0,0')
        self.assertEqual(m3['bar_pct'], 0.0)
        self.assertIn('chart', data)
        self.assertEqual(data['chart']['values'], [1.0, 1.0, 1.0, 0.0, 1.0])
        self.assertEqual(len(data['chart']['pct_labels']), 5)
        self.assertGreater(data['chart']['axis_max'], data['chart']['axis_min'])
        self.assertEqual(_pct_label(1.888), '1,888')
        self.assertEqual(_pct_label(1.0), '1,0')
