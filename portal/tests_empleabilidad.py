from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AliadoEmpleabilidad,
    Cliente,
    Estudiante,
    MisionEmpleabilidad,
    ProgresoEstudiante,
    WhatsappLog,
    Curso,
)
from portal.capabilities import modulos_portal
from portal.empleabilidad_metricas import resumen_empleabilidad_portal
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario


class PortalEmpleabilidadModuloTests(TestCase):
    def test_modulo_empleabilidad_desde_portal_productos(self):
        c = Cliente.objects.create(
            nombre='Org Emp',
            contacto_principal='A',
            email='emp@test.com',
            telefono='573009990090',
            activo=True,
            portal_productos='cursos,empleabilidad',
        )
        m = modulos_portal(c)
        self.assertTrue(m['cursos'])
        self.assertTrue(m['empleabilidad'])
        self.assertFalse(m['gei'])

    def test_modulo_empleabilidad_off_sin_portal_productos(self):
        c = Cliente.objects.create(
            nombre='Solo Cursos',
            contacto_principal='A',
            email='sc@test.com',
            telefono='573009990091',
            activo=True,
            tipo_proyecto='cursos',
        )
        m = modulos_portal(c)
        self.assertFalse(m['empleabilidad'])


class PortalEmpleabilidadVistaTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Portal Emp',
            contacto_principal='Ana',
            email='portal-emp@test.com',
            telefono='573009990092',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
            portal_productos='cursos,empleabilidad',
        )
        self.cliente_sin = Cliente.objects.create(
            nombre='Sin Emp',
            contacto_principal='Bob',
            email='sin-emp@test.com',
            telefono='573009990093',
            activo=True,
            portal_productos='cursos',
        )
        user = User.objects.create_user('emp_admin', password='pass1234')
        PortalUsuario.objects.create(user=user, organizacion=self.cliente, rol='admin')
        self.http = Client()
        session = self.http.session
        session[PORTAL_SESSION_KEY] = PortalUsuario.objects.get(user=user).pk
        session.save()

    def test_vista_requiere_modulo(self):
        user2 = User.objects.create_user('sin_emp', password='pass1234')
        PortalUsuario.objects.create(user=user2, organizacion=self.cliente_sin, rol='admin')
        http2 = Client()
        session = http2.session
        session[PORTAL_SESSION_KEY] = PortalUsuario.objects.get(user=user2).pk
        session.save()
        r = http2.get('/portal/empleabilidad/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/portal/dashboard/', r['Location'])

    def test_vista_muestra_kpis(self):
        est = Estudiante.objects.create(
            cedula='8001', nombre='Joven Activo', telefono='573111111201', cliente=self.cliente,
        )
        aliado = AliadoEmpleabilidad.objects.create(
            nombre_empresa='Café Norte',
            cliente=self.cliente,
            latitud=4.65,
            longitud=-74.05,
            vacantes_activas=True,
            codigo_secreto='CAFE01',
        )
        MisionEmpleabilidad.objects.create(
            cliente=self.cliente,
            estudiante=est,
            aliado=aliado,
            estado='completada',
            codigo_validado=True,
            latitud=4.651,
            longitud=-74.051,
            distancia_metros=120,
        )
        WhatsappLog.objects.create(
            telefono=est.telefono,
            mensaje='hola',
            tipo='INCOMING',
            estudiante=est,
        )

        r = self.http.get('/portal/empleabilidad/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Empleabilidad territorial')
        self.assertContains(r, 'Retención')
        self.assertContains(r, 'Misiones completadas')
        self.assertContains(r, 'Oportunidades georreferenciadas')
        self.assertContains(r, 'Café Norte')


class PortalEmpleabilidadMetricasTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Métricas Emp',
            contacto_principal='X',
            email='met-emp@test.com',
            telefono='573009990094',
            activo=True,
        )
        self.est_activo = Estudiante.objects.create(
            cedula='8002', nombre='Activo', telefono='573111111202', cliente=self.cliente,
        )
        self.est_inactivo = Estudiante.objects.create(
            cedula='8003', nombre='Inactivo', telefono='573111111203', cliente=self.cliente,
        )
        self.aliado = AliadoEmpleabilidad.objects.create(
            nombre_empresa='Aliado Test',
            cliente=self.cliente,
            latitud=4.6,
            longitud=-74.1,
            vacantes_activas=True,
            codigo_secreto='ALI01',
        )

    def test_retencion_por_whatsapp_reciente(self):
        WhatsappLog.objects.create(
            telefono=self.est_activo.telefono,
            mensaje='ok',
            tipo='INCOMING',
            estudiante=self.est_activo,
        )
        resumen = resumen_empleabilidad_portal(self.cliente)
        self.assertEqual(resumen['total_inscritos'], 2)
        self.assertEqual(resumen['jovenes_activos'], 1)
        self.assertEqual(resumen['retencion_pct'], 50.0)

    def test_retencion_por_progreso_reciente(self):
        curso = Curso.objects.create(
            nombre='Curso Emp', descripcion='d', cliente=self.cliente, activo=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est_inactivo,
            curso=curso,
            fecha_ultimo_avance=timezone.now(),
        )
        resumen = resumen_empleabilidad_portal(self.cliente)
        self.assertEqual(resumen['jovenes_activos'], 1)

    def test_misiones_y_oportunidades_georef(self):
        MisionEmpleabilidad.objects.create(
            cliente=self.cliente,
            estudiante=self.est_activo,
            aliado=self.aliado,
            estado='completada',
            latitud=4.601,
            longitud=-74.101,
        )
        MisionEmpleabilidad.objects.create(
            cliente=self.cliente,
            estudiante=self.est_inactivo,
            aliado=self.aliado,
            estado='descubierta',
            latitud=4.602,
            longitud=-74.102,
        )
        MisionEmpleabilidad.objects.create(
            cliente=self.cliente,
            estudiante=self.est_inactivo,
            aliado=self.aliado,
            estado='cancelada',
            latitud=4.603,
            longitud=-74.103,
        )
        resumen = resumen_empleabilidad_portal(self.cliente)
        self.assertEqual(resumen['misiones_completadas'], 1)
        self.assertEqual(resumen['oportunidades_georef'], 2)

    def test_actividad_antigua_no_cuenta_retencion(self):
        WhatsappLog.objects.create(
            telefono=self.est_activo.telefono,
            mensaje='viejo',
            tipo='INCOMING',
            estudiante=self.est_activo,
        )
        WhatsappLog.objects.filter(estudiante=self.est_activo).update(
            fecha=timezone.now() - timedelta(days=45),
        )
        resumen = resumen_empleabilidad_portal(self.cliente, dias_retencion=30)
        self.assertEqual(resumen['jovenes_activos'], 0)
        self.assertEqual(resumen['retencion_pct'], 0.0)


class PortalEmpleabilidadAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('admin_emp', 'admin@test.com', 'pass1234')
        self.cliente = Cliente.objects.create(
            nombre='Org Admin Emp',
            contacto_principal='Admin',
            email='admin-emp@test.com',
            telefono='573009990095',
            activo=True,
            portal_productos='cursos,empleabilidad',
        )
        self.est = Estudiante.objects.create(
            cedula='8010', nombre='Joven KPI', telefono='573111111210', cliente=self.cliente,
        )
        self.aliado = AliadoEmpleabilidad.objects.create(
            nombre_empresa='Tienda Sur',
            cliente=self.cliente,
            latitud=4.7,
            longitud=-74.0,
            vacantes_activas=True,
            codigo_secreto='SUR01',
        )
        MisionEmpleabilidad.objects.create(
            cliente=self.cliente,
            estudiante=self.est,
            aliado=self.aliado,
            estado='completada',
            latitud=4.701,
            longitud=-74.001,
        )
        WhatsappLog.objects.create(
            telefono=self.est.telefono,
            mensaje='hola',
            tipo='INCOMING',
            estudiante=self.est,
        )
        self.http = Client()
        self.http.force_login(self.staff)

    def test_admin_cliente_muestra_kpis(self):
        from django.contrib.admin.sites import AdminSite

        from core.admin import ClienteAdmin

        admin_obj = ClienteAdmin(Cliente, AdminSite())
        html = str(admin_obj.empleabilidad_kpis_resumen(self.cliente))
        self.assertIn('100.0%', html)
        self.assertIn('Retención', html)
        self.assertIn('Misiones completadas', html)
        self.assertIn('Oportunidades georreferenciadas', html)
        self.assertIn('Ver misiones', html)
        self.assertIn(reverse('admin:learning_misionempleabilidad_changelist'), html)

    def test_admin_form_incluye_modulo_empleabilidad(self):
        from portal.forms import PORTAL_PRODUCTO_CHOICES

        labels = [label for _key, label in PORTAL_PRODUCTO_CHOICES]
        self.assertIn('Empleabilidad territorial', labels)
