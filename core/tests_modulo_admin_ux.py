"""Tests UX admin de alta de Módulo (sin depender del manifest Jazzmin)."""

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from core.admin.cursos import (
    ModuloAdmin,
    ModuloAdminForm,
)
from core.bloques_modulo import crear_secciones_desde_titulos, parse_titulos_bloques_rapidos
from core.models import Cliente, Curso, Modulo, SeccionModulo


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

    def test_parse_bloques_rapidos(self):
        self.assertEqual(
            parse_titulos_bloques_rapidos('  Intro \n\nPráctica\n'),
            ['Intro', 'Práctica'],
        )

    def test_initial_precarga_curso_y_siguiente_numero(self):
        req = self._req(data={'_changelist_filters': f'curso__id__exact={self.curso.id}'})
        initial = self.admin.get_changeform_initial_data(req)
        self.assertEqual(initial.get('curso'), self.curso.id)
        self.assertEqual(initial.get('numero'), 3)
        self.assertIn('Introducción', initial.get('bloques_rapidos') or '')

    def test_fieldsets_alta_integran_bloques(self):
        req = self._req()
        titles = [fs[0] for fs in self.admin.get_fieldsets(req, None)]
        self.assertIn('2. Bloques del recorrido', titles)
        self.assertIn('1. Identidad', titles)
        fields_bloques = dict(self.admin.get_fieldsets(req, None))['2. Bloques del recorrido']['fields']
        self.assertIn('bloques_rapidos', fields_bloques)

    def test_alta_sin_inlines_separados(self):
        req = self._req()
        self.assertEqual(self.admin.get_inline_instances(req, None), [])

    def test_edicion_muestra_inlines_completos(self):
        req = self._req()
        mod = Modulo.objects.get(curso=self.curso, numero=2)
        names = [type(i).__name__ for i in self.admin.get_inline_instances(req, mod)]
        self.assertIn('SeccionModuloInline', names)
        self.assertIn('PasoModuloInline', names)

    def test_form_alta_rellena_contenido_desde_bloques(self):
        form = ModuloAdminForm(data={
            'curso': self.curso.id,
            'numero': 5,
            'titulo': 'Nuevo',
            'descripcion': 'desc',
            'contenido': '',
            'bloques_rapidos': 'A\nB\nC',
            'modo_entrega': 'auto',
            'secciones_por_listo': 1,
            'facilitador_checkpoint': 'auto',
            'duracion_dias': 7,
            'examen_obligatorio': False,
            'puntaje_minimo_aprobacion': 70,
            'video_resolucion': '360p',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('• A', form.cleaned_data['contenido'])

    def test_crear_secciones_desde_titulos(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=9,
            titulo='Con bloques',
            descripcion='d',
            contenido='texto',
        )
        n = crear_secciones_desde_titulos(mod, ['Uno', 'Dos'])
        self.assertEqual(n, 2)
        self.assertEqual(
            list(SeccionModulo.objects.filter(modulo=mod).order_by('orden').values_list('titulo', flat=True)),
            ['Uno', 'Dos'],
        )
