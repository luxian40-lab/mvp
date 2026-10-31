"""Lista de aceptantes por curso: aislamiento, página y consultas acotadas."""
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante
from portal.inscritos_curso import POR_PAGINA, inscritos_curso
from portal.models import PortalUsuario


def _org(nombre, telefono):
    return Cliente.objects.create(
        nombre=nombre,
        contacto_principal='A',
        email=f'{nombre.lower()}@test.com',
        telefono=telefono,
        activo=True,
        portal_productos='cursos',
    )


@override_settings(SECURE_SSL_REDIRECT=False)
class InscritosCursoTests(TestCase):
    def setUp(self):
        self.org = _org('ListaOrg', '573009990410')
        self.otra = _org('ListaOtra', '573009990411')
        self.curso = Curso.objects.create(nombre='Curso finca', cliente=self.org, activo=True)
        self.modulo = Modulo.objects.create(curso=self.curso, numero=2, titulo='Riego', descripcion='d')
        self.user = User.objects.create_user('lista_admin', 'l@t.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.org, rol='admin')
        self.http = Client()
        self.http.post('/portal/login/', {'username': 'lista_admin', 'password': 'pass'})

    def _persona(self, org, curso, nombre, telefono, *, paso=1, modulo=None, completado=False):
        est = Estudiante.objects.create(
            nombre=nombre, cedula=telefono[-6:], telefono=telefono, cliente=org, activo=True,
        )
        progreso = ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, paso_actual_modulo=paso, modulo_actual=modulo,
        )
        if completado:
            ProgresoEstudiante.objects.filter(pk=progreso.pk).update(completado=True)
            progreso.completado = True
        return est, progreso

    def _consultas(self, org, curso):
        with CaptureQueriesContext(connection) as ctx:
            inscritos_curso(org, curso)
        return len(ctx.captured_queries)

    def test_aislamiento_pagina_y_ficha(self):
        ana, progreso = self._persona(
            self.org, self.curso, 'Ana Riego', '573001510001', paso=3, modulo=self.modulo,
        )
        ModuloCompletado.objects.create(progreso=progreso, modulo=self.modulo)
        self._persona(self.org, self.curso, 'Beto', '573001510002')
        ajeno_curso = Curso.objects.create(nombre='Ajeno', cliente=self.otra, activo=True)
        self._persona(self.otra, self.curso, 'Clara', '573001510099')
        self._persona(self.otra, ajeno_curso, 'Dario', '573001510098')

        r = self.http.get(f'/portal/analitica/cursos/{self.curso.id}/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Ana Riego', html)
        self.assertIn('Beto', html)
        self.assertIn('Empezó', html)
        self.assertIn('M2 — Riego', html)
        self.assertIn('>3<', html)
        self.assertNotIn('Clara', html)
        self.assertNotIn('573001510001', html)
        self.assertIn(f'/portal/estudiantes/{ana.id}/?curso={self.curso.id}', html)
        self.assertEqual(self.http.get(f'/portal/analitica/cursos/{ajeno_curso.id}/').status_code, 404)

        general = Curso.objects.create(nombre='General vacio', cliente=None, activo=True)
        self.assertEqual(self.http.get(f'/portal/analitica/cursos/{general.id}/').status_code, 404)
        self._persona(self.org, general, 'Eva General', '573001510003', paso=2)
        self._persona(self.otra, general, 'Fran Ajeno', '573001510097', paso=2)
        g = self.http.get(f'/portal/analitica/cursos/{general.id}/')
        self.assertEqual(g.status_code, 200)
        cuerpo = g.content.decode()
        self.assertIn('Eva General', cuerpo)
        self.assertNotIn('Fran Ajeno', cuerpo)

        otro = Curso.objects.create(nombre='Aaa primero', cliente=self.org, activo=True)
        ProgresoEstudiante.objects.create(estudiante=ana, curso=otro, paso_actual_modulo=1)
        ficha = self.http.get(f'/portal/estudiantes/{ana.id}/?curso={self.curso.id}')
        self.assertEqual(ficha.status_code, 200)
        self.assertEqual(ficha.context['progreso_filas'][0]['progreso'].curso_id, self.curso.id)
        self.assertContains(ficha, 'Inscritos del curso')
        self.assertContains(ficha, '>3<')

    def test_pagina_de_cincuenta_no_trae_el_resto(self):
        for i in range(POR_PAGINA + 10):
            self._persona(self.org, self.curso, f'P{i:03d}', f'57300152{i:04d}')
        uno = self.http.get(f'/portal/analitica/cursos/{self.curso.id}/')
        self.assertContains(uno, 'P000')
        self.assertNotContains(uno, 'P050')
        dos = self.http.get(f'/portal/analitica/cursos/{self.curso.id}/?page=2')
        self.assertContains(dos, 'P050')
        self.assertNotContains(dos, 'P000')
        busca = self.http.get(f'/portal/analitica/cursos/{self.curso.id}/?q=P059')
        self.assertContains(busca, 'P059')
        self.assertNotContains(busca, 'P000')

    def test_las_consultas_no_crecen_con_la_pagina(self):
        def armar(nombre, telefono, n):
            org = _org(nombre, telefono)
            curso = Curso.objects.create(nombre=nombre, cliente=org, activo=True)
            modulo = Modulo.objects.create(curso=curso, numero=1, titulo='M', descripcion='d')
            for i in range(n):
                _, progreso = self._persona(
                    org, curso, f'{nombre}{i}', f'{telefono[:-2]}{i:02d}', paso=2, modulo=modulo,
                )
                ModuloCompletado.objects.create(progreso=progreso, modulo=modulo)
            return org, curso

        poca = armar('Poca', '573009910000', 3)
        mucha = armar('Mucha', '573009920000', 10)
        self.assertEqual(self._consultas(*poca), self._consultas(*mucha))
        self.assertEqual(self._consultas(*poca), 3)
