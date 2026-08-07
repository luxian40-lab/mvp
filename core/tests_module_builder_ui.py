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
        self.assertContains(r, 'Cómo entrar')
        self.assertContains(r, 'palette')

    @override_settings(EKI_MODULE_BUILDER_BETA=False, SECURE_SSL_REDIRECT=False)
    def test_builder_denied_when_flag_off(self):
        self.client.force_login(self.staff)
        r = self.client.get(f'/admin/module-builder/{self.mod.id}/', secure=True)
        self.assertEqual(r.status_code, 403)
