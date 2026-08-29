"""Listados admin: orden y columnas operativas (Cliente / Estudiante / Curso / Módulo)."""

from django.contrib.admin.sites import site
from django.test import SimpleTestCase

from core.admin.clientes import ClienteAdmin
from core.admin.cursos import CursoAdmin, ModuloAdmin
from core.admin.estudiantes import EstudianteAdmin
from core.models import Cliente, Curso, Estudiante, Modulo


class AdminListadosOrdenTests(SimpleTestCase):
    def test_cliente_orden_y_columnas(self):
        adm = ClienteAdmin(Cliente, site)
        self.assertEqual(adm.ordering, ('nombre',))
        self.assertIn('nombre', adm.list_display)
        self.assertIn('activo', adm.list_display)
        self.assertEqual(len(adm.list_display), 6)
        self.assertNotIn('mapa_cobertura_rapido', adm.list_display)
        self.assertTrue(adm.compressed_fields)
        self.assertNotIn('fecha_registro', adm.list_display)
        self.assertNotIn('numero_meta_badge', adm.list_display)

    def test_cliente_fieldsets_avanzados_colapsados(self):
        adm = ClienteAdmin(Cliente, site)
        by_title = {fs[0]: fs[1] for fs in adm.fieldsets}
        self.assertNotIn('classes', by_title['Datos y logo'])
        self.assertIn('logo_url', by_title['Datos y logo']['fields'])
        self.assertIn('mapa_cobertura_rapido', by_title['Datos y logo']['fields'])
        for title in (
            'Portal y acceso',
            'Aula Aprende',
            'WhatsApp y legal',
            'Certificados y drip',
            'Ventanas por fechas',
            'Nat e IA',
        ):
            self.assertIn('tab', by_title[title].get('classes', ()))
        self.assertNotIn('twilio_auth_token', by_title['Datos y logo']['fields'])
        self.assertIn('twilio_auth_token', by_title['WhatsApp y legal']['fields'])

    def test_cliente_logo_thumb_usa_clase_css(self):
        adm = ClienteAdmin(Cliente, site)
        org = Cliente(nombre='Cenipalma', logo_url='')
        html = str(adm.logo_thumb(org))
        self.assertIn('eki-id-thumb-list', html)
        self.assertIn('C', html)
        org.logo_url = 'https://example.com/l.png'
        html = str(adm.logo_thumb(org))
        self.assertIn('eki-id-thumb-list', html)
        self.assertIn('https://example.com/l.png', html)

    def test_estudiante_orden_y_columnas(self):
        adm = EstudianteAdmin(Estudiante, site)
        self.assertEqual(adm.ordering, ('cliente__nombre', 'nombre'))
        self.assertEqual(adm.list_filter[0], 'cliente')
        self.assertIn('cliente_nombre', adm.list_display)
        self.assertIn('conversacion_link', adm.list_display)
        self.assertNotIn('cursos_inscritos', adm.list_display)
        self.assertEqual(len(adm.list_display), 6)
        self.assertNotIn('municipio', adm.list_display)
        self.assertNotIn('fecha_registro', adm.list_display)
        self.assertEqual(adm.list_select_related, ('cliente',))
        self.assertEqual(adm.actions[0], 'asignar_a_grupo_accion')

    def test_curso_listado_compacto(self):
        adm = CursoAdmin(Curso, site)
        self.assertLessEqual(len(adm.list_display), 6)
        self.assertIn('nombre', adm.list_display)
        self.assertIn('cliente_nombre', adm.list_display)
        self.assertIn('activo', adm.list_display)
        self.assertNotIn('docs_rag_count', adm.list_display)
        self.assertNotIn('tiene_formulario_gei', adm.list_display)
        self.assertNotIn('usar_agentes_ia', adm.list_display)

    def test_modulo_orden_y_columnas(self):
        adm = ModuloAdmin(Modulo, site)
        self.assertEqual(adm.ordering, ['curso__nombre', 'numero'])
        self.assertEqual(adm.list_filter[0], 'curso__cliente')
        self.assertLessEqual(len(adm.list_display), 6)
        self.assertIn('org_nombre', adm.list_display)
        self.assertIn('module_builder_link', adm.list_display)
        self.assertNotIn('contenido_preview', adm.list_display)
        self.assertNotIn('tiene_pregunta', adm.list_display)
        self.assertNotIn('curso', adm.list_filter)
        self.assertEqual(
            [cls.__name__ for cls in adm.inlines],
            ['SeccionModuloInline', 'PasoModuloInline'],
        )
        self.assertIn('curso', adm.list_select_related)
        self.assertIn('curso__cliente', adm.list_select_related)

    def test_campana_listado_logo_y_seis_columnas(self):
        from core.admin.campanas import CampanaAdmin
        from core.models import Campana

        adm = CampanaAdmin(Campana, site)
        self.assertLessEqual(len(adm.list_display), 6)
        self.assertIn('logo_thumb', adm.list_display)
        self.assertIn('nombre', adm.list_display)
