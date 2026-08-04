"""Alta de módulo: plantilla Estructura + Microcontenidos; tabs Unfold."""

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.admin.cursos import (
    MODULO_ALTA_PASOS_PLANTILLA,
    ModuloAdmin,
    sembrar_plantilla_modulo,
)
from core.models import Cliente, Curso, Modulo, PasoModulo, SeccionModulo


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
        setattr(req, 'session', 'session')
        setattr(req, '_messages', FallbackStorage(req))
        resp = self.admin.response_add(req, mod)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('admin:core_modulo_change', args=[mod.pk]))

    def test_sembrar_plantilla_crea_estructura_y_pasos_inactivos(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=10,
            titulo='Plantilla',
            descripcion='d',
            contenido='',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        created = sembrar_plantilla_modulo(mod)
        self.assertTrue(created['seccion'])
        self.assertEqual(created['pasos'], MODULO_ALTA_PASOS_PLANTILLA)
        self.assertEqual(mod.secciones.count(), 1)
        self.assertEqual(mod.pasos.count(), MODULO_ALTA_PASOS_PLANTILLA)
        self.assertFalse(mod.pasos.filter(activo=True).exists())
        sec = mod.secciones.get()
        self.assertEqual(sec.titulo, 'Bloque 1')
        self.assertTrue(all(p.seccion_id == sec.pk for p in mod.pasos.all()))

    def test_sembrar_plantilla_no_duplica(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=11,
            titulo='Ya tiene',
            descripcion='d',
            contenido='x',
        )
        sec = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='Existente')
        PasoModulo.objects.create(
            modulo=mod, seccion=sec, orden=1, titulo='p1', contenido='hola', activo=True,
        )
        created = sembrar_plantilla_modulo(mod)
        self.assertFalse(created['seccion'])
        self.assertEqual(created['pasos'], 0)
        self.assertEqual(mod.secciones.count(), 1)
        self.assertEqual(mod.pasos.count(), 1)

    def test_alta_inicial_modo_pasos(self):
        req = self.rf.get('/admin/core/modulo/add/')
        req.user = self.user
        data = self.admin.get_changeform_initial_data(req)
        self.assertEqual(data.get('modo_entrega'), Modulo.MODO_ENTREGA_PASOS)

    def test_inlines_tienen_tab_unfold(self):
        for inline_cls in self.admin.inlines:
            self.assertTrue(
                getattr(inline_cls, 'tab', False),
                f'{inline_cls.__name__} debe tener tab=True (Unfold)',
            )

    def test_edicion_muestra_micro_y_tabs_estructura(self):
        """Tras guardar, Microcontenidos y pestañas Unfold (Estructura / Microcontenidos)."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Tabs',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        sembrar_plantilla_modulo(mod)
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_modulo_change', args=[mod.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('id="pasos-group"', body)
        self.assertIn('id="secciones-group"', body)
        # Unfold inline tabs (slug = formset prefix)
        self.assertIn('href="#secciones"', body)
        self.assertIn('href="#pasos"', body)
        self.assertIn('Estructura', body)
        self.assertIn('Microcontenidos', body)
        self.assertIn('Multimedia legacy', body)
        # Sin anclas Jazzmin con tildes rotas
        self.assertNotIn('href="#guía', body)
        self.assertNotIn('href="#duración', body)
        self.assertIn('pasos-0-contenido', body)
        self.assertIn('pasos-0-seccion', body)
