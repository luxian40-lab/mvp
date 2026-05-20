"""Tests filtro por grupo en métricas Empresas."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.metricas_empresa import calcular_metricas_empresa
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.models_extras import GrupoEstudiantes
from formulario.factories import ClienteFactory


class TestAnalyticsEmpresasGrupo(TestCase):
    def setUp(self):
        self.cliente = ClienteFactory()
        self.curso = Curso.objects.create(nombre='Curso G', cliente=self.cliente, activo=True)
        self.g1 = GrupoEstudiantes.objects.create(nombre='Grupo A', cliente=self.cliente, activo=True)
        self.g2 = GrupoEstudiantes.objects.create(nombre='Grupo B', cliente=self.cliente, activo=True)
        self.e1 = Estudiante.objects.create(
            nombre='Uno', cedula='9101', telefono='573001000101', cliente=self.cliente, activo=True
        )
        self.e2 = Estudiante.objects.create(
            nombre='Dos', cedula='9102', telefono='573001000102', cliente=self.cliente, activo=True
        )
        self.g1.estudiantes.add(self.e1)
        self.g2.estudiantes.add(self.e2)
        ProgresoEstudiante.objects.create(estudiante=self.e1, curso=self.curso, completado=True)
        ProgresoEstudiante.objects.create(estudiante=self.e2, curso=self.curso, completado=False)

    def test_filtro_grupo_devuelve_solo_grupo(self):
        data = calcular_metricas_empresa(cliente_id=self.cliente.id, grupo_id=self.g1.id)
        self.assertEqual(data['resumen']['total_inscritos'], 1)
        self.assertEqual(data['resumen']['finalizados'], 1)
        nombres = {r['nombre'] for r in data['progreso_estudiantes']}
        self.assertEqual(nombres, {'Uno'})

    def test_sin_grupo_comportamiento_igual(self):
        sin = calcular_metricas_empresa(cliente_id=self.cliente.id)
        con_todos = calcular_metricas_empresa(cliente_id=self.cliente.id, grupo_id=None)
        self.assertEqual(sin['resumen']['total_inscritos'], con_todos['resumen']['total_inscritos'])
        self.assertEqual(sin['resumen']['total_inscritos'], 2)

    def test_endpoint_grupos_por_empresa(self):
        User = get_user_model()
        user = User.objects.create_superuser('staff_g', 's@e.com', 'x')
        c = Client()
        c.force_login(user)
        resp = c.get(f'/admin/analytics/api/grupos/?cliente_id={self.cliente.id}')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        ids = {g['id'] for g in body['grupos']}
        self.assertIn(self.g1.id, ids)
        self.assertIn(self.g2.id, ids)
