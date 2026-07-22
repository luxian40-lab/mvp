"""Tests semi-admin eki_ops: métricas multi-org + editor API."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Modulo, PasoModulo, SeccionModulo
from portal.models import PortalUsuario


@override_settings(SECURE_SSL_REDIRECT=False)
class EkiOpsAuthTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.org = Cliente.objects.create(
            nombre='Org Cliente',
            contacto_principal='A',
            email='ops-cli@test.com',
            telefono='573001111001',
            activo=True,
            portal_productos='cursos',
        )
        self.org2 = Cliente.objects.create(
            nombre='Org Dos',
            contacto_principal='B',
            email='ops-cli2@test.com',
            telefono='573001111002',
            activo=True,
            portal_productos='cursos',
        )
        self.admin_user = User.objects.create_user('cli_admin', 'a@t.com', 'pass')
        PortalUsuario.objects.create(user=self.admin_user, organizacion=self.org, rol='admin')

        self.ops_user = User.objects.create_user('eki_ops1', 'ops@t.com', 'pass')
        PortalUsuario.objects.create(user=self.ops_user, organizacion=self.org, rol='eki_ops')

    def _login(self, username):
        self.http.post('/portal/login/', {'username': username, 'password': 'pass'})

    def test_cliente_admin_no_entra_ops(self):
        self._login('cli_admin')
        r = self.http.get('/portal/ops/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('/portal/ops/', r.url)

    def test_eki_ops_ve_metricas(self):
        self._login('eki_ops1')
        r = self.http.get('/portal/ops/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Org Cliente')
        self.assertContains(r, 'Org Dos')

    def test_eki_ops_export_excel(self):
        self._login('eki_ops1')
        r = self.http.get('/portal/ops/metricas/exportar/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            r['Content-Type'],
        )

    def test_dashboard_redirige_ops(self):
        self._login('eki_ops1')
        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/portal/ops/')


@override_settings(SECURE_SSL_REDIRECT=False)
class EkiOpsCursoEditorApiTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.org = Cliente.objects.create(
            nombre='Org Editor',
            contacto_principal='A',
            email='ed@test.com',
            telefono='573001111003',
            activo=True,
            portal_productos='cursos',
        )
        self.ops_user = User.objects.create_user('eki_ops_ed', 'oped@t.com', 'pass')
        PortalUsuario.objects.create(user=self.ops_user, organizacion=self.org, rol='eki_ops')
        self.viewer = User.objects.create_user('viewer1', 'v@t.com', 'pass')
        PortalUsuario.objects.create(user=self.viewer, organizacion=self.org, rol='viewer')
        self.http.post('/portal/login/', {'username': 'eki_ops_ed', 'password': 'pass'})

    def test_viewer_api_forbidden(self):
        self.http.post('/portal/logout/')
        self.http.post('/portal/login/', {'username': 'viewer1', 'password': 'pass'})
        r = self.http.get('/portal/ops/api/orgs/', HTTP_ACCEPT='application/json')
        self.assertEqual(r.status_code, 403)

    def test_crear_curso_modulo_paso(self):
        r = self.http.post(
            '/portal/ops/api/cursos/',
            data='{"nombre":"Curso Ops","cliente_id":%d,"activo":true}' % self.org.pk,
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 201)
        curso_id = r.json()['curso']['id']
        self.assertTrue(Curso.objects.filter(pk=curso_id, cliente=self.org).exists())

        r2 = self.http.post(
            f'/portal/ops/api/cursos/{curso_id}/modulos/',
            data='{"titulo":"Modulo 1","modo_entrega":"pasos"}',
            content_type='application/json',
        )
        self.assertEqual(r2.status_code, 201)
        mod_id = r2.json()['modulo']['id']
        sec = SeccionModulo.objects.filter(modulo_id=mod_id).first()
        self.assertIsNotNone(sec)

        r3 = self.http.post(
            f'/portal/ops/api/secciones/{sec.pk}/pasos/',
            data='{"tipo":"contenido","contenido":"Hola campo","titulo":"Intro"}',
            content_type='application/json',
        )
        self.assertEqual(r3.status_code, 201)
        paso_id = r3.json()['paso']['id']
        self.assertTrue(PasoModulo.objects.filter(pk=paso_id, seccion=sec).exists())

        r4 = self.http.get(f'/portal/ops/api/modulos/{mod_id}/')
        self.assertEqual(r4.status_code, 200)
        self.assertEqual(len(r4.json()['pasos']), 1)

    def test_guardar_contenido_legacy_sin_pasos(self):
        from core.models import Curso, Modulo

        curso = Curso.objects.create(
            nombre='Legacy',
            descripcion='d',
            cliente=self.org,
            activo=True,
        )
        mod = Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='Intro',
            descripcion='d',
            contenido='',
            modo_entrega='legacy',
        )
        r = self.http.patch(
            f'/portal/ops/api/modulos/{mod.pk}/',
            data=(
                '{"contenido":"Hola productores del campo",'
                '"modo_entrega":"legacy","video_url":"https://example.com/v.mp4"}'
            ),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        self.assertEqual(mod.contenido, 'Hola productores del campo')
        self.assertEqual(mod.modo_entrega, 'legacy')
        self.assertIn('example.com', mod.video_url or '')

    def test_ops_estudiantes_grupos_campanas(self):
        r1 = self.http.get('/portal/ops/estudiantes/')
        r2 = self.http.get('/portal/ops/grupos/')
        r3 = self.http.get('/portal/ops/campanas/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 200)
        self.assertContains(r3, 'Nueva campaña')

    def test_editor_page_ok(self):
        r = self.http.get('/portal/ops/cursos/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'curso-editor')
