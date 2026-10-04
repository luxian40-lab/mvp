"""Borra la bandera de token Meta inválido. No imprime el token."""
from django.core.management.base import BaseCommand

from core.meta_token import CLAVE_TOKEN_INVALIDO


class Command(BaseCommand):
    help = 'Quita la bandera eki:meta:token_invalido.'

    def handle(self, *args, **options):
        from redis import Redis
        from django.conf import settings

        url = getattr(settings, 'CELERY_BROKER_URL', None) or 'redis://localhost:6379/0'
        try:
            Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4).delete(CLAVE_TOKEN_INVALIDO)
        except Exception as exc:
            self.stderr.write(f'no se pudo borrar la bandera: {exc.__class__.__name__}')
            return
        self.stdout.write('bandera_token_borrada')
