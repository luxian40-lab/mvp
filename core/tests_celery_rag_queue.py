from django.conf import settings
from django.test import SimpleTestCase


class CeleryRagQueueRoutesTests(SimpleTestCase):
    def test_rag_tasks_usan_cola_dedicada(self):
        routes = getattr(settings, 'CELERY_TASK_ROUTES', {})
        self.assertEqual(
            routes['core.tasks.indexar_biblioteca_nat_por_id']['queue'],
            'rag_index',
        )
        self.assertEqual(
            routes['core.tasks.indexar_documento_rag_por_id']['queue'],
            'rag_index',
        )
        self.assertEqual(
            routes['core.tasks.procesar_zip_rag_comercial']['queue'],
            'rag_index',
        )

    def test_cola_rag_index_definida(self):
        queues = getattr(settings, 'CELERY_TASK_QUEUES', {})
        self.assertIn('rag_index', queues)
        self.assertIn('celery', queues)
