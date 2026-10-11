"""Admin de Cliente v2: cobertura de campos. El interruptor sigue apagado por defecto."""
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from core.admin.cliente_v2_flag import admin_clientes_v2_activo
from core.admin.clientes import ClienteAdmin
from core.admin.clientes_v2 import ClienteAdminV2
from core.models import Cliente


# Campos que el formulario no trata como input. El motivo va escrito aquí.
EXCLUIDOS_COBERTURA = {
    'id': 'Clave primaria. No es un campo del formulario.',
    'fecha_registro': 'auto_now_add. Se muestra solo lectura en Datos y no es un input.',
    'usar_gamificacion': (
        'Lo escribe Cliente.save desde modo_gamificacion. Sigue visible en solo lectura.'
    ),
    'peso_gamificacion_reto': (
        'El formulario anterior lo excluye. Solo lectura en Enseñanza para no pisarlo al guardar.'
    ),
    'peso_gamificacion_abierta': (
        'El formulario anterior lo excluye. Solo lectura en Enseñanza para no pisarlo al guardar.'
    ),
    'portal_productos': (
        'No es input. Lo escriben las casillas portal_modulos con el mismo texto separado por comas.'
    ),
}


def _nombres_fieldset(admin_obj, request, obj):
    nombres = set()
    for _titulo, opts in admin_obj.get_fieldsets(request, obj):
        for campo in opts.get('fields') or ():
            if isinstance(campo, (list, tuple)):
                nombres.update(campo)
            else:
                nombres.add(campo)
    return nombres


@override_settings(
    ADMIN_CLIENTES_V2=True,
    SECURE_SSL_REDIRECT=False,
)
class CoberturaCamposClienteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('cov_cli', 'c@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Cobertura',
            contacto_principal='Ana',
            email='cobertura@test.com',
            telefono='573009990001',
        )
        self.request = RequestFactory().get('/admin/core/cliente/')
        self.request.user = self.user
        self.viejo = ClienteAdmin(Cliente, AdminSite())
        self.nuevo = ClienteAdminV2(Cliente, AdminSite())

    def test_cada_campo_editable_esta_en_la_ficha_nueva(self):
        for motivo in EXCLUIDOS_COBERTURA.values():
            self.assertTrue(motivo.strip())
        nuevos = _nombres_fieldset(self.nuevo, self.request, self.cliente)
        viejos = _nombres_fieldset(self.viejo, self.request, self.cliente)
        faltan_viejos = sorted(viejos - nuevos)
        self.assertEqual(faltan_viejos, [], f'El formulario nuevo perdió: {faltan_viejos}')

        faltan = []
        for field in Cliente._meta.fields:
            if not field.editable or field.name in EXCLUIDOS_COBERTURA:
                continue
            if field.name not in nuevos:
                faltan.append(field.name)
        self.assertEqual(faltan, [])
        self.assertIn('portal_modulos', nuevos)
        self.assertIn('es_demo', nuevos)
        self.assertIn('gei_factores_json', nuevos)

    def test_inlines_anteriores_siguen_y_precios_entran(self):
        viejos = {inline.model._meta.label: set(inline.fields) for inline in self.viejo.inlines}
        nuevos = {inline.model._meta.label: set(inline.fields) for inline in self.nuevo.inlines}
        for etiqueta, campos in viejos.items():
            self.assertIn(etiqueta, nuevos)
            self.assertTrue(campos <= nuevos[etiqueta], etiqueta)
        self.assertIn('core.ProductoComercial', nuevos)
        self.assertIn('precio', nuevos['core.ProductoComercial'])
        self.assertTrue(self.nuevo.inlines[4].show_change_link)


class InterruptorClienteAdminTests(TestCase):
    def test_sin_setting_ni_entorno_queda_apagado(self):
        self.assertFalse(admin_clientes_v2_activo())
