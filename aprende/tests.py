"""Tests básicos del aula web /aprende/."""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from portal.models import PortalUsuario


class AprendeWebTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.cliente = Cliente.objects.create(
            nombre='Org Aprende',
            contacto_principal='A',
            email='ap@test.com',
            telefono='573009999001',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso Web', cliente=self.cliente, activo=True)
        self.modulo = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Intro',
            descripcion='d',
            contenido='Hola desde la web',
        )
        self.est = Estudiante.objects.create(
            cedula='web1',
            nombre='Est Web',
            telefono='573009999002',
            cliente=self.cliente,
            activo=True,
        )
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso, modulo_actual=self.modulo)
        self.user = User.objects.create_user('prof_ap', 'p@t.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.cliente, rol='profesor')

    def test_inicio_carga(self):
        r = self.http.get('/aprende/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Estudiante')
        self.assertContains(r, 'Aula web')

    def test_estudiante_login_y_ve_modulo(self):
        r = self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '573009999002',
        })
        self.assertEqual(r.status_code, 302)
        r2 = self.http.get(f'/aprende/estudiante/modulo/{self.modulo.id}/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Hola desde la web')

    def test_estudiante_login_telefono_sin_57(self):
        r = self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        self.assertEqual(r.status_code, 302)

    def test_profesor_ve_cursos(self):
        self.http.post('/aprende/profesor/login/', {'username': 'prof_ap', 'password': 'pass'})
        r = self.http.get('/aprende/profesor/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curso Web')
