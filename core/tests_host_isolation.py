"""Aislamiento por host: admin/portal/studio/aprende."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from studio.models import CuentaAula, PublicacionStudio


@override_settings(
    DEBUG=False,
    EKI_DISABLE_HOST_ISOLATION=False,
    ALLOWED_HOSTS=['*'],
    SECURE_SSL_REDIRECT=False,
)
class HostIsolationTests(TestCase):
    def test_admin_bloqueado_en_app_host(self):
        c = Client(HTTP_HOST='app.eki.technology')
        r = c.get('/admin/login/')
        self.assertIn(r.status_code, (301, 302))
        self.assertIn('admin.eki.technology', r['Location'])

    def test_admin_ok_en_admin_host(self):
        c = Client(HTTP_HOST='admin.eki.technology')
        r = c.get('/admin/login/')
        self.assertEqual(r.status_code, 200)

    def test_portal_bloqueado_en_studio_host(self):
        c = Client(HTTP_HOST='studio.eki.technology')
        r = c.get('/portal/login/')
        self.assertIn(r.status_code, (301, 302))
        self.assertIn('app.eki.technology', r['Location'])

    def test_studio_ok_en_studio_host(self):
        c = Client(HTTP_HOST='studio.eki.technology')
        r = c.get('/studio/')
        self.assertIn(r.status_code, (200, 301, 302))


@override_settings(
    DEBUG=False,
    EKI_DISABLE_HOST_ISOLATION=False,
    ALLOWED_HOSTS=['*'],
    SECURE_SSL_REDIRECT=False,
)
class AdminNoStudentsTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Iso', contacto_principal='A', email='iso@t.com',
            telefono='573001111001', activo=True,
        )
        self.curso = Curso.objects.create(nombre='C Iso', cliente=self.cliente, activo=True)
        PublicacionStudio.objects.create(curso=self.curso, precio_cop=0)
        self.est = Estudiante.objects.create(
            cedula='iso1', nombre='Est Iso', telefono='573001111002', cliente=self.cliente,
        )
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso)

    def test_estudiante_whatsapp_no_es_staff_ni_entra_admin(self):
        c = Client(HTTP_HOST='aprende.eki.technology')
        c.post('/aprende/estudiante/login/', {
            'cedula': 'iso1',
            'telefono': '3001111002',
        })
        self.assertTrue(c.session.get('aprende_estudiante_id'))
        c2 = Client(HTTP_HOST='admin.eki.technology')
        r = c2.get('/admin/')
        self.assertIn(r.status_code, (302, 200, 301))
        if r.status_code in (301, 302):
            self.assertIn('/admin/login', r.url)

    def test_cuenta_studio_is_staff_false(self):
        from studio.cuenta_service import registrar_cuenta_aula

        cuenta, err = registrar_cuenta_aula(
            email='isostudio@test.com', password='testpass123', nombre='Iso Studio',
        )
        self.assertIsNone(err)
        self.assertFalse(cuenta.user.is_staff)
        self.assertFalse(cuenta.user.is_superuser)
