"""Fase I1: con EKI_COLAS_POR_TIPO prendido, toda ruta tiene consumidor."""
import os
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


def _colas_escuchadas():
    worker = Path('scripts/run_worker.sh').read_text(encoding='utf-8')
    rag = Path('scripts/run_worker_rag.sh').read_text(encoding='utf-8')
    defecto_worker = re.search(r'CELERY_QUEUES:-([^}"\s]+)', worker).group(1)
    defecto_rag = re.search(r'CELERY_QUEUES_RAG:-([^}"\s]+)', rag).group(1)
    return set(defecto_worker.split(',')) | set(defecto_rag.split(','))


class ColasPorTipoTests(SimpleTestCase):
    def test_con_el_flag_toda_ruta_tiene_consumidor_y_cola_declarada(self):
        rutas = {**settings.CELERY_TASK_ROUTES, **settings.CELERY_RUTAS_POR_TIPO}
        escuchadas = _colas_escuchadas()
        for nombre, spec in rutas.items():
            self.assertIn(spec['queue'], escuchadas, nombre)
            self.assertIn(spec['queue'], settings.CELERY_TASK_QUEUES, nombre)

    def test_rutas_por_tipo_apuntan_a_tareas_que_existen(self):
        from core import tasks

        self.assertEqual(
            settings.CELERY_RUTAS_POR_TIPO,
            {
                'core.tasks.generar_certificado_async': {'queue': 'certificados'},
                'core.tasks.generar_curso_ia_async': {'queue': 'llm'},
            },
        )
        for nombre in settings.CELERY_RUTAS_POR_TIPO:
            self.assertEqual(getattr(tasks, nombre.rsplit('.', 1)[1]).name, nombre)

    def test_sin_el_flag_las_rutas_no_cambian(self):
        if os.environ.get('EKI_COLAS_POR_TIPO'):
            self.skipTest('EKI_COLAS_POR_TIPO definido en el entorno')
        self.assertFalse(settings.EKI_COLAS_POR_TIPO)
        for nombre in settings.CELERY_RUTAS_POR_TIPO:
            self.assertNotIn(nombre, settings.CELERY_TASK_ROUTES)
