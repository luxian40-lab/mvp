"""Tests onda 3: manual, command search, mejoras admin ops."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.admin_command_search import eki_command_search_callback
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ProgresoEstudiante,
    WhatsappLog,
)
from core.views_admin_panel import build_panel_snapshot
from core.models_certificados import Certificado


@override_settings(SECURE_SSL_REDIRECT=False)
class ManualAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('manual', 'm@t.com', 'pass12345')

    def test_manual_unfold_shell_y_busqueda(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('instrucciones'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('eki-manual', body)
        self.assertIn('Command palette', body)
        self.assertIn('Guías rápidas', body)
        self.assertIn('Captar', body)
        self.assertIn('eki_admin_manual.css', body)
        self.assertIn('WhatsappLog triage', body)


@override_settings(SECURE_SSL_REDIRECT=False)
class CommandSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('cmd', 'c@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Cmd Org',
            contacto_principal='A',
            email='c@test.com',
            telefono='573001110070',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.est = Estudiante.objects.create(
            cedula='cmd1',
            nombre='Pedro Cmd',
            telefono='573001110071',
            cliente=self.cliente,
            activo=True,
        )

    def test_callback_telefono_y_manual(self):
        class R:
            user = self.user

        results = eki_command_search_callback(R(), '573001110071')
        links = [r.link for r in results]
        self.assertTrue(any('conversaciones' in l for l in links))
        self.assertTrue(any('estudiante' in l for l in links))

        manual = eki_command_search_callback(R(), 'manual')
        self.assertTrue(any('instrucciones' in r.link for r in manual))

        borrador = eki_command_search_callback(R(), 'borrador')
        self.assertTrue(any('publicado_wa' in r.link for r in borrador))

    def test_admin_search_endpoint_ok(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:search') + '?s=manual')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('command-results-list', body)


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminOnda3Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('o3', 'o3@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='O3 Org',
            contacto_principal='A',
            email='o3@test.com',
            telefono='573001110080',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso O3',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='o3est',
            nombre='Est O3',
            telefono='573001110081',
            cliente=self.cliente,
            activo=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            completado=True,
        )
        Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Vacío',
            descripcion='d',
        )
        WhatsappLog.objects.create(
            telefono=self.est.telefono,
            mensaje='Ping',
            tipo='INCOMING',
            estudiante=self.est,
        )

    def test_whatsapplog_chat_link_y_filtro_hoy(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_whatsapplog_changelist'))
        body = r.content.decode('utf-8')
        self.assertIn('Chat', body)
        self.assertIn('conversaciones', body)

    def test_cliente_ultima_wa_en_ficha(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_cliente_change', args=[self.cliente.pk]))
        body = r.content.decode('utf-8')
        self.assertIn('Último WA org', body)
        self.assertIn('Ping', body)

    def test_curso_pct_completados(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_curso_change', args=[self.curso.pk]))
        body = r.content.decode('utf-8')
        self.assertIn('% completados', body)

    def test_modulo_borrador_sin_pasos(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_modulo_changelist'))
        body = r.content.decode('utf-8')
        self.assertIn('Borrador', body)

    def test_conversaciones_busqueda_q(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('conversaciones') + '?q=Est+O3')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('name="q"', body)

    def test_panel_certs_pendientes(self):
        Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso,
            calificacion_final=85,
            fecha_inicio=timezone.localdate(),
            emitido=True,
            enviado_whatsapp=False,
            fecha_emision=timezone.now(),
        )
        snap = build_panel_snapshot(force=True)
        labels = [a['label'] for a in snap['acciones']]
        self.assertTrue(any('Certs pend' in lb for lb in labels))

    def test_inscribir_curso_masivo_form(self):
        est2 = Estudiante.objects.create(
            cedula='o3est2',
            nombre='Sin curso',
            telefono='573001110082',
            cliente=self.cliente,
            activo=True,
        )
        self.client.force_login(self.user)
        r = self.client.post(
            reverse('admin:core_estudiante_changelist'),
            {
                'action': 'inscribir_curso_masivo',
                'post': 'yes',
                '_selected_action': [str(est2.pk)],
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn('Inscribir en curso', r.content.decode('utf-8'))
