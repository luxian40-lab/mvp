"""Admin de Cliente v2. El interruptor sigue apagado por defecto."""
import sys
from datetime import timedelta

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import clear_url_caches, reverse
from django.utils import timezone

from core.admin.cliente_v2_flag import admin_clientes_v2_activo
from core.admin.clientes import ClienteAdmin
from core.admin.clientes_v2 import ClienteAdminV2
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
    WhatsappLog,
)


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


def _recargar_admin():
    """Las URLs del admin quedan armadas al importar. Hay que rehacerlas al cambiar el registro."""
    clear_url_caches()
    urlconf = settings.ROOT_URLCONF
    if urlconf in sys.modules:
        del sys.modules[urlconf]
    __import__(urlconf)


@override_settings(
    ADMIN_CLIENTES_V2=True,
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ListadoClienteV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('list_cli', 'l@t.com', 'pass12345')
        self.client.force_login(self.user)
        admin.site.unregister(Cliente)
        admin.site.register(Cliente, ClienteAdminV2)
        _recargar_admin()
        hoy = timezone.localdate()
        self.real = Cliente.objects.create(
            nombre='Cooperativa Real',
            contacto_principal='Ana',
            email='real@test.com',
            telefono='573009990101',
            nit='9001',
            activo=True,
            es_demo=False,
            plan_linea_meta='curso_asesor',
            portal_productos='cursos,nat',
            fecha_fin_suscripcion=hoy + timedelta(days=10),
        )
        self.demo = Cliente.objects.create(
            nombre='Demo Cliente',
            contacto_principal='Bo',
            email='demo@test.com',
            telefono='573009990102',
            activo=True,
            es_demo=True,
            plan_linea_meta='',
            fecha_fin_suscripcion=hoy - timedelta(days=3),
        )
        self.inactivo = Cliente.objects.create(
            nombre='Org Quieta',
            contacto_principal='Ci',
            email='quieta@test.com',
            telefono='573009990103',
            activo=False,
            es_demo=False,
            plan_linea_meta='dos_cursos',
        )
        self.curso = Curso.objects.create(
            nombre='Café',
            descripcion='d',
            cliente=self.real,
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='listcli1',
            nombre='Luz',
            telefono='573009990201',
            cliente=self.real,
            activo=True,
        )
        Estudiante.objects.create(
            cedula='listcli2',
            nombre='Inactivo',
            telefono='573009990202',
            cliente=self.real,
            activo=False,
        )
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Siembra',
            descripcion='d',
            publicado_wa=True,
        )
        prog = ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso)
        ModuloCompletado.objects.create(progreso=prog, modulo=mod)
        WhatsappLog.objects.create(
            telefono=self.est.telefono,
            mensaje='hola',
            estudiante=self.est,
        )

    def tearDown(self):
        admin.site.unregister(Cliente)
        admin.site.register(Cliente, ClienteAdmin)
        _recargar_admin()

    def test_pestanas_y_columnas(self):
        url = reverse('admin:core_cliente_changelist')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn(f'Todos · {Cliente.objects.count()}', body)
        self.assertIn(f'Reales · {Cliente.objects.filter(es_demo=False).count()}', body)
        self.assertIn(f'Demo y pruebas · {Cliente.objects.filter(es_demo=True).count()}', body)
        self.assertIn(f'Sin plan Meta · {Cliente.objects.filter(plan_linea_meta="").count()}', body)
        self.assertIn(f'Inactivos · {Cliente.objects.filter(activo=False).count()}', body)
        self.assertIn('Cooperativa Real', body)
        self.assertIn('eki-cli-chip">OP1', body)
        self.assertIn('Cursos eki', body)
        self.assertIn('Agente Nat', body)
        self.assertIn('Demo', body)
        self.assertIn('Vence en 10 días', body)
        self.assertIn('100%', body)

        solo_demo = self.client.get(url + '?eki_org=demo')
        demo_body = solo_demo.content.decode('utf-8')
        self.assertIn('Demo Cliente', demo_body)
        self.assertNotIn('Cooperativa Real', demo_body)
        self.assertIn('Sin plan', demo_body)
        self.assertIn('Venció hace 3 días', demo_body)

    def test_consultas_no_crecen_con_el_numero_de_clientes(self):
        url = reverse('admin:core_cliente_changelist')
        self.client.get(url)

        def medir():
            with CaptureQueriesContext(connection) as ctx:
                respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200)
            return len(ctx)

        con_pocos = medir()
        Cliente.objects.bulk_create([
            Cliente(
                nombre=f'Org extra {i}',
                contacto_principal='A',
                email=f'extra{i}@test.com',
                telefono=f'57{i:010d}',
            )
            for i in range(500)
        ])
        con_muchos = medir()
        self.assertEqual(con_pocos, con_muchos)

    def test_asignar_plan_pide_confirmacion_y_cuenta_estudiantes(self):
        url = reverse('admin:core_cliente_changelist')
        data = {
            'action': 'asignar_plan_linea_meta',
            '_selected_action': [str(self.real.pk), str(self.demo.pk)],
        }
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('<strong>2</strong> organizaciones', body)
        self.assertIn('<strong>2</strong> estudiantes', body)
        r2 = self.client.post(url, {
            **data,
            'aplicar': '1',
            'plan_linea_meta': 'asesor_60',
        })
        self.assertEqual(r2.status_code, 302)
        self.real.refresh_from_db()
        self.demo.refresh_from_db()
        self.assertEqual(self.real.plan_linea_meta, 'asesor_60')
        self.assertEqual(self.demo.plan_linea_meta, 'asesor_60')

    def test_ficha_muestra_encabezado_y_no_el_menu_de_seccion(self):
        url = reverse('admin:core_cliente_change', args=[self.real.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertNotIn('Ir a sección', body)
        self.assertIn('id="eki-cli-encabezado"', body)
        self.assertIn('Cooperativa Real', body)
        self.assertIn('real@test.com', body)
        self.assertIn('NIT 9001', body)
        self.assertIn('Cursos eki', body)
        self.assertIn('estudiantes activos', body)
        self.assertIn('cursos activos', body)
        self.assertIn('fieldset-datos', body)
        self.assertIn('fieldset-marca', body)
        self.assertIn('Así se ve', body)
        self.assertIn('id_nombre', body)
        self.assertIn('id_nit', body)
        self.assertIn('dejan de recibir mensajes', body)

        demo = self.client.get(reverse('admin:core_cliente_change', args=[self.demo.pk]))
        self.assertEqual(demo.status_code, 200)
        self.assertIn('Sin plan Meta', demo.content.decode('utf-8'))
