"""Tests UX admin de alta de Módulo (sin depender del manifest Jazzmin)."""

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from core.admin.cursos import ModuloAdmin
from core.models import Cliente, Curso, Modulo


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ModuloAdminUxTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Modulo UX',
            contacto_principal='Ana',
            email='modux@test.com',
            telefono='573001110011',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso UX Admin',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Existente',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        self.admin = ModuloAdmin(Modulo, site)
        self.rf = RequestFactory()
        self.user = User.objects.create_superuser('mod_ux_admin', 'm@t.com', 'pass12345')

    def _req(self, path='/admin/core/modulo/add/', data=None):
        req = self.rf.get(path, data or {})
        req.user = self.user
        return req

    def test_initial_precarga_curso_y_siguiente_numero(self):
        req = self._req(data={'_changelist_filters': f'curso__id__exact={self.curso.id}'})
        initial = self.admin.get_changeform_initial_data(req)
        self.assertEqual(initial.get('curso'), self.curso.id)
        self.assertEqual(initial.get('numero'), 3)

    def test_fieldsets_alta_usan_guia_corta(self):
        req = self._req()
        titles = [fs[0] for fs in self.admin.get_fieldsets(req, None)]
        self.assertIn('Antes de empezar', titles)
        self.assertIn('Identidad del módulo', titles)
        self.assertNotIn('📱 Guía: envío por WhatsApp (*listo*)', titles)
        self.assertEqual(self.admin.get_readonly_fields(req, None), ('guia_alta_modulo',))

    def test_fieldsets_edicion_conservan_guia_whatsapp(self):
        req = self._req()
        mod = Modulo.objects.get(curso=self.curso, numero=2)
        titles = [fs[0] for fs in self.admin.get_fieldsets(req, mod)]
        self.assertIn('📱 Guía: envío por WhatsApp (*listo*)', titles)
        self.assertEqual(
            self.admin.get_readonly_fields(req, mod),
            ('guia_microcontenidos_whatsapp',),
        )

    def test_alta_oculta_inlines_avanzados(self):
        req = self._req()
        names = [type(i).__name__ for i in self.admin.get_inline_instances(req, None)]
        self.assertIn('SeccionModuloInline', names)
        self.assertNotIn('PasoModuloInline', names)
        self.assertNotIn('ArchivoModuloInline', names)
        self.assertNotIn('PreguntaModuloInline', names)

    def test_edicion_muestra_inlines_completos(self):
        req = self._req()
        mod = Modulo.objects.get(curso=self.curso, numero=2)
        names = [type(i).__name__ for i in self.admin.get_inline_instances(req, mod)]
        self.assertIn('SeccionModuloInline', names)
        self.assertIn('PasoModuloInline', names)
        self.assertIn('ArchivoModuloInline', names)
        self.assertIn('PreguntaModuloInline', names)
