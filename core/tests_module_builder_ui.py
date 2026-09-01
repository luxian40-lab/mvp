# -*- coding: utf-8 -*-
"""Tests Module Builder UI/logic (sin Twilio)."""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from core.models import Curso, Modulo, PasoModulo, SeccionModulo
from core.module_builder import (
    agregar_micro,
    agregar_seccion,
    arbol_modulo,
    diagnostico_estructura,
    duplicar_micro,
    media_preview_kind,
    module_builder_habilitado,
    paso_builder_ui,
    reordenar_micros_en_seccion,
    reordenar_secciones,
)
from core.module_structure import detectar_secciones_intercaladas


User = get_user_model()


class ModuleBuilderLogicTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Builder Curso')
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )

    def test_agregar_seccion_y_micros_contiguos(self):
        sa = agregar_seccion(self.mod, 'A')
        sb = agregar_seccion(self.mod, 'B')
        agregar_micro(self.mod, sa, contenido='a1')
        agregar_micro(self.mod, sb, contenido='b1')
        agregar_micro(self.mod, sa, contenido='a2')  # debe quedar junto a a1
        pasos = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True).order_by('orden', 'id')
        )
        self.assertEqual([p.contenido for p in pasos], ['a1', 'a2', 'b1'])
        self.assertEqual(detectar_secciones_intercaladas(pasos), [])
        diag = diagnostico_estructura(self.mod)
        self.assertFalse(diag['intercalado'])

    def test_arbol(self):
        sa = agregar_seccion(self.mod, 'Hechos')
        agregar_micro(self.mod, sa, titulo='Infografía', contenido='x')
        arbol, huerfanos = arbol_modulo(self.mod)
        self.assertEqual(len(arbol), 1)
        self.assertEqual(arbol[0]['n_micros'], 1)
        self.assertEqual(huerfanos, [])
        self.assertEqual(arbol[0]['micros'][0].preview_kind, 'text')

    def test_arbol_incluye_borradores_inactivos(self):
        from core.admin.cursos import sembrar_plantilla_modulo

        sembrar_plantilla_modulo(self.mod)
        arbol, _ = arbol_modulo(self.mod, incluir_inactivos=True)
        self.assertGreaterEqual(len(arbol), 1)
        self.assertGreaterEqual(arbol[0]['n_micros'], 1)
        self.assertFalse(arbol[0]['micros'][0].activo)
        arbol_act, _ = arbol_modulo(self.mod, incluir_inactivos=False)
        self.assertEqual(arbol_act[0]['n_micros'], 0)

    def test_media_preview_kind(self):
        self.assertEqual(media_preview_kind(''), 'text')
        self.assertEqual(media_preview_kind('https://x/a.PNG?v=1'), 'image')
        self.assertEqual(media_preview_kind('https://x/a.mp4'), 'video')
        self.assertEqual(media_preview_kind('https://x/a.pdf'), 'file')

    def test_paso_builder_ui_video(self):
        p = SimpleNamespace(
            tipo=PasoModulo.TIPO_CONTENIDO,
            media_url='https://x/v.mp4',
            contenido='',
            requiere_listo_para_avanzar=True,
        )
        ui = paso_builder_ui(p)
        self.assertEqual(ui['step_type'], 'video')
        self.assertEqual(ui['type_label'], 'Video')

    def test_paso_builder_ui_quiz(self):
        p = SimpleNamespace(
            tipo=PasoModulo.TIPO_EVAL_OPC,
            media_url='',
            contenido='Pregunta',
            requiere_listo_para_avanzar=True,
        )
        ui = paso_builder_ui(p)
        self.assertEqual(ui['step_type'], 'quiz')

    def test_duplicar_micro_borrador(self):
        sa = agregar_seccion(self.mod, 'A')
        p = agregar_micro(self.mod, sa, titulo='Original', contenido='texto')
        copia = duplicar_micro(p)
        self.assertFalse(copia.activo)
        self.assertIn('copia', copia.titulo.lower())
        self.assertEqual(copia.contenido, 'texto')
        pasos = list(PasoModulo.objects.filter(modulo=self.mod).order_by('orden', 'id'))
        self.assertEqual([x.pk for x in pasos], [p.pk, copia.pk])

    def test_reordenar_micros_en_seccion(self):
        sa = agregar_seccion(self.mod, 'A')
        sb = agregar_seccion(self.mod, 'B')
        a1 = agregar_micro(self.mod, sa, contenido='a1')
        a2 = agregar_micro(self.mod, sa, contenido='a2')
        b1 = agregar_micro(self.mod, sb, contenido='b1')
        reordenar_micros_en_seccion(self.mod, sa, [a2.id, a1.id])
        pasos = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True).order_by('orden', 'id')
        )
        self.assertEqual([p.contenido for p in pasos], ['a2', 'a1', 'b1'])
        self.assertEqual(detectar_secciones_intercaladas(pasos), [])

    def test_reordenar_secciones_mueve_bloques(self):
        sa = agregar_seccion(self.mod, 'A')
        sb = agregar_seccion(self.mod, 'B')
        agregar_micro(self.mod, sa, contenido='a1')
        agregar_micro(self.mod, sb, contenido='b1')
        reordenar_secciones(self.mod, [sb.id, sa.id])
        pasos = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True).order_by('orden', 'id')
        )
        self.assertEqual([p.contenido for p in pasos], ['b1', 'a1'])
        self.assertEqual(detectar_secciones_intercaladas(pasos), [])
        orden_sec = list(
            SeccionModulo.objects.filter(modulo=self.mod, activa=True)
            .order_by('orden')
            .values_list('titulo', flat=True)
        )
        self.assertEqual(orden_sec, ['B', 'A'])

    def test_reordenar_micros_rechaza_cruzar_seccion(self):
        sa = agregar_seccion(self.mod, 'A')
        sb = agregar_seccion(self.mod, 'B')
        a1 = agregar_micro(self.mod, sa, contenido='a1')
        b1 = agregar_micro(self.mod, sb, contenido='b1')
        with self.assertRaises(ValueError):
            reordenar_micros_en_seccion(self.mod, sa, [a1.id, b1.id])


