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
        setattr(req, 'session', {})
        names_add = [type(i).__name__ for i in self.admin.get_inline_instances(req, None)]
        self.assertNotIn('PasoModuloInline', names_add)
        self.assertNotIn('SeccionModuloInline', names_add)

        mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Nuevo',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        req_adv = self.rf.get('/admin/core/modulo/1/change/', {'avanzado': '1'})
        req_adv.user = self.user
        setattr(req_adv, 'session', {})
        names_edit = [type(i).__name__ for i in self.admin.get_inline_instances(req_adv, mod)]
        self.assertIn('PasoModuloInline', names_edit)
        self.assertIn('SeccionModuloInline', names_edit)

    def _req_post_messages(self, path='/admin/core/modulo/add/', data=None):
        req = self.rf.post(path, data or {})
        req.user = self.user
        session = {}
        setattr(req, 'session', session)
        setattr(req, '_messages', FallbackStorage(req))
        return req

    @override_settings(EKI_MODULE_BUILDER_BETA=False, EKI_MODULE_BUILDER_CURSOS='')
    def test_response_add_redirige_a_edicion_sin_builder(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Creado',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        resp = self.admin.response_add(
            self._req_post_messages(data={'modo_creacion': 'clase'}),
            mod,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('admin:core_modulo_change', args=[mod.pk]), resp.url)
        self.assertIn('modo=clase', resp.url)

    @override_settings(EKI_MODULE_BUILDER_BETA=False, EKI_MODULE_BUILDER_CURSOS='*')
    def test_response_add_redirige_a_builder(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Creado Builder',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        resp = self.admin.response_add(
            self._req_post_messages(data={'modo_creacion': 'builder'}),
            mod,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('admin_module_builder', kwargs={'modulo_id': mod.pk}))

    @override_settings(EKI_MODULE_BUILDER_BETA=False, EKI_MODULE_BUILDER_CURSOS='*')
    def test_response_add_default_es_clase_no_fuerza_builder(self):
        """Default happy path = clase aunque Builder esté ON."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=31,
            titulo='Default clase',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        resp = self.admin.response_add(self._req_post_messages(), mod)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('modo=clase', resp.url)
        self.assertNotIn('module-builder', resp.url)

    @override_settings(EKI_MODULE_BUILDER_BETA=False, EKI_MODULE_BUILDER_CURSOS='*')
    def test_response_change_redirige_a_builder(self):
        from core.modulo_authoring_mode import MODO_BUILDER, set_modulo_modo

        mod = Modulo.objects.create(
            curso=self.curso,
            numero=4,
            titulo='Edit Builder',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        req = self._req_post_messages(f'/admin/core/modulo/{mod.pk}/change/')
        set_modulo_modo(req, mod.pk, MODO_BUILDER)
        resp = self.admin.response_change(req, mod)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('admin_module_builder', kwargs={'modulo_id': mod.pk}))

    @override_settings(EKI_MODULE_BUILDER_BETA=False, EKI_MODULE_BUILDER_CURSOS='*')
    def test_response_change_clase_no_fuerza_builder(self):
        from core.modulo_authoring_mode import MODO_CLASE, set_modulo_modo

        mod = Modulo.objects.create(
            curso=self.curso,
            numero=41,
            titulo='Edit Clase',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        req = self._req_post_messages(f'/admin/core/modulo/{mod.pk}/change/')
        set_modulo_modo(req, mod.pk, MODO_CLASE)
        resp = self.admin.response_change(req, mod)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('modo=clase', resp.url)

    @override_settings(EKI_MODULE_BUILDER_BETA=False, EKI_MODULE_BUILDER_CURSOS='*')
    def test_response_change_continue_no_fuerza_builder(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=5,
            titulo='Continue',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        resp = self.admin.response_change(
            self._req_post_messages(
                f'/admin/core/modulo/{mod.pk}/change/',
                {'_continue': '1'},
            ),
            mod,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('admin:core_modulo_change', args=[mod.pk]))

    def test_modo_clase_oculta_inlines(self):
        from core.modulo_authoring_mode import MODO_CLASE, set_modulo_modo

        mod = Modulo.objects.create(
            curso=self.curso,
            numero=6,
            titulo='Solo clase',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        req = self.rf.get(f'/admin/core/modulo/{mod.pk}/change/', {'modo': 'clase'})
        req.user = self.user
        setattr(req, 'session', {})
        set_modulo_modo(req, mod.pk, MODO_CLASE)
        names = [type(i).__name__ for i in self.admin.get_inline_instances(req, mod)]
        self.assertEqual(names, [])

    def test_fieldsets_alta_incluye_modo_creacion(self):
        req = self.rf.get('/admin/core/modulo/add/')
        req.user = self.user
        setattr(req, 'session', {})
        fs = self.admin.get_fieldsets(req, None)
        self.assertEqual(fs[0][0], 'Clase')
        self.assertNotIn('tab', fs[0][1].get('classes') or [])
        fields = fs[0][1]['fields']
        self.assertIn('modo_creacion', fields)
        self.assertIn('titulo', fields)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_alta_html_muestra_campos_no_solo_intro(self):
        """Regresión: alta no debe quedar en blanco (tabs Unfold + jump IR A)."""
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_modulo_add'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('data-eki-modulo-add', body)
        self.assertIn('name="modo_creacion"', body)
        self.assertIn('name="titulo"', body)
        self.assertIn('name="curso"', body)
        self.assertIn('clase_texto', body)
        # Unfold: fieldsets visibles solo con primary activeTab=general
        self.assertIn("activeTab == 'general'", body)
        self.assertNotIn('id="eki-modulo-jump"', body)

    def test_jump_js_no_pone_active_tab_clase_como_primary(self):
        """Contrato anti- Panamá: never assign Alpine primary activeTab to fieldset slug."""
        from pathlib import Path

        js = Path('static/admin/js/eki_modulo_jump.js').read_text(encoding='utf-8')
        self.assertIn('PRIMARY_GENERAL', js)
        self.assertIn("FIELDSET_ONLY_SLUGS", js)
        # Prohibido asignación literal al primary (comentarios no cuentan: strip)
        code = '\n'.join(
            ln for ln in js.splitlines()
            if not ln.strip().startswith('*') and not ln.strip().startswith('//')
        )
        self.assertNotRegex(code, r"activeTab\s*=\s*['\"]clase['\"]")
        self.assertIn("setPrimaryTab(PRIMARY_GENERAL)", js)

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
        """Con ?avanzado=1: pestañas Unfold Clase / Estructura / Materiales."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Tabs',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        sembrar_plantilla_modulo(mod)
        self.client.force_login(self.user)
        r = self.client.get(
            reverse('admin:core_modulo_change', args=[mod.pk]) + '?avanzado=1'
        )
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('id="pasos-group"', body)
        self.assertIn('id="secciones-group"', body)
        # Unfold inline tabs (slug = formset prefix)
        self.assertIn('href="#secciones"', body)
        self.assertIn('href="#pasos"', body)
        self.assertIn('Estructura', body)
        self.assertIn('Materiales', body)
        self.assertNotIn('Media (legacy)', body)
        self.assertIn('Clase', body)
        self.assertIn('clase_archivo', body)
        # Sin anclas Jazzmin con tildes rotas
        self.assertNotIn('href="#guía', body)
        self.assertNotIn('href="#duración', body)
        self.assertIn('pasos-0-contenido', body)
        self.assertIn('pasos-0-seccion', body)

    # --- QA adversario: intentar romper happy path A/B ---

    @override_settings(EKI_MODULE_BUILDER_BETA=False, EKI_MODULE_BUILDER_CURSOS='')
    def test_break_builder_elegido_pero_flag_off_cae_a_clase(self):
        """Modo B + Builder OFF → no 500; warning + redirect ?modo=clase."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=50,
            titulo='Builder off',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        resp = self.admin.response_add(
            self._req_post_messages(data={'modo_creacion': 'builder'}),
            mod,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('modo=clase', resp.url)
        self.assertNotIn('module-builder', resp.url)

    def test_break_modo_basura_normaliza_a_clase(self):
        from core.modulo_authoring_mode import normalizar_modo

        self.assertEqual(normalizar_modo('???'), 'clase')
        self.assertEqual(normalizar_modo(''), 'clase')
        self.assertEqual(normalizar_modo(None), 'clase')
        self.assertEqual(normalizar_modo('BUILDER'), 'builder')
        self.assertEqual(normalizar_modo('a'), 'clase')

    @override_settings(
        EKI_MODULE_BUILDER_BETA=False,
        EKI_MODULE_BUILDER_CURSOS='',
        SECURE_SSL_REDIRECT=False,
    )
    def test_break_builder_sin_habilitar_curso_no_redirige(self):
        """?modo=builder con BETA off y sin allowlist → se queda en admin (200)."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=51,
            titulo='Sin allowlist',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        self.client.force_login(self.user)
        r = self.client.get(
            reverse('admin:core_modulo_change', args=[mod.pk]) + '?modo=builder',
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b'/admin/module-builder/', r.content)

    def test_break_session_perdida_default_clase_en_save(self):
        """Sin sesión de modo → response_change no fuerza Builder."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=52,
            titulo='Sin sesion',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        with override_settings(EKI_MODULE_BUILDER_BETA=True, EKI_MODULE_BUILDER_CURSOS='*'):
            resp = self.admin.response_change(
                self._req_post_messages(f'/admin/core/modulo/{mod.pk}/change/'),
                mod,
            )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('modo=clase', resp.url)
        self.assertNotIn('module-builder', resp.url)

    def test_break_avanzado_rompe_modo_clase_y_muestra_inlines(self):
        """?avanzado=1 gana sobre modo clase (escape hatch legacy)."""
        from core.modulo_authoring_mode import MODO_CLASE, set_modulo_modo

        mod = Modulo.objects.create(
            curso=self.curso,
            numero=53,
            titulo='Avanzado',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
        )
        req = self.rf.get(
            f'/admin/core/modulo/{mod.pk}/change/',
            {'modo': 'clase', 'avanzado': '1'},
        )
        req.user = self.user
        setattr(req, 'session', {})
        set_modulo_modo(req, mod.pk, MODO_CLASE)
        names = [type(i).__name__ for i in self.admin.get_inline_instances(req, mod)]
        self.assertIn('PasoModuloInline', names)
        self.assertIn('SeccionModuloInline', names)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_post_alta_clase_guarda_modulo(self):
        """QA P0: Grabar en alta (camino rápido) debe crear el módulo (no solo redirigir)."""
        self.client.force_login(self.user)
        before = Modulo.objects.count()
        r = self.client.post(
            reverse('admin:core_modulo_add'),
            {
                'modo_creacion': 'clase',
                'curso': str(self.curso.pk),
                'numero': '99',
                'titulo': 'Alta happy path',
                'clase_texto': 'Contenido de clase de prueba',
                'clase_activo': 'on',
            },
        )
        self.assertIn(r.status_code, (302, 200), msg=r.content[:500] if r.status_code == 200 else '')
        if r.status_code == 200:
            body = r.content.decode('utf-8')
            self.fail('Alta rechazada. Fragmento: ' + body[body.find('error'):body.find('error') + 400])
        self.assertEqual(Modulo.objects.count(), before + 1)
        mod = Modulo.objects.get(titulo='Alta happy path')
        self.assertEqual(mod.curso_id, self.curso.pk)
        self.assertTrue((mod.descripcion or '').strip())
        self.assertIn('modo=clase', r.url)
        # Tras crear, la ficha change no debe 500 (Unfold actions_detail + @action).
        follow = self.client.get(r.url)
        self.assertEqual(follow.status_code, 200, msg=follow.content[:400])
        self.assertContains(follow, 'Alta happy path')

    def test_jump_js_filtra_errornote_generico(self):
        from pathlib import Path

        js = Path('static/admin/js/eki_modulo_jump.js').read_text(encoding='utf-8')
        self.assertIn('corrija los siguientes errores', js)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_break_alta_sin_curso_no_500(self):
        """POST alta incompleta → form errors, no crash."""
        self.client.force_login(self.user)
        r = self.client.post(
            reverse('admin:core_modulo_add'),
            {
                'modo_creacion': 'clase',
                'numero': '1',
                'titulo': 'Sin curso',
                'clase_texto': 'hola',
                'clase_activo': 'on',
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'error', status_code=200)
        self.assertFalse(Modulo.objects.filter(titulo='Sin curso').exists())
