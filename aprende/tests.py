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

    def test_subdominio_aprende_redirige_raiz(self):
        r = self.http.get('/', HTTP_HOST='aprende.eki.technology')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/aprende/')

    def test_subdominio_aula_redirige_raiz(self):
        r = self.http.get('/', HTTP_HOST='aula.eki.technology')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/aprende/')

    def test_catalogo_e_inscripcion(self):
        curso2 = Curso.objects.create(
            nombre='Curso Catálogo',
            descripcion='Para elegir',
            cliente=self.cliente,
            activo=True,
            visible_en_aula=True,
        )
        Modulo.objects.create(
            curso=curso2, numero=1, titulo='L1', descripcion='', contenido='x',
        )
        est2 = Estudiante.objects.create(
            cedula='web2',
            nombre='Est Cat',
            telefono='573009999003',
            cliente=self.cliente,
            activo=True,
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web2',
            'telefono': '3009999003',
        })
        r = self.http.get('/aprende/estudiante/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Catálogo')
        self.assertContains(r, 'Curso Catálogo')
        r2 = self.http.post(f'/aprende/estudiante/inscribir/{curso2.id}/')
        self.assertEqual(r2.status_code, 302)
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est2, curso=curso2).exists()
        )

    def test_no_inscribir_curso_de_otra_org(self):
        otra = Cliente.objects.create(
            nombre='Otra Org',
            contacto_principal='B',
            email='b@t.com',
            telefono='573009999004',
            activo=True,
        )
        ajeno = Curso.objects.create(
            nombre='Curso Ajeno',
            descripcion='x',
            cliente=otra,
            activo=True,
            visible_en_aula=True,
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.post(f'/aprende/estudiante/inscribir/{ajeno.id}/')
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            ProgresoEstudiante.objects.filter(estudiante=self.est, curso=ajeno).exists()
        )

    def test_curso_general_en_catalogo(self):
        general = Curso.objects.create(
            nombre='Curso General',
            descripcion='Para todos',
            cliente=None,
            activo=True,
            visible_en_aula=True,
        )
        est2 = Estudiante.objects.create(
            cedula='web3',
            nombre='Est Gen',
            telefono='573009999005',
            cliente=self.cliente,
            activo=True,
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web3',
            'telefono': '3009999005',
        })
        r = self.http.get('/aprende/estudiante/')
        self.assertContains(r, 'Curso General')
