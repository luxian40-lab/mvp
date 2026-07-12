"""Cupos portal, provisión admin y primer acceso."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings

from core.models import Cliente
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario
from portal.provision import completar_primer_acceso, provisionar_usuario_portal


@override_settings(SECURE_SSL_REDIRECT=False)
class PortalProvisionTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.org = Cliente.objects.create(
            nombre='Org Cupos',
            contacto_principal='Contacto',
            email='org@test.com',
            telefono='3001112233',
            cupos_portal=1,
        )

    def test_provision_respeta_cupos_y_no_staff(self):
        user, pu, pwd = provisionar_usuario_portal(
            cliente=self.org,
            username='u1',
            password='TempPass12',
            rol='admin',
        )
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(pu.debe_cambiar_credenciales)
        self.assertEqual(pu.password_temporal, 'TempPass12')
        self.assertEqual(pwd, 'TempPass12')
        with self.assertRaises(ValidationError):
            provisionar_usuario_portal(cliente=self.org, username='u2')

    def test_primer_acceso_limpia_temporal(self):
        user, pu, _ = provisionar_usuario_portal(
            cliente=self.org,
            username='u_first',
            password='TempPass12',
        )
        session = self.http.session
        session[PORTAL_SESSION_KEY] = pu.pk
        session.save()

        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/portal/primer-acceso/', r.url)

        r2 = self.http.post('/portal/primer-acceso/', {
            'first_name': 'Ana',
            'last_name': 'Pérez',
            'password1': 'NuevaClave99',
            'password2': 'NuevaClave99',
        })
        self.assertEqual(r2.status_code, 302)
        pu.refresh_from_db()
        user.refresh_from_db()
        self.assertFalse(pu.debe_cambiar_credenciales)
        self.assertEqual(pu.password_temporal, '')
        self.assertEqual(user.first_name, 'Ana')
        self.assertTrue(user.check_password('NuevaClave99'))
