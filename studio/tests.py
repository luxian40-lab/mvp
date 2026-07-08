"""Tests eki Studio (/studio/)."""

from django.test import Client, TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


class StudioTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.cliente = Cliente.objects.create(
            nombre='Org Studio',
            contacto_principal='A',
            email='st@test.com',
            telefono='573009999010',
            activo=True,
        )
        self.curso = Curso.objects.create(
            nombre='Curso Studio',
            descripcion='Público',
            cliente=self.cliente,
            activo=True,
            visible_en_studio=True,
        )
        Modulo.objects.create(
            curso=self.curso, numero=1, titulo='L1', descripcion='', contenido='x',
        )
        self.est = Estudiante.objects.create(
            cedula='st1',
            nombre='Est Studio',
            telefono='573009999011',
            cliente=self.cliente,
            activo=True,
        )

    def test_inicio_carga(self):
        r = self.http.get('/studio/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'eki Studio')

    def test_subdominio_studio_redirige_raiz(self):
        r = self.http.get('/', HTTP_HOST='studio.eki.technology')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/studio/')

    def test_catalogo_e_inscripcion(self):
        self.http.post('/studio/cuenta/registro/', {
            'nombre': 'Est Studio',
            'email': 'estudio@test.com',
            'password': 'testpass123',
        })
        r = self.http.get('/studio/cursos/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curso Studio')

        r2 = self.http.post(f'/studio/inscribir/{self.curso.id}/')
        self.assertEqual(r2.status_code, 302)
        est = Estudiante.objects.get(cedula__startswith='WEB')
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est, curso=self.curso).exists()
        )

    def test_whatsapp_login_legacy(self):
        self.http.post('/studio/estudiante/whatsapp/', {
            'cedula': 'st1',
            'telefono': '3009999011',
        })
        r = self.http.get('/studio/cursos/')
        self.assertEqual(r.status_code, 200)

    def test_no_inscribir_curso_de_otra_org(self):
        otra = Cliente.objects.create(
            nombre='Otra',
            contacto_principal='B',
            email='b@t.com',
            telefono='573009999012',
            activo=True,
        )
        ajeno = Curso.objects.create(
            nombre='Ajeno',
            cliente=otra,
            activo=True,
            visible_en_studio=True,
        )
        self.http.post('/studio/estudiante/whatsapp/', {
            'cedula': 'st1',
            'telefono': '3009999011',
        })
        r = self.http.post(f'/studio/inscribir/{ajeno.id}/')
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
            visible_en_studio=True,
        )
        r = self.http.get('/studio/cursos/')
        self.assertContains(r, 'Curso General')

    def test_curso_pago_requiere_confirmacion(self):
        from studio.models import PublicacionStudio

        PublicacionStudio.objects.create(curso=self.curso, precio_cop=99000)
        self.http.post('/studio/cuenta/registro/', {
            'nombre': 'Comprador',
            'email': 'buyer@test.com',
            'password': 'testpass123',
        })
        r = self.http.post(f'/studio/inscribir/{self.curso.id}/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/studio/pagar/', r.url)
        self.assertFalse(
            ProgresoEstudiante.objects.filter(curso=self.curso).exists()
        )

    def test_aula_sin_catalogo(self):
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'st1',
            'telefono': '3009999011',
        })
        r = self.http.get('/aprende/estudiante/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Inscribirme')
        self.assertContains(r, 'eki Studio')
