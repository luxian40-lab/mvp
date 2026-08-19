# -*- coding: utf-8 -*-
"""Tests asistente Curso nuevo."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Curso, Modulo


User = get_user_model()


@override_settings(
    EKI_MODULE_BUILDER_BETA=False,
    EKI_MODULE_BUILDER_CURSOS='*',
    SECURE_SSL_REDIRECT=False,
)
class CursoNuevoWizardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='cn_staff', password='x', is_staff=True, is_superuser=True,
        )
        self.client = Client()

    def test_get_wizard(self):
        self.client.force_login(self.staff)
        r = self.client.get('/admin/curso-nuevo/', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curso nuevo')
        self.assertContains(r, 'Crear y abrir Builder')

    def test_post_crea_curso_modulos_y_abre_builder(self):
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
        self.assertEqual(
            r.url,
            reverse('admin_module_builder', kwargs={'modulo_id': mods[0].pk}),
        )
        self.assertTrue(mods[0].secciones.exists())
