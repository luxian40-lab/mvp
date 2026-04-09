"""
Configuración de Celery para EKI MVP
Maneja tareas asíncronas: certificados, campañas, gamificación, reportes
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Establecer settings de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

app = Celery('eki_mvp')

# Leer configuración desde settings.py con prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tasks en todas las apps de Django
app.autodiscover_tasks()

# ==========================================
# TAREAS PROGRAMADAS (Celery Beat)
# ==========================================
app.conf.beat_schedule = {
    # Enviar campañas programadas cada 5 minutos
    'enviar-campanhas-programadas': {
        'task': 'core.tasks.enviar_campanas_programadas',
        'schedule': 300.0,  # cada 5 minutos
    },
    # Generar reporte de actividad cada hora
    'reporte-actividad-hora': {
        'task': 'core.tasks.generar_reporte_actividad',
        'schedule': 3600.0,  # cada hora
    },
    # Limpiar logs antiguos a las 2 AM
    'limpiar-logs-antiguos': {
        'task': 'core.tasks.limpiar_logs_antiguos',
        'schedule': crontab(hour=2, minute=0),
    },
    # Reenganche de módulos drip (diario 8:00 AM)
    'reenganche-drip-diario': {
        'task': 'core.tasks.reenganche_drip_content_diario',
        'schedule': crontab(hour=8, minute=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Task de prueba para verificar que Celery funciona."""
    print(f'Request: {self.request!r}')
