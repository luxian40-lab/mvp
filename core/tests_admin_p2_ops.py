# -*- coding: utf-8 -*-
"""Tests P2 ops: wizard, filtro campaña, bulk publicar, QA, panel, Slack."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Campana, Cliente, Curso, Modulo, ModuloPublicacionEvent, ProgresoEstudiante
from core.modulo_publicacion import (
    campanas_programadas_con_borradores,
    cursos_listos_para_campana_ids,
    diff_snapshots,
    estado_media_paso,
    publicar_modulos_bulk,
    snapshot_modulo_publicacion,
    validar_modulo_qa,
)
from core.views_admin_panel import _avg_avance_pct


User = get_user_model()


def _org():
    return Cliente.objects.create(
        nombre='P2 Org',
        contacto_principal='A',
        email='p2@test.com',
        telefono='573001110099',
        activo=True,
        fecha_fin_suscripcion='2099-12-31',
    )


@override_settings(SECURE_SSL_REDIRECT=False, EKI_MODULE_BUILDER_BETA=True)
class WizardModulosBorradorTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('p2w', 'w@t.com', 'x')
        self.client = Client()

    def test_wizard_crea_modulos_borrador(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            '/admin/curso-nuevo/',
            {
                'nombre': 'Curso P2',
                'n_modulos': '3',
                'modo_aula': Curso.MODO_AULA_MODULOS,
            },
        )
        self.assertEqual(r.status_code, 302)
        curso = Curso.objects.get(nombre='Curso P2')
        self.assertEqual(curso.modulos.filter(publicado_wa=False).count(), 3)


@override_settings(SECURE_SSL_REDIRECT=False)
class CursoListoCampanaFilterTests(TestCase):
    def setUp(self):
        self.org = _org()
        self.curso = Curso.objects.create(
            nombre='Listo WA',
            descripcion='d',
            cliente=self.org,
            activo=True,
        )
        Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='x',
            contenido='Texto mínimo para checklist.',
            publicado_wa=True,
        )

    def test_listo_campana_helper(self):
        self.assertIn(self.curso.pk, cursos_listos_para_campana_ids())


@override_settings(SECURE_SSL_REDIRECT=False)
class BulkPublicarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('p2b', 'b@t.com', 'x')
        self.org = _org()
        self.curso = Curso.objects.create(
            nombre='Bulk',
            descripcion='d',
            cliente=self.org,
            activo=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='Contenido ok.',
            publicado_wa=False,
        )

    def test_bulk_publicar_modulo_con_contenido(self):
        n, errs = publicar_modulos_bulk(self.curso, usuario=self.user)
        self.assertEqual(n, 1)
        self.assertFalse(errs)
        self.m1.refresh_from_db()
        self.assertTrue(self.m1.publicado_wa)
        self.assertTrue(
            ModuloPublicacionEvent.objects.filter(
                modulo=self.m1,
                accion=ModuloPublicacionEvent.ACCION_PUBLICAR,
            ).exists()
        )

    def test_admin_bulk_url(self):
        self.client = Client()
        self.client.force_login(self.user)
        r = self.client.get(
            reverse('admin:core_curso_publicar_modulos', args=[self.curso.pk]),
        )
        self.assertEqual(r.status_code, 302)
        self.m1.refresh_from_db()
        self.assertTrue(self.m1.publicado_wa)


@override_settings(SECURE_SSL_REDIRECT=False)
class CampanaBorradorAlertTests(TestCase):
    def setUp(self):
        self.org = _org()
        self.curso = Curso.objects.create(
            nombre='Camp Curso',
            descripcion='d',
            cliente=self.org,
            activo=True,
        )
        Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='x',
            publicado_wa=False,
        )
        self.camp = Campana.objects.create(
            nombre='Prog',
            cliente=self.org,
            es_campana_curso=True,
            curso_destino=self.curso,
            ejecutada=False,
            fecha_programada=timezone.now() + timedelta(days=2),
        )

    def test_campanas_programadas_con_borradores(self):
        items = campanas_programadas_con_borradores()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['campana_id'], self.camp.pk)


@override_settings(SECURE_SSL_REDIRECT=False)
class ModuloPublicacionHelpersTests(TestCase):
    def test_diff_snapshots_primera_publicacion(self):
        diff = diff_snapshots({}, {'publicado_wa': True})
        self.assertTrue(any('Primera' in d for d in diff))

    def test_estado_media_paso_na_sin_url(self):
        from core.models import PasoModulo

        class P:
            media_url = ''
            media_wa_apto = None

        code, _ = estado_media_paso(P())
        self.assertEqual(code, 'na')

    def test_validar_qa_sin_head(self):
        org = _org()
        curso = Curso.objects.create(nombre='Q', descripcion='d', cliente=org, activo=True)
        mod = Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='M',
            descripcion='d',
            contenido='ok',
        )
        qa = validar_modulo_qa(mod, head_urls=False)
        self.assertTrue(qa.ok)


@override_settings(SECURE_SSL_REDIRECT=False, EKI_SLACK_OPS_WEBHOOK='https://hooks.example/test')
class SlackBorradorTests(TestCase):
    @patch('core.ops_slack.notify_slack_ops')
    def test_signal_nuevo_modulo_curso_con_inscritos(self, mock_slack):
        from core.models import Estudiante

        org = _org()
        curso = Curso.objects.create(nombre='Act', descripcion='d', cliente=org, activo=True)
        est = Estudiante.objects.create(
            cedula='p2s1',
            nombre='Est',
            telefono='573001110088',
            cliente=org,
            activo=True,
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
        Modulo.objects.create(
            curso=curso,
            numero=2,
            titulo='M2',
            descripcion='d',
            contenido='',
            publicado_wa=False,
        )
        mock_slack.assert_called_once()


@override_settings(SECURE_SSL_REDIRECT=False)
class PanelAvancePublicadosTests(TestCase):
    def test_avg_avance_usa_publicados(self):
        org = _org()
        curso = Curso.objects.create(nombre='Av', descripcion='d', cliente=org, activo=True)
        m1 = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='d',
            contenido='x', publicado_wa=True,
        )
        Modulo.objects.create(
            curso=curso, numero=2, titulo='M2', descripcion='d',
            contenido='x', publicado_wa=False,
        )
        from core.models import Estudiante, ModuloCompletado

        est = Estudiante.objects.create(
            cedula='p2a1',
            nombre='E',
            telefono='573001110077',
            cliente=org,
            activo=True,
        )
        prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
        ModuloCompletado.objects.create(progreso=prog, modulo=m1, respuesta_correcta=True)
        pct = _avg_avance_pct()
        self.assertGreaterEqual(pct, 99.0)

    def test_modulo_validar_qa_endpoint(self):
        user = User.objects.create_superuser('p2qa', 'q@t.com', 'x')
        org = _org()
        curso = Curso.objects.create(nombre='QA', descripcion='d', cliente=org, activo=True)
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M', descripcion='d', contenido='ok',
        )
        c = Client()
        c.force_login(user)
        r = c.get(reverse('admin:core_modulo_validar_qa', args=[mod.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            ModuloPublicacionEvent.objects.filter(
                modulo=mod,
                accion=ModuloPublicacionEvent.ACCION_QA,
            ).exists()
        )

    def test_curso_add_redirige_wizard(self):
        user = User.objects.create_superuser('p2add', 'a@t.com', 'x')
        c = Client()
        c.force_login(user)
        r = c.get('/admin/core/curso/add/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('curso-nuevo', r.url)