class ModuleBuilderFlagTests(TestCase):
    @override_settings(EKI_MODULE_BUILDER_BETA=False)
    def test_flag_off(self):
        self.assertFalse(module_builder_habilitado(None))

    @override_settings(EKI_MODULE_BUILDER_BETA=True)
    def test_flag_on(self):
        self.assertTrue(module_builder_habilitado(None))


class ModuleBuilderViewTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Builder View')
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        self.staff = User.objects.create_user(
            username='mb_staff', password='x', is_staff=True, is_superuser=True,
        )
        self.client = Client()

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_get_builder_ok(self):
        self.client.force_login(self.staff)
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Module Builder')
        self.assertContains(r, 'Añadir sección')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_add_seccion(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {'action': 'add_seccion', 'titulo': 'Interesting Facts'},
            secure=True,
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            SeccionModulo.objects.filter(modulo=self.mod, titulo='Interesting Facts').exists()
        )

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_reorder_micros(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'A')
        a1 = agregar_micro(self.mod, sa, contenido='a1')
        a2 = agregar_micro(self.mod, sa, contenido='a2')
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'reorder_micros',
                'seccion_id': str(sa.id),
                'orden': f'{a2.id},{a1.id}',
            },
            secure=True,
        )
        self.assertEqual(r.status_code, 302)
        pasos = list(
            PasoModulo.objects.filter(modulo=self.mod, activo=True).order_by('orden', 'id')
        )
        self.assertEqual([p.contenido for p in pasos], ['a2', 'a1'])

    def test_get_muestra_tonos_y_drag(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'Hechos')
        agregar_micro(self.mod, sa, contenido='x')
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'eki-mb__drag-handle')
        self.assertContains(r, 'Guardar')
        self.assertContains(r, 'Module Builder')

    @override_settings(
        EKI_MODULE_BUILDER_BETA=True,
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        },
    )
    def test_post_add_micro_pdf(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'Lectura')
        pdf = SimpleUploadedFile(
            'guia_tomate.pdf',
            b'%PDF-1.4 fake pdf content for builder test',
            content_type='application/pdf',
        )
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'add_micro',
                'seccion_id': str(sa.id),
                'titulo': 'Guía PDF',
                'contenido': 'Lee el documento adjunto',
                'media_file': pdf,
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        paso = PasoModulo.objects.filter(modulo=self.mod, titulo='Guía PDF').first()
        self.assertIsNotNone(paso)
        self.assertIn('.pdf', (paso.media_url or '').lower())

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_add_micro_form_accepts_pdf(self):
        self.client.force_login(self.staff)
        agregar_seccion(self.mod, 'A')
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8')
        idx = html.find('value="add_micro"')
        self.assertGreater(idx, -1)
        chunk = html[idx:idx + 900]
        self.assertIn('application/pdf', chunk)

    @override_settings(
        EKI_MODULE_BUILDER_BETA=True,
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        },
    )
    def test_post_add_micro_texto_y_rechazo_vacio(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'A')
        r_bad = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {'action': 'add_micro', 'seccion_id': str(sa.id), 'contenido': '   '},
            secure=True,
            follow=True,
        )
        self.assertEqual(r_bad.status_code, 200)
        self.assertContains(r_bad, 'Escriba texto o suba un archivo')
        self.assertEqual(
            PasoModulo.objects.filter(modulo=self.mod, activo=True).count(), 0
        )

        r_ok = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'add_micro',
                'seccion_id': str(sa.id),
                'titulo': 'Intro',
                'contenido': 'Hola estudiante',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertContains(r_ok, 'Microcontenido añadido')
        self.assertTrue(
            PasoModulo.objects.filter(
                modulo=self.mod, contenido='Hola estudiante', activo=True
            ).exists()
        )

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_update_micro_guarda_texto_inicial(self):
        self.client.force_login(self.staff)
        from core.admin.cursos import sembrar_plantilla_modulo
        from core.module_builder import actualizar_micro

        sembrar_plantilla_modulo(self.mod)
        paso = PasoModulo.objects.filter(modulo=self.mod).order_by('orden').first()
        self.assertFalse(paso.activo)
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'update_micro',
                'paso_id': str(paso.id),
                'titulo': 'Bienvenida',
                'contenido': 'Texto guardado en builder',
                'activo': '1',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Micro guardado')
        paso.refresh_from_db()
        self.assertEqual(paso.contenido, 'Texto guardado en builder')
        self.assertTrue(paso.activo)

        with self.assertRaises(ValueError):
            actualizar_micro(paso, contenido='', activo=True)

    @override_settings(
        EKI_MODULE_BUILDER_BETA=False,
        EKI_MODULE_BUILDER_CURSOS='',
        SECURE_SSL_REDIRECT=False,
    )
    def test_builder_denied_when_flag_off(self):
        self.client.force_login(self.staff)
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 403)

    @override_settings(
        EKI_MODULE_BUILDER_BETA=False,
        EKI_MODULE_BUILDER_CURSOS='',
        SECURE_SSL_REDIRECT=False,
    )
    def test_post_preserva_builder_query(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/?builder=1',
            {'action': 'add_seccion', 'titulo': 'Sec', 'builder': '1'},
            secure=True,
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn('builder=1', r.url)
        self.assertTrue(
            SeccionModulo.objects.filter(modulo=self.mod, titulo='Sec').exists()
        )

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_save_modulo_batch(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'A')
        p1 = agregar_micro(self.mod, sa, titulo='T1', contenido='c1')
        p2 = agregar_micro(self.mod, sa, titulo='T2', contenido='c2')
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'save_modulo',
                f'paso_{p1.id}_titulo': 'Nuevo T1',
                f'paso_{p1.id}_contenido': 'Nuevo c1',
                f'paso_{p1.id}_activo': '1',
                f'paso_{p2.id}_titulo': 'T2',
                f'paso_{p2.id}_contenido': 'c2 inactivo',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Módulo guardado')
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p1.titulo, 'Nuevo T1')
        self.assertEqual(p1.contenido, 'Nuevo c1')
        self.assertTrue(p1.activo)
        self.assertEqual(p2.contenido, 'c2 inactivo')
        self.assertTrue(p2.activo)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_save_modulo_deactivate_explicit(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'A')
        p1 = agregar_micro(self.mod, sa, titulo='T1', contenido='c1')
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'save_modulo',
                f'paso_{p1.id}_titulo': 'T1',
                f'paso_{p1.id}_contenido': 'c1',
                f'paso_{p1.id}_activo': '0',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        p1.refresh_from_db()
        self.assertFalse(p1.activo)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_save_modulo_meta_titulo(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'save_modulo_meta',
                'modulo_titulo': 'Nuevo nombre módulo',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.mod.refresh_from_db()
        self.assertEqual(self.mod.titulo, 'Nuevo nombre módulo')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_rename_seccion(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'Viejo')
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'rename_seccion',
                'seccion_id': str(sa.id),
                'titulo': 'Bloque renombrado',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        sa.refresh_from_db()
        self.assertEqual(sa.titulo, 'Bloque renombrado')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_save_modulo_unificado_meta_seccion_config(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'Viejo')
        p1 = agregar_micro(self.mod, sa, titulo='T1', contenido='c1')
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'Módulo renombrado',
                f'seccion_{sa.id}_titulo': 'Sección nueva',
                'modulo_descripcion': 'Desc actualizada',
                'modulo_modo_entrega': Modulo.MODO_ENTREGA_PASOS,
                'modulo_duracion_dias': '14',
                'modulo_publicado_wa': '1',
                'modulo_examen_obligatorio': '0',
                'modulo_puntaje_minimo_aprobacion': '80',
                f'paso_{p1.id}_titulo': 'T1 ok',
                f'paso_{p1.id}_contenido': 'c1 ok',
                f'paso_{p1.id}_activo': '1',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Módulo guardado')
        self.mod.refresh_from_db()
        sa.refresh_from_db()
        p1.refresh_from_db()
        self.assertEqual(self.mod.titulo, 'Módulo renombrado')
        self.assertEqual(sa.titulo, 'Sección nueva')
        self.assertEqual(self.mod.descripcion, 'Desc actualizada')
        self.assertEqual(self.mod.modo_entrega, Modulo.MODO_ENTREGA_PASOS)
        self.assertEqual(self.mod.duracion_dias, 14)
        self.assertEqual(self.mod.puntaje_minimo_aprobacion, 80)
        self.assertEqual(p1.contenido, 'c1 ok')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_modulo_change_avanzado_stays_admin(self):
        from django.urls import reverse

        self.client.force_login(self.staff)
        url = reverse('admin:core_modulo_change', args=[self.mod.pk]) + '?avanzado=1'
        r = self.client.get(url, secure=True)
        self.assertEqual(r.status_code, 200)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_builder_muestra_general_y_avanzado(self):
        self.client.force_login(self.staff)
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Calendario y drip')
        self.assertContains(r, 'eki-mb-habilitado-fecha')
        self.assertContains(r, 'Configuración avanzada')
        self.assertContains(r, 'avanzado=1')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_modulo_change_redirects_to_builder(self):
        from django.urls import reverse

        self.client.force_login(self.staff)
        url = reverse('admin:core_modulo_change', args=[self.mod.pk])
        r = self.client.get(url, secure=True)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/module-builder/', r.url)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_modulo_change_legacy_stays_admin(self):
        from django.urls import reverse

        self.client.force_login(self.staff)
        url = reverse('admin:core_modulo_change', args=[self.mod.pk]) + '?legacy=1'
        r = self.client.get(url, secure=True)
        self.assertEqual(r.status_code, 200)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_post_duplicate_micro(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'A')
        p = agregar_micro(self.mod, sa, titulo='Original', contenido='texto base')
        n_before = PasoModulo.objects.filter(modulo=self.mod).count()
        r = self.client.post(
            f'/admin/module-builder/{self.mod.id}/',
            {
                'action': 'duplicate_micro',
                'paso_id': str(p.id),
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'duplicado')
        self.assertEqual(PasoModulo.objects.filter(modulo=self.mod).count(), n_before + 1)
        copia = PasoModulo.objects.filter(modulo=self.mod).exclude(pk=p.pk).get()
        self.assertFalse(copia.activo)
        self.assertEqual(copia.contenido, 'texto base')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_builder_panel_dom_contract(self):
        """QA: panel lateral + JS v16 — clic debe poder mostrar contenido del paso."""
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'Hechos')
        p = agregar_micro(self.mod, sa, titulo='Intro', contenido='Texto visible QA')
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8')
        self.assertIn('eki-mb-panel-edits', html)
        self.assertIn('data-paso-select="' + str(p.id) + '"', html)
        self.assertIn('data-paso-edit="' + str(p.id) + '"', html)
        self.assertIn('name="paso_' + str(p.id) + '_contenido"', html)
        self.assertIn('Texto visible QA', html)
        self.assertIn('module_builder.js?v=23', html)
        self.assertIn('eki-mb__row-preview', html)
        self.assertIn('eki-mb__activo-hint', html)
        self.assertIn('css/module_builder.css?v=23', html)
        self.assertIn('eki-mb-save-trigger', html)
        self.assertIn('Calendario y drip', html)
        self.assertIn('avanzado=1', html)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_builder_v8_sticky_save_and_problems(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod, 'Hechos')
        agregar_micro(
            self.mod,
            sa,
            titulo='Clip',
            contenido='x',
            media_url='https://x/v.mp4',
        )
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'eki-mb-save-all')
        self.assertContains(r, 'eki-mb-save-top')
        self.assertContains(r, 'Guardar este micro')
        self.assertContains(r, 'eki-mb-sticky')
        self.assertContains(r, 'replace_media')
        self.assertContains(r, 'eki-mb-layout')
        self.assertContains(r, 'eki-mb-panel')
        self.assertContains(r, 'duplicate_micro')
        self.assertContains(r, 'eki-mb-wa-preview')


