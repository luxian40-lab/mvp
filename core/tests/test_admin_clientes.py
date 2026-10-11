"""Admin de Cliente v2. El interruptor sigue apagado por defecto."""
import json
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
from core.admin.clientes_v2 import ClienteAdminFormV2, ClienteAdminV2
from core.models import (
    Campana,
    Cliente,
    Curso,
    Estudiante,
    FaqOrganizacion,
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
        from portal.models import PortalUsuario
        self.assertEqual(
            [clave for clave, _etiqueta in PortalUsuario.ROL_CHOICES],
            ['admin', 'profesor', 'viewer', 'eki_ops'],
        )
        self.assertIn('rol', self.nuevo.inlines[0].fields)


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
        demo_body = demo.content.decode('utf-8')
        self.assertIn('Sin plan Meta', demo_body)
        self.assertIn('Vencida hace 3 días', demo_body)
        self.assertIn('1 curso al mes y asesor (30 preguntas)', demo_body)
        self.assertIn('2 cursos al mes, sin asesor', demo_body)
        self.assertIn('60 preguntas al mes', demo_body)
        self.assertIn('Ritmo drip por curso', body)
        self.assertIn('Calendario de módulos', body)
        self.assertIn('Usuarios del portal', body)
        self.assertIn(
            f'/admin/core/estudiante/?cliente__id__exact={self.real.pk}',
            body,
        )
        self.assertIn('2 estudiantes', body)
        self.assertIn(
            f'/admin/core/grupoestudiantes/?cliente__id__exact={self.real.pk}',
            body,
        )

    def test_cobertura_pqrs_y_actividad(self):
        self.est.departamento = 'Antioquia'
        self.est.save(update_fields=['departamento'])
        FaqOrganizacion.objects.create(
            cliente=self.real,
            pregunta='¿Cuándo pagan?',
            respuesta='El viernes.',
        )
        Campana.objects.create(nombre='Cosecha', cliente=self.real)
        from django.contrib.admin.models import CHANGE, LogEntry
        from django.contrib.contenttypes.models import ContentType

        LogEntry.objects.log_action(
            user_id=self.user.pk,
            content_type_id=ContentType.objects.get_for_model(Cliente).pk,
            object_id=self.real.pk,
            object_repr=self.real.nombre,
            action_flag=CHANGE,
            change_message='nota de prueba',
        )
        r = self.client.get(reverse('admin:core_cliente_change', args=[self.real.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('FAQ organización', body)
        self.assertIn('1 preguntas', body)
        self.assertIn('Antioquia: 1', body)
        self.assertIn('Cosecha', body)
        self.assertIn('nota de prueba', body)
        self.assertIn('activeFieldsetTab', body)

    def test_eliminar_se_bloquea_con_estudiantes_y_pide_el_nombre_si_esta_vacia(self):
        ocupada = reverse('admin:core_cliente_eliminar', args=[self.real.pk])
        r = self.client.get(ocupada)
        self.assertEqual(r.status_code, 200)
        cuerpo = r.content.decode('utf-8')
        self.assertIn('No se puede eliminar', cuerpo)
        self.assertIn('Desactivar', cuerpo)
        self.assertTrue(Cliente.objects.filter(pk=self.real.pk).exists())

        vacia = Cliente.objects.create(
            nombre='Org Vacia',
            contacto_principal='Ana',
            email='vacia@test.com',
            telefono='573009990199',
        )
        url = reverse('admin:core_cliente_eliminar', args=[vacia.pk])
        mal = self.client.post(url, {'confirmacion': 'otro'})
        self.assertEqual(mal.status_code, 200)
        self.assertTrue(Cliente.objects.filter(pk=vacia.pk).exists())
        bien = self.client.post(url, {'confirmacion': 'Org Vacia'})
        self.assertEqual(bien.status_code, 302)
        self.assertFalse(Cliente.objects.filter(pk=vacia.pk).exists())

    def test_desactivar_apaga_la_organizacion(self):
        from django.contrib.messages.storage.fallback import FallbackStorage

        request = RequestFactory().post('/admin/core/cliente/1/change/', {'_desactivar': '1'})
        request.user = self.user
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        ClienteAdminV2(Cliente, admin.site).response_change(request, self.real)
        self.real.refresh_from_db()
        self.assertFalse(self.real.activo)

    def test_mojibake_lista_y_solo_escribe_con_apply(self):
        from io import StringIO

        from django.core.management import call_command

        from core.models_extras import GrupoEstudiantes

        roto = 'Usaqu\u00c3\u00a9n'
        cliente = Cliente.objects.create(
            nombre=roto,
            contacto_principal='Ana',
            email='moji@test.com',
            telefono='573009990188',
        )
        grupo = GrupoEstudiantes.objects.create(nombre=roto, cliente=cliente)
        salida = StringIO()
        call_command('corregir_nombres_mojibake', '--dry-run', stdout=salida)
        cliente.refresh_from_db()
        self.assertEqual(cliente.nombre, roto)
        self.assertIn('Usaquén', salida.getvalue())
        call_command('corregir_nombres_mojibake', '--apply', stdout=StringIO())
        cliente.refresh_from_db()
        grupo.refresh_from_db()
        self.assertEqual(cliente.nombre, 'Usaquén')
        self.assertEqual(grupo.nombre, 'Usaquén')


def _datos_formulario(cliente, **cambios):
    form = ClienteAdminFormV2(instance=cliente)
    data = {}
    for name, field in form.fields.items():
        if getattr(field, 'disabled', False):
            continue
        initial = form.get_initial_for_field(field, name)
        if isinstance(initial, bool):
            if initial:
                data[name] = 'on'
        elif isinstance(initial, (list, tuple)):
            data[name] = list(initial)
        elif isinstance(initial, dict):
            data[name] = json.dumps(initial)
        elif initial is None:
            data[name] = ''
        elif hasattr(initial, 'isoformat'):
            data[name] = initial.isoformat()
        else:
            data[name] = initial
    data.update(cambios)
    return data


class GuardadoClienteV2Tests(TestCase):
    def _cliente(self, **kwargs):
        base = dict(
            nombre='Org Form',
            contacto_principal='Ana',
            email='form@test.com',
            telefono='573009991111',
        )
        base.update(kwargs)
        return Cliente.objects.create(**base)

    def test_casillas_iguales_conservan_el_texto(self):
        cliente = self._cliente(portal_productos='nat,cursos')
        form = ClienteAdminFormV2(
            _datos_formulario(cliente, portal_modulos=['cursos', 'nat']),
            instance=cliente,
        )
        self.assertTrue(form.is_valid(), form.errors)
        guardado = form.save()
        self.assertEqual(guardado.portal_productos, 'nat,cursos')

    def test_casillas_nuevas_guardan_el_texto_separado_por_comas(self):
        cliente = self._cliente(portal_productos='cursos')
        form = ClienteAdminFormV2(
            _datos_formulario(cliente, portal_modulos=['cursos', 'gei']),
            instance=cliente,
        )
        self.assertTrue(form.is_valid(), form.errors)
        guardado = form.save()
        self.assertEqual(guardado.portal_productos, 'cursos,gei')

    def test_numero_nat_invalido_y_duplicado(self):
        otro = self._cliente(
            nombre='Org Dueña',
            email='duena@test.com',
            telefono='573009991112',
            numero_whatsapp_nat='573001112233',
        )
        cliente = self._cliente(
            nombre='Org Nueva',
            email='nueva@test.com',
            telefono='573009991113',
        )
        invalido = ClienteAdminFormV2(
            _datos_formulario(cliente, numero_whatsapp_nat='12'),
            instance=cliente,
        )
        self.assertFalse(invalido.is_valid())
        self.assertIn('dígitos', str(invalido.errors['numero_whatsapp_nat']))

        duplicado = ClienteAdminFormV2(
            _datos_formulario(cliente, numero_whatsapp_nat='573001112233'),
            instance=cliente,
        )
        self.assertFalse(duplicado.is_valid())
        self.assertIn(otro.nombre, str(duplicado.errors['numero_whatsapp_nat']))

    def test_numero_nat_sin_cambios_pasa_aunque_sea_corto(self):
        cliente = self._cliente(numero_whatsapp_nat='123')
        form = ClienteAdminFormV2(_datos_formulario(cliente), instance=cliente)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().numero_whatsapp_nat, '123')
