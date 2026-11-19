"""Pulso semanal cohorte septiembre: barras HTML, sin envío sin correos."""
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.utils.html import escape

from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante
from core.reporte_clientes import (
    COHORTE_NOMBRES,
    DESDE_COHORTE,
    construir_html,
    destinatarios_desde_setting,
    enviar_reporte_clientes,
    recoger_snapshot,
)

_BOG = ZoneInfo('America/Bogota')


class DestinatariosTests(TestCase):
    def test_parte_lista_y_ignora_basura(self):
        self.assertEqual(destinatarios_desde_setting(''), [])
        self.assertEqual(destinatarios_desde_setting([]), [])
        self.assertEqual(
            destinatarios_desde_setting('jefe@eki.co, ops@eki.co ,malo, a @ x'),
            ['jefe@eki.co', 'ops@eki.co'],
        )


class CohorteSnapshotTests(TestCase):
    def setUp(self):
        self.alitic = Cliente.objects.create(
            nombre='Alitic', contacto_principal='A', email='a@x.co',
            telefono='573001200001', activo=True,
        )
        self.lhaura = Cliente.objects.create(
            nombre='Lhaura vet', contacto_principal='L', email='l@x.co',
            telefono='573001200002', activo=True,
        )
        self.agri = Cliente.objects.create(
            nombre='Agricapital', contacto_principal='G', email='g@x.co',
            telefono='573001200003', activo=True,
        )
        # Fuera de cohorte
        Cliente.objects.create(
            nombre='Cenipalma', contacto_principal='C', email='c@x.co',
            telefono='573001200004', activo=True,
        )
        self.curso_a = Curso.objects.create(nombre='Crea', descripcion='d', cliente=self.alitic)
        self.curso_l = Curso.objects.create(nombre='Vet', descripcion='d', cliente=self.lhaura)
        mod = Modulo.objects.create(curso=self.curso_a, numero=1, titulo='M1', descripcion='d', contenido='c')

        est_a = Estudiante.objects.create(
            cedula='9912001', nombre='Ana', telefono='573001201001',
            cliente=self.alitic, activo=True,
        )
        est_l = Estudiante.objects.create(
            cedula='9912002', nombre='Leo', telefono='573001201002',
            cliente=self.lhaura, activo=True,
        )
        # Inscripción desde septiembre (en cohorte)
        p_a = ProgresoEstudiante.objects.create(
            estudiante=est_a, curso=self.curso_a, completado=False,
        )
        ProgresoEstudiante.objects.filter(pk=p_a.pk).update(
            fecha_inicio=datetime(2026, 9, 15, 10, 0, 0, tzinfo=_BOG),
        )
        ModuloCompletado.objects.create(progreso=p_a, modulo=mod)
        # Completado Lhaura
        p_l = ProgresoEstudiante.objects.create(
            estudiante=est_l, curso=self.curso_l, completado=True,
        )
        ProgresoEstudiante.objects.filter(pk=p_l.pk).update(
            fecha_inicio=datetime(2026, 10, 1, 10, 0, 0, tzinfo=_BOG),
        )
        # Viejo (antes de sep) no cuenta
        est_viejo = Estudiante.objects.create(
            cedula='9912003', nombre='Viejo', telefono='573001201003',
            cliente=self.alitic, activo=True,
        )
        p_v = ProgresoEstudiante.objects.create(
            estudiante=est_viejo, curso=self.curso_a, completado=True,
        )
        ProgresoEstudiante.objects.filter(pk=p_v.pk).update(
            fecha_inicio=datetime(2026, 8, 1, 10, 0, 0, tzinfo=_BOG),
        )

    def test_solo_cohorte_y_desde_septiembre(self):
        snap = recoger_snapshot()
        self.assertEqual(DESDE_COHORTE, date(2026, 9, 1))
        nombres = [o['org_nombre'] for o in snap['orgs']]
        self.assertEqual(nombres, list(COHORTE_NOMBRES))
        by_name = {o['org_nombre']: o for o in snap['orgs']}
        self.assertEqual(by_name['Alitic']['inscritos'], 1)
        self.assertEqual(by_name['Alitic']['en_curso'], 1)
        self.assertEqual(by_name['Lhaura vet']['inscritos'], 1)
        self.assertEqual(by_name['Lhaura vet']['finalizados'], 1)
        self.assertEqual(by_name['Agricapital']['inscritos'], 0)
        self.assertEqual(snap['totales']['inscritos'], 2)

    def test_html_barras_y_novedades(self):
        snap = recoger_snapshot()
        html = construir_html(snap)
        self.assertIn('Cohorte septiembre', html)
        self.assertIn('background:#2f7d4a', html)
        self.assertIn('background:#4a7ea8', html)
        self.assertIn('/admin/novedades-eki/', html)
        self.assertIn(escape('Alitic'), html)
        self.assertNotIn('Cenipalma', html)


class EnvioTests(TestCase):
    @override_settings(EKI_REPORTE_CLIENTES_EMAIL=[])
    def test_sin_correos_no_envia(self):
        with patch('core.reporte_clientes.get_email_service') as mock_svc:
            resultado = enviar_reporte_clientes()
        self.assertEqual(resultado['enviado'], False)
        self.assertEqual(resultado['motivo'], 'sin_destinatarios')
        mock_svc.assert_not_called()

    @override_settings(EKI_REPORTE_CLIENTES_EMAIL=['andres@eki.com'])
    def test_con_correo_envia_html_cohorte(self):
        Cliente.objects.create(
            nombre='Alitic', contacto_principal='A', email='a@x.co',
            telefono='573001200010', activo=True,
        )
        svc = MagicMock()
        svc.send_email.return_value = True
        with patch('core.reporte_clientes.get_email_service', return_value=svc):
            resultado = enviar_reporte_clientes()
        self.assertTrue(resultado['enviado'])
        kwargs = svc.send_email.call_args.kwargs
        self.assertEqual(kwargs['to_emails'], ['andres@eki.com'])
        self.assertIn('cohorte septiembre', kwargs['subject'])
        self.assertIn('novedades-eki', kwargs['html_body'])


class BeatTests(TestCase):
    def test_lunes_ocho_en_cola_masivo(self):
        from celery.schedules import crontab
        from django.conf import settings

        from core.tasks import enviar_reporte_clientes_semanal
        from mvp_project.celery import app

        nombre = 'core.tasks.enviar_reporte_clientes_semanal'
        entrada = app.conf.beat_schedule['reporte-clientes-semanal']
        self.assertEqual(entrada['task'], nombre)
        esperado = crontab(hour=8, minute=0, day_of_week='monday')
        self.assertEqual(entrada['schedule'].hour, esperado.hour)
        self.assertEqual(entrada['schedule'].minute, esperado.minute)
        self.assertEqual(entrada['schedule'].day_of_week, esperado.day_of_week)
        self.assertEqual(settings.CELERY_TASK_ROUTES[nombre]['queue'], 'masivo')
        with patch('core.reporte_clientes.enviar_reporte_clientes', return_value={'enviado': False}) as fn:
            self.assertEqual(enviar_reporte_clientes_semanal(), {'enviado': False})
        fn.assert_called_once_with()
