"""Diagnóstico rápido de broker Redis y ruta Chroma (prod/local)."""

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Muestra CELERY_BROKER_URL (enmascarado) y CHROMA_DB_DIR; ping Redis opcional.'

    def add_arguments(self, parser):
        parser.add_argument('--ping', action='store_true', help='Intentar PING a Redis.')

    def handle(self, *args, **options):
        broker = getattr(settings, 'CELERY_BROKER_URL', '') or ''
        backend = getattr(settings, 'CELERY_RESULT_BACKEND', '') or ''
        chroma = getattr(settings, 'CHROMA_DB_DIR', '') or ''
        self.stdout.write(f'CHROMA_DB_DIR={chroma}')
        self.stdout.write(f'CELERY_BROKER_URL={_mask(broker)}')
        self.stdout.write(f'CELERY_RESULT_BACKEND={_mask(backend)}')
        local = broker.startswith('redis://127.') or broker.startswith('redis://localhost')
        self.stdout.write(f'broker_local={local}')

        if options['ping']:
            try:
                import redis
                from urllib.parse import urlparse

                u = urlparse(broker)
                r = redis.Redis(
                    host=u.hostname or '127.0.0.1',
                    port=u.port or 6379,
                    db=int((u.path or '/0').lstrip('/') or 0),
                    socket_connect_timeout=3,
                    ssl=broker.startswith('rediss://'),
                )
                self.stdout.write(self.style.SUCCESS(f'REDIS PING={r.ping()}'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'REDIS PING failed: {exc}'))


def _mask(url: str) -> str:
    if not url:
        return '(vacío)'
    if '@' in url:
        # redis://:pass@host → redis://:***@host
        pre, post = url.split('@', 1)
        if '//' in pre:
            scheme, rest = pre.split('//', 1)
            return f'{scheme}//***@{post}'
    return url
