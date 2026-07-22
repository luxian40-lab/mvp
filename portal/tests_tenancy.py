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


@override_settings(SECURE_SSL_REDIRECT=False)
class GeiTenancyOrphanTests(TestCase):
    """Fichas GEI huérfanas (cliente NULL) deben verse solo en la org del estudiante."""

    def setUp(self):
        self.org_a = Cliente.objects.create(
            nombre='Org GEI A',
            contacto_principal='A',
            email='gei-a@test.com',
            telefono='573001111301',
            activo=True,
            tipo_proyecto='gei',
            portal_productos='gei,cursos',
        )
        self.org_b = Cliente.objects.create(
            nombre='Org GEI B',
            contacto_principal='B',
            email='gei-b@test.com',
            telefono='573001111302',
            activo=True,
            tipo_proyecto='gei',
            portal_productos='gei,cursos',
        )
        self.est_a = Estudiante.objects.create(
            nombre='Est GEI A',
            cedula='GEI1001',
            telefono='573001111401',
            cliente=self.org_a,
            activo=True,
        )
        from formulario.models import FichaGEI

        self.ficha_huerfana = FichaGEI.objects.create(
            estudiante=self.est_a,
            cliente=None,
            nombre_finca='Finca huérfana',
            area_ha=1.5,
        )
        admin = User.objects.create_user('admin_gei_ten', password='x')
        PortalUsuario.objects.create(user=admin, organizacion=self.org_a, rol='admin')
        self.http = Client()
        self.http.force_login(admin)
        s = self.http.session
        from portal.middleware import PORTAL_SESSION_KEY
        s[PORTAL_SESSION_KEY] = self.org_a.pk
        s.save()

    def test_queryset_incluye_huerfana_y_repara_cliente(self):
        from datetime import date, timedelta

        from formulario.models import FichaGEI
        from portal.gei_service import queryset_fichas_org

        filtros = {
            'curso_id': None,
            'desde': date.today() - timedelta(days=30),
            'hasta': date.today() + timedelta(days=1),
        }
        qs = queryset_fichas_org(self.org_a, filtros)
        self.assertTrue(qs.filter(pk=self.ficha_huerfana.pk).exists())
        self.ficha_huerfana.refresh_from_db()
        self.assertEqual(self.ficha_huerfana.cliente_id, self.org_a.pk)

        qs_b = queryset_fichas_org(self.org_b, filtros)
        self.assertFalse(qs_b.filter(pk=self.ficha_huerfana.pk).exists())
