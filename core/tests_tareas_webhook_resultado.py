"""Las tareas de webhook no guardan resultado: devuelven el HttpResponse de la vista y Celery no lo puede serializar."""
from django.http import HttpResponse
from django.test import SimpleTestCase
from kombu.utils.json import dumps

from core import tasks


class TareasWebhookSinResultadoTests(SimpleTestCase):
    def test_el_httpresponse_de_la_vista_no_se_puede_guardar_como_resultado(self):
        with self.assertRaises(TypeError):
            dumps(HttpResponse('OK'))

    def test_las_tareas_de_webhook_no_guardan_resultado(self):
        for tarea in (
            tasks.procesar_sandbox_meta_async,
            tasks.procesar_twilio_webhook_async,
            tasks.procesar_bot_comercial_webhook_async,
        ):
            with self.subTest(tarea=tarea.name):
                self.assertTrue(tarea.ignore_result)
