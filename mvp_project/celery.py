"""
Configuración de Celery para EKI MVP
Maneja tareas asíncronas: certificados, campañas, gamificación, reportes
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# En EB el web usa settings_production; el worker debe igual (NAT_WEBHOOK / Redis).
if os.environ.get('AWS_EXECUTION_ENV') or os.path.exists('/var/app/current'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production')
else:
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
    # Estado PENDING/IN_APPEAL de Plantilla Meta (Graph). No toca campañas Twilio.
    'sincronizar-plantillas-meta': {
        'task': 'core.tasks.sincronizar_plantillas_meta',
        'schedule': 600.0,
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
    # Reenganche drip (08:00). Solo Graph si META_REENGANCHE_ENABLED. Plantilla: META_TEMPLATE_DRIP_REENGANCHE.
    'reenganche-drip-diario': {
        'task': 'core.tasks.reenganche_drip_content_diario',
        'schedule': crontab(hour=8, minute=0),
    },
    # Advisor de infra (reglas): snapshot + email si overall → ACTUAR.
    'revisar-infra-advisor': {
        'task': 'core.tasks_infra.revisar_infra_advisor',
        'schedule': crontab(minute=15),  # cada hora a :15
    },
    # Cluster territorial v0 + reintento del data lake (outbox sin published_at).
    'correlacionar-alertas-territoriales': {
        'task': 'core.tasks.correlacionar_alertas_territoriales',
        'schedule': crontab(minute=20),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Task de prueba para verificar que Celery funciona."""
    print(f'Request: {self.request!r}')
