"""Estado de colas Celery (rápida vs indexación RAG). Uso: python manage.py celery_cola_rag"""

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Muestra tareas pendientes en colas celery y rag_index.'

    def handle(self, *args, **options):
        url = getattr(settings, 'CELERY_BROKER_URL', '') or ''
        self.stdout.write(f'Broker: {url}')
        eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        if eager:
            self.stdout.write(self.style.WARNING('CELERY_TASK_ALWAYS_EAGER=True (sin cola real)'))
            return

        try:
            import redis

            client = redis.from_url(url, socket_connect_timeout=3)
            client.ping()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Redis no disponible: {exc}'))
            raise SystemExit(1) from exc

        for cola in ('celery', 'rag_index'):
            try:
                pendientes = client.llen(cola)
            except Exception:
                pendientes = '?'
            self.stdout.write(f'  {cola}: {pendientes} tarea(s) en cola')

        try:
            from celery import current_app

            insp = current_app.control.inspect(timeout=3)
            activos = insp.active() or {}
            rag_activos = 0
            for _worker, tareas in activos.items():
                for t in tareas or []:
                    if t.get('name', '').endswith(('indexar_biblioteca_nat_por_id',
                                                   'indexar_documento_rag_por_id',
                                                   'procesar_zip_rag_comercial')):
                        rag_activos += 1
            self.stdout.write(f'  rag_index (ejecutando ahora): {rag_activos}')
        except Exception as exc:
            self.stdout.write(f'  (inspect Celery no disponible: {exc})')