class ModuleBuilderAdversarialQATests(TestCase):
    """QA: intentos de romper guardado unificado y permisos."""

    def setUp(self):
        self.curso_a = Curso.objects.create(nombre='Curso A')
        self.curso_b = Curso.objects.create(nombre='Curso B')
        self.mod_a = Modulo.objects.create(
            curso=self.curso_a, numero=1, titulo='Mod A', descripcion='d', contenido='c',
        )
        self.mod_b = Modulo.objects.create(
            curso=self.curso_b, numero=1, titulo='Mod B', descripcion='d', contenido='c',
        )
        self.staff = User.objects.create_user(
            username='mb_qa', password='x', is_staff=True, is_superuser=True,
        )
        self.client = Client()

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_no_cross_modulo_paso_update(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod_a, 'A')
        sb = agregar_seccion(self.mod_b, 'B')
        pa = agregar_micro(self.mod_a, sa, titulo='A1', contenido='texto A')
        pb = agregar_micro(self.mod_b, sb, titulo='B1', contenido='texto B')
        r = self.client.post(
            f'/admin/module-builder/{self.mod_a.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'Mod A',
                f'paso_{pb.id}_titulo': 'HACKED',
                f'paso_{pb.id}_contenido': 'contenido ajeno',
                f'paso_{pb.id}_activo': '0',
                f'paso_{pa.id}_titulo': 'A1',
                f'paso_{pa.id}_contenido': 'texto A',
                f'paso_{pa.id}_activo': '1',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        pb.refresh_from_db()
        pa.refresh_from_db()
        self.assertEqual(pb.titulo, 'B1')
        self.assertEqual(pb.contenido, 'texto B')
        self.assertTrue(pb.activo)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_rechaza_titulo_modulo_vacio(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            f'/admin/module-builder/{self.mod_a.id}/',
            {'action': 'save_modulo', 'modulo_titulo': '   '},
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'no puede quedar vacío')
        self.mod_a.refresh_from_db()
        self.assertEqual(self.mod_a.titulo, 'Mod A')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_save_sin_activo_no_desactiva_otros_pasos(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod_a, 'A')
        p1 = agregar_micro(self.mod_a, sa, titulo='T1', contenido='c1')
        p2 = agregar_micro(self.mod_a, sa, titulo='T2', contenido='c2')
        r = self.client.post(
            f'/admin/module-builder/{self.mod_a.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'Mod A',
                f'paso_{p1.id}_titulo': 'T1 edit',
                f'paso_{p1.id}_contenido': 'c1 edit',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(p1.activo)
        self.assertTrue(p2.activo)
        self.assertEqual(p1.contenido, 'c1 edit')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_publicado_wa_explicito_off(self):
        self.client.force_login(self.staff)
        self.mod_a.publicado_wa = True
        self.mod_a.save(update_fields=['publicado_wa'])
        r = self.client.post(
            f'/admin/module-builder/{self.mod_a.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'Mod A',
                'modulo_publicado_wa': '0',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.mod_a.refresh_from_db()
        self.assertFalse(self.mod_a.publicado_wa)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_non_staff_forbidden(self):
        user = User.objects.create_user(username='norm', password='x', is_staff=False)
        self.client.force_login(user)
        r = self.client.get(f'/admin/module-builder/{self.mod_a.id}/', secure=True)
        self.assertIn(r.status_code, (302, 403))

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_replace_media_rechaza_paso_ajeno(self):
        self.client.force_login(self.staff)
        sa = agregar_seccion(self.mod_a, 'A')
        sb = agregar_seccion(self.mod_b, 'B')
        pb = agregar_micro(self.mod_b, sb, titulo='B1', contenido='texto B')
        from django.core.files.uploadedfile import SimpleUploadedFile

        pdf = SimpleUploadedFile('x.pdf', b'%PDF-1.4', content_type='application/pdf')
        r = self.client.post(
            f'/admin/module-builder/{self.mod_a.id}/',
            {
                'action': 'replace_media',
                'paso_id': str(pb.id),
                'media_file': pdf,
            },
            secure=True,
        )
        self.assertEqual(r.status_code, 404)
        pb.refresh_from_db()
        self.assertFalse((pb.media_url or '').strip())


class ModuleBuilderSeccionTituloTests(TestCase):
    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_save_modulo_no_pisa_bloque_default(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='Mi módulo', descripcion='d', contenido='c',
        )
        sec = agregar_seccion(mod, 'Bloque 1')
        staff = User.objects.create_user(
            username='mb_sec', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {'action': 'save_modulo', 'modulo_titulo': 'Mi módulo'},
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        sec.refresh_from_db()
        self.assertEqual(sec.titulo, 'Bloque 1')

    @override_settings(
        EKI_MODULE_BUILDER_BETA=True,
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        },
    )
    def test_add_micro_persiste_titulo_seccion(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='Mi módulo', descripcion='d', contenido='c',
        )
        sec = agregar_seccion(mod, 'Viejo')
        staff = User.objects.create_user(
            username='mb_up', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        from django.core.files.uploadedfile import SimpleUploadedFile

        pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'add_micro',
                'seccion_id': str(sec.id),
                'contenido': 'Leé el PDF',
                f'seccion_{sec.id}_titulo': 'Nombre custom sección',
                'modulo_titulo': 'Mi módulo',
                'media_file': pdf,
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        sec.refresh_from_db()
        self.assertEqual(sec.titulo, 'Nombre custom sección')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_add_micro_no_pisa_general_sin_persist_flag(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='vieja', contenido='c',
        )
        mod.publicado_wa = False
        mod.habilitado_desde = None
        mod.save(update_fields=['publicado_wa'])
        sec = agregar_seccion(mod, 'S')
        p = agregar_micro(mod, sec, titulo='T', contenido='original')
        staff = User.objects.create_user(
            username='mb_full', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'add_micro',
                'seccion_id': str(sec.id),
                'contenido': 'nuevo micro',
                'modulo_descripcion': 'desc nueva',
                'modulo_publicado_wa': '1',
                'modulo_habilitado_desde': '2030-01-15T10:00',
                f'paso_{p.id}_titulo': 'T edit',
                f'paso_{p.id}_contenido': 'texto editado sin guardar',
                f'paso_{p.id}_activo': '1',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(mod.descripcion, 'vieja')
        self.assertFalse(mod.publicado_wa)
        self.assertIsNone(mod.habilitado_desde)
        self.assertEqual(p.contenido, 'texto editado sin guardar')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_add_micro_persiste_general_con_persist_flag(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='vieja', contenido='c',
        )
        mod.publicado_wa = False
        mod.save(update_fields=['publicado_wa'])
        sec = agregar_seccion(mod, 'S')
        staff = User.objects.create_user(
            username='mb_pg', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'add_micro',
                'seccion_id': str(sec.id),
                'contenido': 'nuevo micro',
                'persist_general': '1',
                'modulo_descripcion': 'desc nueva',
                'modulo_publicado_wa': '1',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        self.assertEqual(mod.descripcion, 'desc nueva')
        self.assertTrue(mod.publicado_wa)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_save_modulo_persiste_habilitado_desde(self):
        from django.utils import timezone

        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='c',
        )
        staff = User.objects.create_user(
            username='mb_cal', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'M',
                'modulo_habilitado_desde': '2031-06-10T14:30',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        self.assertIsNotNone(mod.habilitado_desde)
        local = timezone.localtime(mod.habilitado_desde)
        self.assertEqual(local.strftime('%Y-%m-%dT%H:%M'), '2031-06-10T14:30')

        r2 = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'M',
                'modulo_habilitado_desde': '',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r2.status_code, 200)
        mod.refresh_from_db()
        self.assertIsNone(mod.habilitado_desde)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_save_modulo_ajax_json_ok(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='c',
        )
        staff = User.objects.create_user(
            username='mb_ajax', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'save_modulo',
                'ajax': '1',
                'modulo_titulo': 'M',
                'modulo_habilitado_desde': '2032-03-20T09:15',
            },
            secure=True,
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get('ok'))
        partes_txt = ' '.join(data.get('partes') or [])
        self.assertIn('calendario', partes_txt)
        self.assertEqual(data.get('habilitado_desde'), '2032-03-20T09:15')
        mod.refresh_from_db()
        self.assertIsNotNone(mod.habilitado_desde)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_save_modulo_post_then_get_muestra_drip(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='c',
        )
        staff = User.objects.create_user(
            username='mb_drip_get', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'M',
                'modulo_habilitado_desde': '2027-08-01T16:45',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        self.assertIsNotNone(mod.habilitado_desde)
        self.assertContains(r, 'Drip guardado')
        self.assertContains(r, '2027-08-01')
        self.assertContains(r, '16:45')
        self.assertContains(r, 'value="2027-08-01T16:45"', html=False)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_save_modulo_rechaza_fecha_drip_invalida(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='c',
        )
        staff = User.objects.create_user(
            username='mb_drip_bad', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'save_modulo',
                'ajax': '1',
                'modulo_titulo': 'M',
                'modulo_habilitado_desde': 'no-es-fecha',
            },
            secure=True,
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(r.status_code, 400)
        data = r.json()
        self.assertFalse(data.get('ok'))
        mod.refresh_from_db()
        self.assertIsNone(mod.habilitado_desde)

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_save_modulo_sin_campo_drip_no_borra_habilitado_desde(self):
        from django.utils import timezone

        curso = Curso.objects.create(nombre='C')
        drip = timezone.make_aware(
            timezone.datetime(2029, 5, 1, 8, 30),
            timezone.get_current_timezone(),
        )
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='c',
            habilitado_desde=drip,
        )
        staff = User.objects.create_user(
            username='mb_drip_keep', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'save_modulo',
                'modulo_titulo': 'M renombrado',
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        self.assertEqual(mod.titulo, 'M renombrado')
        self.assertIsNotNone(mod.habilitado_desde)
        self.assertEqual(
            timezone.localtime(mod.habilitado_desde).strftime('%Y-%m-%dT%H:%M'),
            '2029-05-01T08:30',
        )

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_reorder_micros_ajax_json(self):
        staff = User.objects.create_user(
            username='mb_reord', password='x', is_staff=True, is_superuser=True,
        )
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='c',
        )
        client = Client()
        client.force_login(staff)
        sa = agregar_seccion(mod, 'A')
        a1 = agregar_micro(mod, sa, contenido='a1')
        a2 = agregar_micro(mod, sa, contenido='a2')
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'reorder_micros',
                'ajax': '1',
                'seccion_id': str(sa.id),
                'orden': f'{a2.id},{a1.id}',
            },
            secure=True,
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data['orden'][str(a2.id)], 1)
        self.assertEqual(data['orden'][str(a1.id)], 2)

    @override_settings(
        EKI_MODULE_BUILDER_BETA=True,
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        },
    )
    def test_add_micro_no_renombra_modulo_ni_seccion_default(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='Nombre real módulo', descripcion='d', contenido='c',
        )
        sec = agregar_seccion(mod, 'Bloque 1')
        staff = User.objects.create_user(
            username='mb_norename', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        from django.core.files.uploadedfile import SimpleUploadedFile

        pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'add_micro',
                'seccion_id': str(sec.id),
                'contenido': 'Leé el PDF',
                f'seccion_{sec.id}_titulo': 'Bloque 1',
                'modulo_titulo': 'Título distinto en POST',
                'media_file': pdf,
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        sec.refresh_from_db()
        self.assertEqual(mod.titulo, 'Nombre real módulo')
        self.assertEqual(sec.titulo, 'Bloque 1')

    @override_settings(
        EKI_MODULE_BUILDER_BETA=True,
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        },
    )
    def test_replace_media_solo_toca_paso_subido(self):
        curso = Curso.objects.create(nombre='C')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='Módulo intacto', descripcion='d', contenido='c',
        )
        sec = agregar_seccion(mod, 'Sección intacta')
        p1 = agregar_micro(mod, sec, titulo='Paso uno', contenido='c1')
        p2 = agregar_micro(mod, sec, titulo='Paso dos', contenido='c2')
        staff = User.objects.create_user(
            username='mb_rep', password='x', is_staff=True, is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        from django.core.files.uploadedfile import SimpleUploadedFile

        pdf = SimpleUploadedFile('x.pdf', b'%PDF-1.4', content_type='application/pdf')
        r = client.post(
            f'/admin/module-builder/{mod.id}/',
            {
                'action': 'replace_media',
                'paso_id': str(p1.id),
                'modulo_titulo': 'Otro módulo',
                f'seccion_{sec.id}_titulo': 'Otra sección',
                f'paso_{p1.id}_titulo': 'Paso uno edit',
                f'paso_{p1.id}_contenido': 'c1 edit',
                f'paso_{p2.id}_titulo': 'Paso dos MAL',
                f'paso_{p2.id}_contenido': 'c2 MAL',
                'media_file': pdf,
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        mod.refresh_from_db()
        sec.refresh_from_db()
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(mod.titulo, 'Módulo intacto')
        self.assertEqual(sec.titulo, 'Sección intacta')
        self.assertEqual(p1.titulo, 'Paso uno edit')
        self.assertEqual(p1.contenido, 'c1 edit')
        self.assertTrue((p1.media_url or '').strip())
        self.assertEqual(p2.titulo, 'Paso dos')
        self.assertEqual(p2.contenido, 'c2')


class ModuleBuilderJsHealthTests(TestCase):
    """Fase 4 gobernanza: gate JS parse antes de deploy (complementa eb_precheck)."""

    def test_module_builder_js_syntax_valid(self):
        import shutil
        import subprocess
        from pathlib import Path

        js_path = Path(__file__).resolve().parents[1] / 'static' / 'admin' / 'js' / 'module_builder.js'
        self.assertTrue(js_path.is_file(), f'Falta {js_path}')
        node = shutil.which('node')
        if not node:
            self.skipTest('node no está en PATH')
        proc = subprocess.run(
            [node, '--check', str(js_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f'module_builder.js syntax error:\n{proc.stderr or proc.stdout}',
        )
