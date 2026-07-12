"""Tests eki Studio (/studio/)."""

from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


@override_settings(SECURE_SSL_REDIRECT=False)
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

    def test_pago_simulado_inscribe_en_aprende(self):
        from studio.models import AccesoCursoPagado, PublicacionStudio
        from studio.pago_service import monto_en_centavos, firma_integridad_checkout

        PublicacionStudio.objects.create(curso=self.curso, precio_cop=50000)
        self.assertEqual(monto_en_centavos(50000), 5_000_000)

        self.http.post('/studio/cuenta/registro/', {
            'nombre': 'Buyer2',
            'email': 'buyer2@test.com',
            'password': 'testpass123',
        })
        r = self.http.post(f'/studio/inscribir/{self.curso.id}/')
        ref = r.url.rstrip('/').split('/')[-1]
        r2 = self.http.post(f'/studio/pagar/{ref}/confirmar/')
        self.assertEqual(r2.status_code, 302)
        self.assertIn('/aprende/estudiante/curso/', r2.url)
        self.assertTrue(
            AccesoCursoPagado.objects.filter(
                wompi_referencia=ref, estado='aprobado',
            ).exists()
        )
        self.assertTrue(
            ProgresoEstudiante.objects.filter(curso=self.curso).exists()
        )

    def test_creador_publica_curso_con_precio(self):
        from studio.models import CreadorStudio, PublicacionStudio

        self.http.post('/studio/creador/registro/', {
            'email': 'creador@test.com',
            'password': 'testpass123',
            'nombre_publico': 'Profe Test',
            'bio': 'Bio',
        })
        creador = CreadorStudio.objects.get(user__username='creador@test.com')
        creador.activo = True
        creador.save(update_fields=['activo'])

        r = self.http.post('/studio/creador/panel/', {
            'accion': 'crear',
            'nombre': 'Curso Creador',
            'descripcion': 'Aprende X',
            'precio_cop': '120000',
            'publicar': 'on',
        })
        self.assertEqual(r.status_code, 302)
        pub = PublicacionStudio.objects.get(curso__nombre='Curso Creador')
        self.assertEqual(pub.precio_cop, 120000)
        self.assertEqual(pub.creador_id, creador.pk)
        self.assertTrue(pub.curso.visible_en_studio)

    def test_aula_sin_catalogo(self):
        self.http.post('/aprende/estudiante/login/', {
            'modo': 'whatsapp',
            'cedula': 'st1',
            'telefono': '3009999011',
        })
        r = self.http.get('/aprende/estudiante/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Inscribirme')
        self.assertContains(r, 'eki Studio')

    def test_aprende_login_correo(self):
        self.http.post('/studio/cuenta/registro/', {
            'nombre': 'Web Est',
            'email': 'webest@test.com',
            'password': 'testpass123',
        })
        self.http.get('/studio/cuenta/logout/')
        r = self.http.post('/aprende/estudiante/login/', {
            'modo': 'correo',
            'email': 'webest@test.com',
            'password': 'testpass123',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('/aprende/estudiante/', r.url)
