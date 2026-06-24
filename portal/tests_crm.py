"""Tests CRM portal: dashboard ops, timeline, usuarios, conversaciones."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.models_extras import GrupoEstudiantes
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario


class PortalCrmTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='CRM Org',
            contacto_principal='Ana',
            email='crm@test.com',
            telefono='573001234500',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
            tipo_proyecto='cursos',
        )
        self.user_admin = User.objects.create_user('crm_admin', password='pass1234')
        self.user_viewer = User.objects.create_user('crm_viewer', password='pass1234')
        PortalUsuario.objects.create(user=self.user_admin, organizacion=self.cliente, rol='admin')
        PortalUsuario.objects.create(user=self.user_viewer, organizacion=self.cliente, rol='viewer')
        self.http = Client()

        self.curso = Curso.objects.create(
            nombre='Curso CRM', descripcion='d', cliente=self.cliente, activo=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            cedula='8001', nombre='Est CRM', telefono='573222222201', cliente=self.cliente,
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.m1,
        )
        self.grupo = GrupoEstudiantes.objects.create(
            nombre='Grupo Norte', cliente=self.cliente, activo=True,
        )
        self.grupo.estudiantes.add(self.est)

    def _login(self, username):
        pu = PortalUsuario.objects.get(user__username=username)
        session = self.http.session
        session[PORTAL_SESSION_KEY] = pu.pk
        session.save()

    def test_dashboard_operacion_del_dia(self):
        self._login('crm_admin')
        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Operación del día')
        self.assertContains(r, 'Este mes vs mes anterior')

    def test_timeline_page(self):
        self._login('crm_admin')
        r = self.http.get('/portal/timeline/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Línea de tiempo')

    def test_usuarios_solo_admin(self):
        self._login('crm_viewer')
        r = self.http.get('/portal/usuarios/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/portal/dashboard/', r.url)

    def test_usuarios_admin_crea(self):
        self._login('crm_admin')
        r = self.http.post('/portal/usuarios/', {
            'username': 'nuevo_coord',
            'first_name': 'Nuevo',
            'last_name': 'Coord',
            'email': 'nuevo@test.com',
            'password1': 'Segura123!',
            'password2': 'Segura123!',
            'rol': 'viewer',
            'is_active': 'on',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='nuevo_coord').exists())
        self.assertTrue(
            PortalUsuario.objects.filter(user__username='nuevo_coord', organizacion=self.cliente).exists()
        )

    @patch('portal.views.enviar_whatsapp_respuesta', return_value=True)
    def test_conversaciones_post_admin(self, mock_send):
        self._login('crm_admin')
        r = self.http.post('/portal/conversaciones/', {
            'estudiante_id': str(self.est.pk),
            'mensaje': 'Hola desde portal',
        })
        self.assertEqual(r.status_code, 302)
        mock_send.assert_called_once()
        self.assertIn(f'estudiante={self.est.pk}', r.url)

    def test_gamificacion_page(self):
        self._login('crm_admin')
        r = self.http.get('/portal/gamificacion/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Gamificación')
