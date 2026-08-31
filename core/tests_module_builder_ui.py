# -*- coding: utf-8 -*-
"""Tests Module Builder UI/logic (sin Twilio)."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from core.models import Curso, Modulo, PasoModulo, SeccionModulo
from core.module_builder import (
    agregar_micro,
    agregar_seccion,
    arbol_modulo,
    diagnostico_estructura,
    media_preview_kind,
    module_builder_habilitado,
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
        self.assertFalse(p2.activo)

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
