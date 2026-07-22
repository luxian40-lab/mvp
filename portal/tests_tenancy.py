"""Tests aislamiento por organización (tenancy suave)."""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Estudiante
from portal.models import PortalUsuario
from portal.tenancy import assert_same_org, scoped_to_org


@override_settings(SECURE_SSL_REDIRECT=False)
class TenancyIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Cliente.objects.create(
            nombre='Org A Tenancy',
            contacto_principal='A',
            email='ten-a@test.com',
            telefono='573001111101',
            activo=True,
            portal_productos='cursos',
        )
        self.org_b = Cliente.objects.create(
            nombre='Org B Tenancy',
            contacto_principal='B',
            email='ten-b@test.com',
            telefono='573001111102',
            activo=True,
            portal_productos='cursos',
        )
        self.est_a = Estudiante.objects.create(
            nombre='Est A',
            cedula='TEN1001',
            telefono='573001111201',
            cliente=self.org_a,
            activo=True,
        )
        self.est_b = Estudiante.objects.create(
            nombre='Est B',
            cedula='TEN1002',
            telefono='573001111202',
            cliente=self.org_b,
            activo=True,
        )
        self.curso_a = Curso.objects.create(
            nombre='Curso A',
            descripcion='d',
            cliente=self.org_a,
            activo=True,
        )
        self.curso_b = Curso.objects.create(
            nombre='Curso B',
            descripcion='d',
            cliente=self.org_b,
            activo=True,
        )
        self.admin_a = User.objects.create_user('ten_admin_a', 'a@t.com', 'pass')
        PortalUsuario.objects.create(user=self.admin_a, organizacion=self.org_a, rol='admin')
        self.http = Client()
        self.http.post('/portal/login/', {'username': 'ten_admin_a', 'password': 'pass'})

    def test_scoped_to_org_filtra_estudiantes(self):
        qs = scoped_to_org(Estudiante.objects.all(), self.org_a)
        ids = set(qs.values_list('pk', flat=True))
        self.assertIn(self.est_a.pk, ids)
        self.assertNotIn(self.est_b.pk, ids)

    def test_assert_same_org_bloquea_cruzado(self):
        assert_same_org(self.curso_a, self.org_a)
        with self.assertRaises(PermissionDenied):
            assert_same_org(self.curso_b, self.org_a)

    def test_portal_cliente_no_ve_curso_ajeno_en_lista(self):
        r = self.http.get('/portal/cursos/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curso A')
        self.assertNotContains(r, 'Curso B')

    def test_portal_estudiante_ajeno_404(self):
        r = self.http.get(f'/portal/estudiantes/{self.est_b.pk}/')
        self.assertIn(r.status_code, (404, 302, 403))
