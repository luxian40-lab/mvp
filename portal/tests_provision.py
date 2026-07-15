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


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ProfesorAulaPasswordYRedirectTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.org = Cliente.objects.create(
            nombre='Org Profesores',
            contacto_principal='Contacto',
            email='prof@test.com',
            telefono='3001112299',
            cupos_portal=5,
            fecha_fin_suscripcion='2099-12-31',
        )

    def test_establecer_password_admin_definitiva(self):
        from portal.provision import establecer_password_admin

        user, pu, _ = provisionar_usuario_portal(
            cliente=self.org,
            username='docente1',
            password='TempPass12',
            rol='profesor',
        )
        establecer_password_admin(pu, 'ClaveDefinitiva1', forzar_primer_acceso=False)
        pu.refresh_from_db()
        user.refresh_from_db()
        self.assertFalse(pu.debe_cambiar_credenciales)
        self.assertEqual(pu.password_temporal, 'ClaveDefinitiva1')
        self.assertTrue(user.check_password('ClaveDefinitiva1'))
        self.assertTrue(user.is_active)

    def test_primer_acceso_profesor_redirige_a_aula(self):
        user, pu, _ = provisionar_usuario_portal(
            cliente=self.org,
            username='docente2',
            password='TempPass12',
            rol='profesor',
        )
        session = self.http.session
        session[PORTAL_SESSION_KEY] = pu.pk
        session.save()

        r = self.http.post('/portal/primer-acceso/', {
            'first_name': 'Luis',
            'last_name': 'García',
            'password1': 'NuevaClave99',
            'password2': 'NuevaClave99',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('/aprende/profesor/', r.url)

    def test_login_portal_profesor_va_a_aula(self):
        user, pu, _ = provisionar_usuario_portal(
            cliente=self.org,
            username='docente3',
            password='ClaveLista12',
            rol='profesor',
            forzar_cambio=False,
        )
        r = self.http.post('/portal/login/', {
            'username': 'docente3',
            'password': 'ClaveLista12',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('/aprende/profesor/', r.url)

    def test_login_profesor_con_forzar_pide_primer_acceso(self):
        from portal.provision import establecer_password_admin

        user, pu, _ = provisionar_usuario_portal(
            cliente=self.org,
            username='docente_force',
            password='TempOld999',
            rol='profesor',
            forzar_cambio=False,
        )
        establecer_password_admin(pu, 'TempNueva88', forzar_primer_acceso=True)
        r = self.http.post('/aprende/profesor/login/', {
            'username': 'docente_force',
            'password': 'TempNueva88',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('/portal/primer-acceso/', r.url)

    def test_admin_profesores_aula_solo_rol_profesor(self):
        from portal.models import ProfesorAula

        _, pu_prof, _ = provisionar_usuario_portal(
            cliente=self.org,
            username='solo_prof',
            password='ClaveLista12',
            rol='profesor',
            forzar_cambio=False,
        )
        _, pu_admin, _ = provisionar_usuario_portal(
            cliente=self.org,
            username='solo_admin',
            password='ClaveLista12',
            rol='admin',
            forzar_cambio=False,
        )
        qs = ProfesorAula.objects.all()
        self.assertTrue(qs.filter(pk=pu_prof.pk).exists())
        self.assertFalse(qs.filter(pk=pu_admin.pk).exists())
        self.assertEqual(qs.filter(rol='profesor').count(), ProfesorAula.objects.count())
