# -*- coding: utf-8 -*-
"""Humo del constructor oficial en el navegador. No corre en la suite normal.

  $env:EKI_PLAYWRIGHT='1'
  $env:PYTHONUTF8='1'
  python manage.py test core.tests_browser.test_constructor_humo --keepdb
"""
import os
import unittest

from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings

from core.models import Curso

User = get_user_model()


@unittest.skipUnless(
    os.environ.get('EKI_PLAYWRIGHT') == '1',
    'Humo de navegador. Definir EKI_PLAYWRIGHT=1 y tener Chromium de Playwright.',
)
@override_settings(
    EKI_CONSTRUCTOR_CURSOS=True,
    EKI_CURSO_VERSIONES=False,
    SECURE_SSL_REDIRECT=False,
    DEBUG=True,
)
class ConstructorHumoTests(LiveServerTestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='[PRUEBA] Constructor humo', descripcion='d')
        User.objects.create_superuser('ctor_humo', 'ctor@example.com', 'ctor-pass-local')

    def test_crear_modulo_y_mensaje(self):
        from playwright.sync_api import sync_playwright

        url = self.live_server_url + f'/admin/core/curso/{self.curso.pk}/constructor/'
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.goto(self.live_server_url + '/admin/login/?next=/admin/')
            page.fill('#id_username', 'ctor_humo')
            page.fill('#id_password', 'ctor-pass-local')
            page.locator('#login-form').locator('input[type="submit"], button[type="submit"]').click()
            page.wait_for_load_state('networkidle')
            page.goto(url)
            page.wait_for_selector('[data-eki-ctor="1"]')
            page.locator('[data-eki-ctor-accion="crear_modulo"] input[name="titulo"]').fill('Intro')
            page.locator('[data-eki-ctor-accion="crear_modulo"] input[type="submit"]').click()
            page.wait_for_selector('[data-eki-ctor-ok]')
            page.wait_for_selector('[data-eki-ctor-modulo]')
            page.locator('[data-eki-ctor-accion="crear_mensaje"] textarea[name="contenido"]').fill(
                'Hola piloto'
            )
            page.locator('[data-eki-ctor-accion="crear_mensaje"] input[type="submit"]').click()
            page.wait_for_selector('[data-eki-ctor-mensaje]')
            self.assertIn('Hola piloto', page.content())
            browser.close()
