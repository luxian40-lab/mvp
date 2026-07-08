"""Tests panel de retención portal (Fase 1)."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante
from core.models_certificados import Certificado
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario
from portal.retencion_service import analitica_retencion_portal


class RetencionServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Retención',
            contacto_principal='A',
            email='ret@test.com',
            telefono='573001111001',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso Ret', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Intro', descripcion='', contenido='c',
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='Avanzado', descripcion='', contenido='c',
        )
        self.est_ok = Estudiante.objects.create(
            cedula='ret1',
            nombre='Activo Uno',
            telefono='573001111002',
            cliente=self.cliente,
            estado_chat='ACTIVO',
        )
        self.est_inactivo = Estudiante.objects.create(
            cedula='ret2',
            nombre='Inactivo Dos',
            telefono='573001111003',
            cliente=self.cliente,
            estado_chat='ACTIVO',
        )
        self.est_habeas = Estudiante.objects.create(
            cedula='ret3',
            nombre='Sin Habeas',
            telefono='573001111004',
            cliente=self.cliente,
            estado_chat='ESPERANDO_HABEAS_DATA',
        )
        self.prog_ok = ProgresoEstudiante.objects.create(
            estudiante=self.est_ok,
            curso=self.curso,
            modulo_actual=self.m2,
            fecha_ultimo_avance=timezone.now(),
        )
        self.prog_inactivo = ProgresoEstudiante.objects.create(
            estudiante=self.est_inactivo,
            curso=self.curso,
            modulo_actual=self.m1,
            fecha_ultimo_avance=timezone.now() - timedelta(days=12),
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est_habeas,
            curso=self.curso,
        )
        ModuloCompletado.objects.create(progreso=self.prog_ok, modulo=self.m1)
        ModuloCompletado.objects.create(progreso=self.prog_ok, modulo=self.m2)
        ModuloCompletado.objects.create(progreso=self.prog_inactivo, modulo=self.m1)
        ProgresoEstudiante.objects.filter(pk=self.prog_inactivo.pk).update(
            fecha_ultimo_avance=timezone.now() - timedelta(days=12),
        )

    def test_kpis_inscritos_activos_inactivos(self):
        data = analitica_retencion_portal(self.cliente, curso_id=self.curso.pk)
        self.assertEqual(data['kpis']['inscritos'], 3)
        self.assertEqual(data['kpis']['activos'], 1)
        self.assertEqual(data['kpis']['inactivos'], 2)

    def test_embudo_modulos_y_abandono(self):
        data = analitica_retencion_portal(self.cliente, curso_id=self.curso.pk)
        modulos_embudo = [p for p in data['embudo'] if p.get('tipo') == 'modulo']
        self.assertEqual(len(modulos_embudo), 2)
        self.assertEqual(modulos_embudo[0]['cantidad'], 2)
        self.assertEqual(modulos_embudo[1]['cantidad'], 1)
        self.assertIsNotNone(data['kpis']['modulo_mayor_abandono'])
        self.assertEqual(data['kpis']['modulo_mayor_abandono']['modulo_numero'], 1)

    def test_certificado_en_kpis(self):
        Certificado.objects.create(
            estudiante=self.est_ok,
            curso=self.curso,
            calificacion_final=85,
            fecha_inicio=timezone.localdate(),
            emitido=True,
        )
        data = analitica_retencion_portal(self.cliente, curso_id=self.curso.pk)
        self.assertEqual(data['kpis']['certificados'], 1)


class RetencionPortalViewTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Portal Ret',
            contacto_principal='B',
            email='retp@test.com',
            telefono='573002222001',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
            portal_productos='cursos',
        )
        self.curso = Curso.objects.create(nombre='Curso P', cliente=self.cliente, activo=True)
        self.user = User.objects.create_user('ret_portal', password='pass1234')
        PortalUsuario.objects.create(user=self.user, organizacion=self.cliente, rol='admin')
        self.http = Client()
        session = self.http.session
        session[PORTAL_SESSION_KEY] = PortalUsuario.objects.get(user=self.user).pk
        session.save()

    def test_retencion_carga(self):
        est = Estudiante.objects.create(
            cedula='rp1', nombre='E1', telefono='573002222002', cliente=self.cliente,
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=self.curso)

        r = self.http.get('/portal/retencion/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Retención y embudo')
        self.assertContains(r, 'Inscritos')
        self.assertContains(r, 'Embudo de aprendizaje')

    def test_retencion_requiere_modulo_cursos(self):
        self.cliente.portal_productos = 'gei'
        self.cliente.save(update_fields=['portal_productos'])
        r = self.http.get('/portal/retencion/')
        self.assertIn(r.status_code, (302, 403))
