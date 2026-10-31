"""Métricas por curso: inicio, culminación y avance, agrupadas por línea."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.lineas.modelo import LineaWhatsapp
from core.models import (
    Cliente, Curso, Estudiante, Modulo, ModuloCompletado, NotaCierreCurso, ProgresoEstudiante,
)
from portal.metricas_curso import metricas_cursos
from portal.models import PortalUsuario


def _org(nombre):
    return Cliente.objects.create(
        nombre=nombre,
        contacto_principal='A',
        email=f'{nombre.lower()}@test.com',
        telefono='573009990200',
        activo=True,
        portal_productos='cursos',
    )


@override_settings(SECURE_SSL_REDIRECT=False)
class MetricasCursoTests(TestCase):
    def setUp(self):
        self.org = _org('MetCurso')
        self.otra = _org('MetOtra')
        self.finca = Curso.objects.create(nombre='Curso finca', cliente=self.org, activo=True)
        self.general = Curso.objects.create(nombre='Riendas', cliente=None, activo=True)
        self.vacio = Curso.objects.create(nombre='Sin gente', cliente=self.org, activo=True)
        self.m1 = Modulo.objects.create(curso=self.finca, numero=1, titulo='M1', descripcion='d')
        self.m2 = Modulo.objects.create(curso=self.finca, numero=2, titulo='M2', descripcion='d')
        Modulo.objects.create(curso=self.general, numero=1, titulo='G1', descripcion='d')

        # Finca: 4 inscritos. Uno sin empezar, uno en el primer paso, uno con un módulo, uno terminó.
        self._prog('573001300001', self.finca)
        self._prog('573001300002', self.finca, paso_actual_modulo=3)
        con_modulo = self._prog('573001300003', self.finca)
        ModuloCompletado.objects.create(progreso=con_modulo, modulo=self.m1)
        self._prog('573001300004', self.finca, completado=True)
        # General: 1 inscrito sin empezar.
        self._prog('573001300005', self.general)
        # Otra organización no cuenta.
        ajeno = Estudiante.objects.create(
            nombre='Ajeno', cedula='300099', telefono='573001300099', cliente=self.otra, activo=True,
        )
        self._completar(ProgresoEstudiante.objects.create(estudiante=ajeno, curso=self.finca))

    def _completar(self, progreso):
        # update() no dispara la señal que genera el diploma.
        ProgresoEstudiante.objects.filter(pk=progreso.pk).update(completado=True)
        return progreso

    def _prog(self, telefono, curso, completado=False, **extra):
        est = Estudiante.objects.create(
            nombre=f'E{telefono[-2:]}', cedula=telefono[-6:], telefono=telefono,
            cliente=self.org, activo=True,
        )
        progreso = ProgresoEstudiante.objects.create(estudiante=est, curso=curso, **extra)
        return self._completar(progreso) if completado else progreso

    def test_por_curso_con_definiciones(self):
        filas = {f['nombre']: f for f in metricas_cursos(self.org)['por_curso']}
        finca = filas['Curso finca']
        self.assertEqual(finca['inscritos'], 4)
        self.assertEqual(finca['iniciaron'], 3)
        self.assertEqual(finca['terminaron'], 1)
        self.assertEqual(finca['inicio_pct'], 75.0)
        self.assertEqual(finca['culminacion_iniciados_pct'], round(100 / 3, 1))
        self.assertEqual(finca['culminacion_inscritos_pct'], 25.0)
        # Avance: 0, 0, 50 y 100 → 37.5
        self.assertEqual(finca['avance_pct'], 37.5)
        self.assertTrue(filas['Riendas']['general'])
        self.assertEqual(filas['Riendas']['inicio_pct'], 0.0)
        self.assertIsNone(filas['Riendas']['culminacion_iniciados_pct'])
        self.assertEqual(filas['Sin gente']['inscritos'], 0)
        self.assertIsNone(filas['Sin gente']['inicio_pct'])
        self.assertIsNone(filas['Sin gente']['avance_pct'])

    def test_total_suma_inscripciones(self):
        total = metricas_cursos(self.org)['total']
        self.assertEqual(total['inscritos'], 5)
        self.assertEqual(total['iniciaron'], 3)
        self.assertEqual(total['terminaron'], 1)
        self.assertEqual(total['inicio_pct'], 60.0)
        self.assertEqual(total['culminacion_inscritos_pct'], 20.0)
        self.assertEqual(total['avance_pct'], 30.0)

    def test_segundo_curso_y_cursos_destacados(self):
        quien = Estudiante.objects.get(telefono='573001300002', cliente=self.org)
        ProgresoEstudiante.objects.create(estudiante=quien, curso=self.general, paso_actual_modulo=2)

        amplio = Curso.objects.create(nombre='Amplio', cliente=self.org, activo=True)
        for i in range(5):
            est = Estudiante.objects.create(
                nombre=f'Am{i}', cedula=f'81{i:04d}', telefono=f'5730081000{i}',
                cliente=self.org, activo=True,
            )
            progreso = ProgresoEstudiante.objects.create(estudiante=est, curso=amplio, paso_actual_modulo=2)
            if i < 2:
                self._completar(progreso)
        largo = Curso.objects.create(nombre='Largo', cliente=self.org, activo=True)
        for i in range(6):
            est = Estudiante.objects.create(
                nombre=f'La{i}', cedula=f'82{i:04d}', telefono=f'5730082000{i}',
                cliente=self.org, activo=True,
            )
            ProgresoEstudiante.objects.create(estudiante=est, curso=largo, paso_actual_modulo=2)
        chico = Curso.objects.create(nombre='Chico', cliente=self.org, activo=True)
        uno = Estudiante.objects.create(
            nombre='Uno', cedula='830001', telefono='573008300001', cliente=self.org, activo=True,
        )
        self._completar(ProgresoEstudiante.objects.create(estudiante=uno, curso=chico))

        data = metricas_cursos(self.org)
        self.assertEqual(data['segundo_curso']['n'], 1)
        self.assertEqual(data['segundo_curso']['base'], 3 + 5 + 6 + 1)
        self.assertEqual(data['destacados']['mas_inicios']['nombre'], 'Largo')
        self.assertEqual(data['destacados']['mas_inicios']['iniciaron'], 6)
        self.assertEqual(data['destacados']['mayor_culminacion']['nombre'], 'Amplio')
        self.assertEqual(data['destacados']['mayor_culminacion']['culminacion_iniciados_pct'], 40.0)
        self.assertEqual(data['destacados']['min_iniciadores'], 5)

    def test_recomendacion_es_nps_no_promedio(self):
        vacio = metricas_cursos(self.org)['nota_cierre']
        self.assertEqual(vacio['n'], 0)
        self.assertIsNone(vacio['nps'])
        # 10, 9, 8 y 6: promotores 2, detractores 1, base 4 → NPS 25. El promedio sería 8.3.
        for telefono, nota in (
            ('573001300001', 10),
            ('573001300002', 9),
            ('573001300003', 8),
            ('573001300004', 6),
        ):
            NotaCierreCurso.objects.create(
                estudiante=Estudiante.objects.get(telefono=telefono, cliente=self.org),
                curso=self.finca,
                nota=nota,
            )
        ajeno = Estudiante.objects.get(telefono='573001300099')
        NotaCierreCurso.objects.create(estudiante=ajeno, curso=self.finca, nota=1)

        nota = metricas_cursos(self.org)['nota_cierre']
        self.assertEqual(nota['n'], 4)
        self.assertEqual(nota['nps'], 25)

    def test_agrupa_por_linea_sin_mostrar_lineas_de_otra_org(self):
        propia = LineaWhatsapp.objects.create(phone_id='pid-met-1', nombre='Línea finca', cliente=self.org)
        propia.cursos.add(self.finca, self.general)
        ajena = LineaWhatsapp.objects.create(phone_id='pid-met-2', nombre='Línea ajena', cliente=self.otra)
        ajena.cursos.add(self.finca)
        lineas = metricas_cursos(self.org)['lineas']
        nombres = [linea['nombre'] for linea in lineas]
        self.assertEqual(nombres, ['Línea finca', 'Sin línea asignada'])
        self.assertEqual([c['nombre'] for c in lineas[0]['cursos']], ['Curso finca', 'Riendas'])
        self.assertEqual([c['nombre'] for c in lineas[1]['cursos']], ['Sin gente'])

    def test_paginas_boton_y_tabla(self):
        user = User.objects.create_user('met_admin', 'm@t.com', 'pass')
        PortalUsuario.objects.create(user=user, organizacion=self.org, rol='admin')
        http = Client()
        http.post('/portal/login/', {'username': 'met_admin', 'password': 'pass'})
        uso = http.get('/portal/analitica/').content.decode()
        self.assertIn('Ver métricas por curso', uso)
        self.assertIn('href="/portal/analitica/cursos/"', uso)
        for etiqueta in (
            'Tasa de inicio', 'Culminación sobre iniciadores', 'Culminación sobre aceptantes',
            'Avance promedio', 'Inicio de segundo curso', 'Curso con más inicios',
            'Curso con mayor culminación', 'Recomendación del curso',
        ):
            self.assertIn(etiqueta, uso)
        self.assertIn('Curso finca', uso)
        self.assertIn('0 de 3', uso)
        self.assertIn('Ningún curso llega a 5 iniciadores.', uso)
        self.assertIn('Promotores 9–10, detractores 1–6.', uso)
        self.assertNotIn('Culminación de quienes iniciaron', uso)
        self.assertNotIn('Culminación de inscritos', uso)
        self.assertIn('3 de 5', uso)
        self.assertNotIn('Ver métricas por curso', http.get('/portal/analitica/?s=impacto').content.decode())
        r = http.get('/portal/analitica/cursos/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Curso finca', html)
        self.assertIn(f'href="/portal/analitica/cursos/{self.finca.id}/"', html)
        self.assertNotIn('>E01<', html)
        self.assertIn('75.0%', html)
        self.assertIn('Culminación sobre iniciadores', html)
        self.assertIn('Culminación sobre aceptantes', html)
        self.assertIn('Sin línea asignada', html)
