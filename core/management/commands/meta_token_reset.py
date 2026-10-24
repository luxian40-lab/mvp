"""Borra la bandera de token Meta inválido. No imprime el token."""
from django.core.management.base import BaseCommand

from core.meta_token import CLAVE_TOKEN_INVALIDO


class Command(BaseCommand):
    help = 'Quita la bandera eki:meta:token_invalido.'

    def handle(self, *args, **options):
        from core.locks import _cliente_redis

        try:
            _cliente_redis(socket_connect_timeout=0.4, socket_timeout=0.4).delete(CLAVE_TOKEN_INVALIDO)
        except Exception as exc:
            self.stderr.write(f'no se pudo borrar la bandera: {exc.__class__.__name__}')
            return
        self.stdout.write('bandera_token_borrada')
