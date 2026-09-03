"""Course Engine en portal: acceso, contrato ajax y selección de voz."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.course_engine.voice_config import DEFAULT_VOICES, label_voz
from core.models import Cliente, Curso
from portal.models import PortalUsuario


@override_settings(SECURE_SSL_REDIRECT=False)
class PortalCourseEngineTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.org = Cliente.objects.create(
            nombre='Org CE',
            contacto_principal='A',
            email='ce@test.com',
            telefono='573001111010',
            activo=True,
            portal_productos='cursos',
        )
        self.otra_org = Cliente.objects.create(
            nombre='Org Ajena',
            contacto_principal='B',
            email='ce2@test.com',
            telefono='573001111011',
            activo=True,
            portal_productos='cursos',
        )
        self.curso = Curso.objects.create(nombre='Curso CE', cliente=self.org, activo=True)
        self.curso_ajeno = Curso.objects.create(
            nombre='Curso Ajeno', cliente=self.otra_org, activo=True
        )

        self.admin_user = User.objects.create_user('ce_admin', 'a@t.com', 'pass')
        PortalUsuario.objects.create(user=self.admin_user, organizacion=self.org, rol='admin')

        self.viewer = User.objects.create_user('ce_viewer', 'v@t.com', 'pass')
        PortalUsuario.objects.create(user=self.viewer, organizacion=self.org, rol='viewer')

    def _login(self, username):
        self.http.post('/portal/login/', {'username': username, 'password': 'pass'})

    def _url(self, curso=None):
        return f'/portal/cursos/{(curso or self.curso).pk}/course-engine/'

    def test_admin_org_ve_la_pagina(self):
        self._login('ce_admin')
        r = self.http.get(self._url())
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('ce-studio', html)
        self.assertIn('Sube tus documentos', html)
        self.assertIn('Elige la voz', html)

    def test_viewer_no_entra(self):
        self._login('ce_viewer')
        r = self.http.get(self._url())
        self.assertEqual(r.status_code, 302)

    def test_anonimo_va_a_login(self):
        r = self.http.get(self._url())
        self.assertEqual(r.status_code, 302)
        self.assertIn('/portal/login/', r.url)

    def test_admin_no_toca_curso_de_otra_org(self):
        self._login('ce_admin')
        r = self.http.get(self._url(self.curso_ajeno))
        self.assertEqual(r.status_code, 302)

    def test_set_voice_guarda_en_el_curso(self):
        self._login('ce_admin')
        voz = DEFAULT_VOICES[1]
        esperado = label_voz(voz['id'])
        r = self.http.post(self._url(), {'action': 'set_voice', 'voice_id': voz['id']})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['voice_label'], esperado)
        self.assertIn(voz['label'], esperado)

        self.curso.refresh_from_db()
        self.assertEqual(self.curso.course_engine_voice_id, voz['id'])
        self.assertEqual(self.curso.course_engine_voice_label, esperado)

    def test_set_voice_rechaza_voz_fuera_de_catalogo(self):
        self._login('ce_admin')
        r = self.http.post(self._url(), {'action': 'set_voice', 'voice_id': 'no_existe'})
        self.assertEqual(r.status_code, 400)
        self.curso.refresh_from_db()
        self.assertEqual(self.curso.course_engine_voice_id, '')

    def test_set_voice_de_otra_org_prohibido(self):
        self._login('ce_admin')
        r = self.http.post(
            self._url(self.curso_ajeno),
            {'action': 'set_voice', 'voice_id': DEFAULT_VOICES[0]['id']},
        )
        self.assertEqual(r.status_code, 403)
        self.curso_ajeno.refresh_from_db()
        self.assertEqual(self.curso_ajeno.course_engine_voice_id, '')

    def test_docs_devuelve_json(self):
        self._login('ce_admin')
        r = self.http.get(self._url() + '?docs=1')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertEqual(r.json()['documentos'], [])

    def test_accion_desconocida_400(self):
        self._login('ce_admin')
        r = self.http.post(self._url(), {'action': 'borrar_todo'})
        self.assertEqual(r.status_code, 400)
