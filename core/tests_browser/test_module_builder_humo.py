# -*- coding: utf-8 -*-
"""Humo del Module Builder en el navegador. No corre en la suite normal.

Dependencia solo de desarrollo (requirements-dev.txt). No entra en Elastic Beanstalk.

  $env:EKI_PLAYWRIGHT='1'
  $env:PYTHONUTF8='1'
  python manage.py test core.tests_browser.test_module_builder_humo --keepdb
"""
import os
import unittest

from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings

from core.models import Curso, Modulo
from core.module_builder import agregar_micro, agregar_seccion

User = get_user_model()


@unittest.skipUnless(
    os.environ.get('EKI_PLAYWRIGHT') == '1',
    'Humo de navegador. Definir EKI_PLAYWRIGHT=1 y tener Chromium de Playwright.',
)
@override_settings(
    EKI_MODULE_BUILDER_UI_V2=True,
    EKI_MODULE_BUILDER_BETA=True,
    SECURE_SSL_REDIRECT=False,
    DEBUG=True,
)
class ModuleBuilderHumoTests(LiveServerTestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='Humo', descripcion='d')
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Modulo humo',
            descripcion='d',
            contenido='c',
            publicado_wa=False,
        )
        sec = agregar_seccion(self.mod, 'Seccion uno')
        self.primero = agregar_micro(self.mod, sec, titulo='Primero', contenido='hola')
        self.segundo = agregar_micro(self.mod, sec, titulo='Segundo', contenido='adios')
        User.objects.create_superuser('humo', 'humo@example.com', 'humo-pass-local')

    def test_cuatro_pasos(self):
        from playwright.sync_api import sync_playwright

        url = self.live_server_url + f'/admin/module-builder/{self.mod.pk}/'
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.goto(self.live_server_url + '/admin/login/?next=/admin/')
            page.fill('#id_username', 'humo')
            page.fill('#id_password', 'humo-pass-local')
            page.locator('#login-form').locator('input[type="submit"], button[type="submit"]').click()
            page.wait_for_load_state('networkidle')
            page.goto(url)
            page.wait_for_load_state('domcontentloaded')
            # Esta vista no arma el sidebar: el HTML trae la barra de Unfold vacía.
            # «Módulos» resaltado se comprueba en el listado, no en esta página.
            page.locator('[data-eki-mb-pestana="contenido"]').wait_for()
            page.locator('[data-eki-mb-pestana="general"]').wait_for()
            page.locator('[data-eki-mb-pestana="calendario"]').wait_for()

            page.locator('input[name^="seccion_"][name$="_titulo"]').first.fill('Seccion renombrada')
            page.locator('#eki-mb-save-top').click()
            page.get_by_text('Guardado', exact=False).first.wait_for()
            page.locator('button', has_text='Agregar mensaje').first.click()
            page.wait_for_load_state('networkidle')
            self.assertIn('Texto', page.content())

            self.assertGreaterEqual(page.locator('[aria-label="Subir mensaje"]').count(), 2)
            self.assertGreaterEqual(page.locator('[aria-label="Bajar mensaje"]').count(), 2)

            href = page.locator('#eki-mb-publicar').get_attribute('href')
            self.assertIn(f'/admin/core/modulo/{self.mod.pk}/publicar/confirmar/', href or '')
            self.assertNotIn('/publicar/', page.url)

            destino = os.path.join(os.environ.get('TEMP', '.'), 'eki_mb_claro.png')
            page.screenshot(path=destino, full_page=True)
            page.evaluate("document.documentElement.setAttribute('data-eki-tone', 'noche')")
            page.screenshot(
                path=os.path.join(os.environ.get('TEMP', '.'), 'eki_mb_oscuro.png'),
                full_page=True,
            )
            browser.close()
