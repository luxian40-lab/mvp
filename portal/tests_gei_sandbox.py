"""Tests Excel GEI + sandbox portal."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client as HttpClient, TestCase, override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante
from formulario.models import FichaGEI, ResultadoGEI
from portal.gei_exports import respuesta_excel_fichas_gei
from portal.gei_sandbox import (
    asegurar_cupos_sandbox,
    margen_error_pct,
    queryset_sandbox_org,
)
from portal.gei_service import parse_filtros_gei, queryset_fichas_org
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario


@override_settings(SECURE_SSL_REDIRECT=False)
class GeiExcelExportTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org GEI Excel',
            email='gei-excel@test.local',
            activo=True,
            tipo_proyecto='gei',
            portal_productos='gei',
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            cliente=self.org,
            nombre='Curso GEI',
            activo=True,
            tiene_formulario_gei=True,
        )
        self.est = Estudiante.objects.create(
            cliente=self.org,
            nombre='Productor Real',
            cedula='1001',
            telefono='573001111111',
            activo=True,
        )
        self.ficha = FichaGEI.objects.create(
            estudiante=self.est,
            cliente=self.org,
            curso=self.curso,
            nombre_finca='La Esperanza',
            area_ha=2.5,
            fertilizante_kg=100,
            concentracion_n_pct=15,
            produccion_kg=800,
            energia_kwh=200,
            anio_datos_energia=2025,
            es_sandbox=False,
        )
        # Forzar update aware (auto_now)
        FichaGEI.objects.filter(pk=self.ficha.pk).update(
            fecha_update=timezone.now(),
        )
        self.ficha.refresh_from_db()

    def test_excel_con_datetime_aware_no_falla(self):
        class FakeReq:
            GET = {}

        filtros = parse_filtros_gei(FakeReq(), self.org)
        resp = respuesta_excel_fichas_gei(self.org, filtros, nombre_archivo='t.xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resp['Content-Type'],
        )
        self.assertTrue(resp.content[:2] == b'PK')

    def test_inventario_excluye_sandbox(self):
        sb_est = Estudiante.objects.create(
            cliente=self.org, nombre='Sandbox GEI 01', cedula='SANDBOX-X', telefono='573009999001',
        )
        FichaGEI.objects.create(
            estudiante=sb_est, cliente=self.org, curso=self.curso, es_sandbox=True,
            nombre_finca='Ensayo',
        )

        class FakeReq:
            GET = {}

        filtros = parse_filtros_gei(FakeReq(), self.org)
        qs = queryset_fichas_org(self.org, filtros)
        self.assertEqual(qs.filter(es_sandbox=True).count(), 0)
        self.assertEqual(qs.filter(es_sandbox=False).count(), 1)


@override_settings(SECURE_SSL_REDIRECT=False)
class GeiSandboxTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org GEI Sandbox',
            email='gei-sandbox@test.local',
            activo=True,
            tipo_proyecto='gei',
            portal_productos='gei',
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            cliente=self.org,
            nombre='Curso Sandbox',
            activo=True,
            tiene_formulario_gei=True,
        )
        self.user = User.objects.create_user('gei_admin', password='x')
        self.pu = PortalUsuario.objects.create(
            user=self.user, organizacion=self.org, rol='admin',
        )
        self.client = HttpClient()
        session = self.client.session
        session[PORTAL_SESSION_KEY] = self.pu.pk
        session.save()

    def test_margen_error(self):
        self.assertEqual(margen_error_pct(10, 10), 0.0)
        self.assertEqual(margen_error_pct(11, 10), 10.0)
        self.assertIsNone(margen_error_pct(None, 10))

    def test_asegurar_10_cupos(self):
        slots = asegurar_cupos_sandbox(self.org, cupos=10, curso=self.curso)
        self.assertEqual(len(slots), 10)
        self.assertEqual(queryset_sandbox_org(self.org).count(), 10)
        # idempotente
        slots2 = asegurar_cupos_sandbox(self.org, cupos=10, curso=self.curso)
        self.assertEqual(len(slots2), 10)
        self.assertEqual(queryset_sandbox_org(self.org).count(), 10)

    def test_editar_sandbox_recalcula_y_margen(self):
        slots = asegurar_cupos_sandbox(self.org, cupos=10, curso=self.curso)
        ficha = slots[0]
        url = f'/portal/gei/sandbox/{ficha.pk}/'
        resp = self.client.post(url, {
            'nombre_finca': 'Finca ensayo 01',
            'area_ha': '3',
            'num_plantas': '1200',
            'tipo_fertilizante': 'sintetico',
            'fertilizante_kg': '150',
            'concentracion_n_pct': '20',
            'produccion_kg': '1000',
            'energia_kwh': '300',
            'anio_datos_energia': '2025',
            'tipo_combustible': 'diesel',
            'combustible_gal': '40',
            'residuos_ton': '1.5',
            'manejo_residuos': 'compost',
            'tipo_cultivo': 'perenne',
            'alta_mecanizacion': 'no',
            'usa_enmiendas_cal': 'si',
            'tiene_bosque': 'si',
            'area_bosque_ha': '0.5',
            'referencia_balance_tco2e': '1.0',
        })
        self.assertEqual(resp.status_code, 200)
        ficha.refresh_from_db()
        self.assertTrue(ficha.es_sandbox)
        self.assertEqual(ficha.nombre_finca, 'Finca ensayo 01')
        self.assertTrue(ResultadoGEI.objects.filter(ficha=ficha).exists())
        res = ficha.resultado
        self.assertIsNotNone(res.balance_neto_tco2e)
        # margen aparece en contexto
        self.assertContains(resp, 'Margen de error')

    def test_listado_sandbox_autoprovisiona(self):
        resp = self.client.get('/portal/gei/sandbox/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(queryset_sandbox_org(self.org).count(), 10)
