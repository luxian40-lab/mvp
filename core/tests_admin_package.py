"""Verifica que el paquete core.admin carga y registra admins tras el split."""

from django.contrib import admin
from django.test import SimpleTestCase

from core.admin import (
    ClienteAdmin,
    CursoAdmin,
    EstudianteAdmin,
    PasoModuloInline,
    _extension_archivo_comercial_ok,
)
from core.models import Cliente, Curso, Estudiante


class AdminPackageTests(SimpleTestCase):
    def test_reexports_para_proxy_apps(self):
        self.assertTrue(callable(_extension_archivo_comercial_ok))
        self.assertTrue(hasattr(PasoModuloInline, 'model'))

    def test_modelos_registrados_en_site(self):
        for model, admin_cls in (
            (Cliente, ClienteAdmin),
            (Estudiante, EstudianteAdmin),
            (Curso, CursoAdmin),
        ):
            registered = admin.site._registry.get(model)
            self.assertIsNotNone(registered, msg=f'{model.__name__} no registrado')
            self.assertIsInstance(registered, admin_cls)
