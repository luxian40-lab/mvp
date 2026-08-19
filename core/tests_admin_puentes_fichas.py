"""Puentes admin: fichas Módulo/Estudiante/Campaña + conversaciones + panel."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Campana,
    Cliente,
    Curso,
    EnvioLog,
    Estudiante,
    Modulo,
    ProgresoEstudiante,
    WhatsappLog,
)
from core.views_admin_panel import build_panel_snapshot


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EKI_MODULE_BUILDER_BETA=True,
    EKI_MODULE_BUILDER_CURSOS='*',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AdminPuentesFichaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('puentes', 'p@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Org Puentes',
            contacto_principal='Ops',
            email='ops@test.com',
            telefono='573001110050',
            activo=True,
            logo_url='https://example.com/logo.png',
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso WA',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        self.modulo = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Intro',
            descripcion='d',
        )
        self.est = Estudiante.objects.create(
            cedula='puente1',
            nombre='Ana Puentes',
            telefono='573001110088',
            cliente=self.cliente,
            activo=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.modulo,
            completado=False,
        )
        WhatsappLog.objects.create(
            telefono=self.est.telefono,
            mensaje='Hola desde campo',
            tipo='INCOMING',
            estudiante=self.est,
        )
        self.campana = Campana.objects.create(
            nombre='Lanzamiento prueba',
            cliente=self.cliente,
            curso_destino=self.curso,
        )

    def test_ficha_modulo_banda_y_builder(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_modulo_change', args=[self.modulo.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('eki-id-band', body)
        self.assertIn('Abrir Module Builder', body)
        self.assertIn('Intro', body)
        self.assertIn(f'/admin/module-builder/{self.modulo.pk}/', body)

    def test_ficha_estudiante_puente_progreso_y_conv(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_estudiante_change', args=[self.est.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('eki-puente-panel', body)
        self.assertIn('Curso WA', body)
        self.assertIn('Ver conversación', body)
        self.assertIn(f'?estudiante={self.est.pk}', body)
        self.assertIn('Hola desde campo', body)

    def test_ficha_campana_banda_unificada(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_campana_change', args=[self.campana.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('eki-id-band', body)
        self.assertIn('Lanzamiento prueba', body)
        self.assertIn('Org Puentes', body)

    def test_conversaciones_volver_a_estudiante(self):
        self.client.force_login(self.user)
        r = self.client.get(
            reverse('conversaciones') + f'?estudiante={self.est.pk}',
        )
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('Ficha estudiante', body)
        self.assertIn(f'/admin/core/estudiante/{self.est.pk}/change/', body)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AdminPanelAccionesContextualesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('panel_ctx', 'c@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Panel Org',
            contacto_principal='A',
            email='p@test.com',
            telefono='573001110051',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='C',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='panelctx1',
            nombre='Sin Progreso',
            telefono='573001110089',
            cliente=self.cliente,
            activo=True,
        )
        self.campana = Campana.objects.create(
            nombre='Hoy',
            cliente=self.cliente,
            curso_destino=self.curso,
            ejecutada=False,
            fecha_programada=timezone.now(),
        )
        EnvioLog.objects.create(
            campana=self.campana,
            estudiante=self.est,
            estado='FALLIDO',
        )

    def test_panel_acciones_destacadas(self):
        snap = build_panel_snapshot(force=True)
        labels = [a['label'] for a in snap['acciones']]
        self.assertTrue(any('Envíos fallidos' in lb for lb in labels))
        self.assertTrue(any('Campañas hoy' in lb for lb in labels))
        alertas = [a for a in snap['acciones'] if a.get('destacada')]
        self.assertGreaterEqual(len(alertas), 2)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EKI_MODULE_BUILDER_BETA=True,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AdminOnda2MejorasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('onda2', 'o@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Org Onda2',
            contacto_principal='Ops',
            email='o@test.com',
            telefono='573001110060',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Ops',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        Modulo.objects.create(curso=self.curso, numero=1, titulo='M1', descripcion='d')
        self.est = Estudiante.objects.create(
            cedula='onda2',
            nombre='Est Onda2',
            telefono='573001110061',
            cliente=self.cliente,
            activo=True,
        )

    def test_ficha_curso_puente_modulos(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_curso_change', args=[self.curso.pk]))
        body = r.content.decode('utf-8')
        self.assertIn('Ver módulos', body)
        self.assertIn('Module Builder', body)
        self.assertIn('1 módulo', body)

    def test_ficha_cliente_contadores(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_cliente_change', args=[self.cliente.pk]))
        body = r.content.decode('utf-8')
        self.assertIn('eki-puente-panel--stats', body)
        self.assertIn('estudiantes activos', body)

    def test_listado_estudiante_link_chat(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_estudiante_changelist'))
        body = r.content.decode('utf-8')
        self.assertIn('Chat', body)
        self.assertIn(f'?estudiante={self.est.pk}', body)

    def test_filtro_sin_progreso(self):
        self.client.force_login(self.user)
        r = self.client.get(
            reverse('admin:core_estudiante_changelist') + '?eki_progreso=sin',
        )
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('Est Onda2', body)

    def test_envio_certificados_banda(self):
        self.client.force_login(self.user)
        url = (
            reverse('admin_envio_certificados')
            + f'?cliente={self.cliente.pk}&curso={self.curso.pk}'
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('eki-id-band', body)
        self.assertIn('Curso Ops', body)
