# -*- coding: utf-8 -*-
"""Tests asistente Curso nuevo — puerta única de alta."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Curso
from core.modulo_authoring_mode import MODO_CLASE, SESSION_KEY
from mvp_project.unfold_admin import UNFOLD


User = get_user_model()


def _todos_los_links_nav() -> list[tuple[str, str]]:
    hits = []
    for item in UNFOLD.get('SITE_DROPDOWN') or []:
        hits.append(('dropdown', str(item.get('link') or '')))
    for group in (UNFOLD.get('SIDEBAR') or {}).get('navigation') or []:
        for item in group.get('items') or []:
            hits.append((str(group.get('title') or ''), str(item.get('link') or '')))
    return hits


@override_settings(
    EKI_MODULE_BUILDER_BETA=True,
    EKI_MODULE_BUILDER_CURSOS='*',
    SECURE_SSL_REDIRECT=False,
)
class CursoNuevoWizardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='cn_staff', password='x', is_staff=True, is_superuser=True,
        )
        self.client = Client()

    def test_get_wizard_es_puerta_unica(self):
        self.client.force_login(self.staff)
        r = self.client.get('/admin/curso-nuevo/', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curso nuevo')
        self.assertContains(r, 'Crear y abrir el primer módulo')
        self.assertNotContains(r, 'Crear y abrir Builder')
        self.assertNotContains(r, 'Añadir curso clásico')

    def test_post_crea_curso_y_abre_modulo_modo_clase(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            '/admin/curso-nuevo/',
            {
                'nombre': 'Curso Wizard QA',
                'descripcion': 'desc',
                'cliente_id': '',
                'modo_aula': Curso.MODO_AULA_MODULOS,
                'n_modulos': '2',
            },
            secure=True,
        )
        self.assertEqual(r.status_code, 302)
        curso = Curso.objects.get(nombre='Curso Wizard QA')
        mods = list(curso.modulos.order_by('numero'))
        self.assertEqual(len(mods), 2)
        self.assertFalse(mods[0].publicado_wa)
        self.assertFalse(mods[1].publicado_wa)
        esperado = reverse('admin:core_modulo_change', args=[mods[0].pk]) + '?modo=clase'
        self.assertEqual(r.url, esperado)
        self.assertNotIn('module-builder', r.url)
        self.assertTrue(mods[0].secciones.exists())
        modos = self.client.session.get(SESSION_KEY) or {}
        self.assertEqual(modos.get(str(mods[0].pk)), MODO_CLASE)

    def test_sidebar_un_solo_curso_nuevo_y_sin_ia(self):
        links = _todos_los_links_nav()
        nuevos = [item for item in links if '/admin/curso-nuevo/' in item[1]]
        self.assertEqual(len(nuevos), 1, nuevos)
        self.assertEqual(nuevos[0][0], 'dropdown')
        ia = [item for item in links if 'crear-curso-ia' in item[1]]
        self.assertEqual(ia, [])
