"""Listados admin: orden y columnas operativas (Cliente / Estudiante / Módulo)."""

from django.contrib.admin.sites import site
from django.test import SimpleTestCase

from core.admin.clientes import ClienteAdmin
from core.admin.cursos import ModuloAdmin
from core.admin.estudiantes import EstudianteAdmin
from core.models import Cliente, Estudiante, Modulo


class AdminListadosOrdenTests(SimpleTestCase):
    def test_cliente_orden_y_columnas(self):
        adm = ClienteAdmin(Cliente, site)
        self.assertEqual(adm.ordering, ('nombre',))
        self.assertIn('nombre', adm.list_display)
        self.assertIn('activo', adm.list_display)
        self.assertNotIn('fecha_registro', adm.list_display)
        self.assertNotIn('numero_meta_badge', adm.list_display)

    def test_estudiante_orden_y_columnas(self):
        adm = EstudianteAdmin(Estudiante, site)
        self.assertEqual(adm.ordering, ('cliente__nombre', 'nombre'))
        self.assertEqual(adm.list_filter[0], 'cliente')
        self.assertIn('cliente_nombre', adm.list_display)
        self.assertNotIn('municipio', adm.list_display)
        self.assertNotIn('fecha_registro', adm.list_display)
        self.assertEqual(adm.list_select_related, ('cliente',))

    def test_modulo_orden_y_columnas(self):
        adm = ModuloAdmin(Modulo, site)
        self.assertEqual(adm.ordering, ['curso__nombre', 'numero'])
        self.assertEqual(adm.list_filter[0], 'curso')
        self.assertNotIn('contenido_preview', adm.list_display)
        self.assertNotIn('tiene_pregunta', adm.list_display)
        self.assertIn('curso', adm.list_select_related)
