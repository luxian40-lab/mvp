"""Tareas de beat: que existan en el worker y que no fallen por un modelo que no existe."""
from datetime import timedelta

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.models import Estudiante, WhatsappLog
from core.models_meta_webhook import MetaWebhookEvento
from core.tasks import generar_reporte_actividad, limpiar_logs_antiguos
from core.webhook_evento import WebhookEventoProcesado


class BeatRegistradoTests(SimpleTestCase):
    def test_toda_tarea_de_beat_esta_en_un_modulo_que_el_worker_importa(self):
        from mvp_project.celery import app

        importados = {'core.tasks'} | set(getattr(settings, 'CELERY_IMPORTS', ()) or ())
        for entrada, spec in app.conf.beat_schedule.items():
            modulo = spec['task'].rsplit('.', 1)[0]
            self.assertIn(modulo, importados, entrada)


class ReporteActividadTests(TestCase):
    def test_cuenta_mensajes_de_la_ultima_hora(self):
        ana = Estudiante.objects.create(nombre='Ana', cedula='990001', telefono='573009990001')
        WhatsappLog.objects.create(telefono='573009990001', mensaje='hola', tipo='INCOMING', estudiante=ana)
        WhatsappLog.objects.create(telefono='573009990001', mensaje='otra', tipo='SENT', estudiante=ana)
        viejo = WhatsappLog.objects.create(telefono='573009990002', mensaje='ayer', tipo='SENT')
        WhatsappLog.objects.filter(pk=viejo.pk).update(fecha=timezone.now() - timedelta(hours=3))
        reporte = generar_reporte_actividad()
        self.assertNotIn('error', reporte)
        self.assertEqual(reporte['mensajes_hora'], 2)
        self.assertEqual(reporte['estudiantes_activos'], 1)
        self.assertEqual(reporte['progreso_actualizado'], 0)


class LimpiezaTests(TestCase):
    def test_purga_eventos_viejos_y_no_toca_whatsapplog(self):
        hace = timezone.now()
        viejo = WebhookEventoProcesado.objects.create(canal='meta', external_id='wamid.viejo')
        nuevo = WebhookEventoProcesado.objects.create(canal='meta', external_id='wamid.nuevo')
        WebhookEventoProcesado.objects.filter(pk=viejo.pk).update(creado=hace - timedelta(days=11))
        meta = MetaWebhookEvento.objects.create(wamid='wamid.meta.viejo', telefono='573009990003')
        MetaWebhookEvento.objects.filter(pk=meta.pk).update(recibido_en=hace - timedelta(days=31))
        log = WhatsappLog.objects.create(telefono='573009990004', mensaje='viejo', tipo='SENT')
        WhatsappLog.objects.filter(pk=log.pk).update(fecha=hace - timedelta(days=200))

        resultado = limpiar_logs_antiguos()

        self.assertFalse(str(resultado).startswith('Error'), resultado)
        self.assertFalse(WebhookEventoProcesado.objects.filter(pk=viejo.pk).exists())
        self.assertTrue(WebhookEventoProcesado.objects.filter(pk=nuevo.pk).exists())
        self.assertFalse(MetaWebhookEvento.objects.filter(pk=meta.pk).exists())
        self.assertTrue(WhatsappLog.objects.filter(pk=log.pk).exists())
