# -*- coding: utf-8 -*-
"""Publicar un módulo: el GET muestra el checklist y el POST es el que escribe."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from core.models import Curso, Modulo, PasoModulo, SeccionModulo

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class PublicarConfirmacionTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Curso publicar', descripcion='d')
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M',
            descripcion='d',
            contenido='',
            publicado_wa=False,
        )
        sec = SeccionModulo.objects.create(modulo=self.mod, orden=1, titulo='S')
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sec,
            orden=1,
            titulo='P',
            contenido='Texto',
            activo=True,
        )
        staff = User.objects.create_superuser('pub_conf', 'a@b.c', 'x')
        self.client = Client()
        self.client.force_login(staff)
        self.url = f'/admin/core/modulo/{self.mod.pk}/publicar/'

    def test_get_muestra_el_checklist_y_no_escribe(self):
        r = self.client.get(self.url, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Publicar en WhatsApp')
        self.assertContains(r, 'csrfmiddlewaretoken')
        self.mod.refresh_from_db()
        self.assertFalse(self.mod.publicado_wa)

    def test_post_publica(self):
        r = self.client.post(self.url, secure=True)
        self.assertEqual(r.status_code, 302)
        self.mod.refresh_from_db()
        self.assertTrue(self.mod.publicado_wa)
