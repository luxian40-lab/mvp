"""Alta de módulo: Microcontenidos solo tras guardar; redirect a change."""

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.admin.cursos import ModuloAdmin
from core.models import Cliente, Curso, Modulo


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ModuloAltaMicrocontenidosTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Alta Micro',
            contacto_principal='Ana',
            email='alta@test.com',
            telefono='573001110011',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Alta Micro',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        self.admin = ModuloAdmin(Modulo, site)
        self.user = User.objects.create_superuser('alta_micro', 'a@t.com', 'pass12345')
        self.rf = RequestFactory()

    def test_alta_oculta_pasos_edicion_los_muestra(self):
        req = self.rf.get('/admin/core/modulo/add/')
        req.user = self.user
        names_add = [type(i).__name__ for i in self.admin.get_inline_instances(req, None)]
        self.assertNotIn('PasoModuloInline', names_add)
        self.assertIn('SeccionModuloInline', names_add)

        mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Nuevo',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        names_edit = [type(i).__name__ for i in self.admin.get_inline_instances(req, mod)]
        self.assertIn('PasoModuloInline', names_edit)

    def test_response_add_redirige_a_edicion(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Creado',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        req = self.rf.post('/admin/core/modulo/add/', {})
        req.user = self.user
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(req, 'session', 'session')
        setattr(req, '_messages', FallbackStorage(req))
        resp = self.admin.response_add(req, mod)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('admin:core_modulo_change', args=[mod.pk]))

    def test_edicion_pestanas_ascii_y_formulario_micro_vacio(self):
        """Tras guardar, Microcontenidos debe existir con extra>=1 y tabs sin tildes."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Tabs',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_modulo_change', args=[mod.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('id="pasos-group"', body)
        self.assertIn('href="#microcontenidos-tab"', body)
        self.assertIn('href="#secciones-tab"', body)
        self.assertNotIn('href="#guía', body)
        self.assertNotIn('href="#duración', body)
        self.assertNotIn('Mini examen (después', body)
        # Al menos un formulario vacío de paso (extra=1)
        self.assertIn('pasos-0-contenido', body)
        self.assertIn('pasos-0-seccion', body)
