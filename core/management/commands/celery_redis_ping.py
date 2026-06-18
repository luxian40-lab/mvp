"""Comprueba conexión Redis (broker Celery). Uso: python manage.py celery_redis_ping"""

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Ping al broker Redis de Celery (diagnóstico EB/worker/beat).'

    def handle(self, *args, **options):
        url = getattr(settings, 'CELERY_BROKER_URL', '') or ''
        self.stdout.write(f'Broker: {url}')
        try:
            import redis

            client = redis.from_url(url, socket_connect_timeout=3)
            client.ping()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Redis no disponible: {exc}'))
            raise SystemExit(1) from exc
        eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        self.stdout.write(self.style.SUCCESS('Redis OK'))
        self.stdout.write(f'CELERY_TASK_ALWAYS_EAGER={eager}')
