"""Borra la bandera de token Meta inválido. Solo quien tiene shell de staff."""
from django.core.management.base import BaseCommand

from core.meta_token import CLAVE_TOKEN_INVALIDO


class Command(BaseCommand):
    help = 'Borra eki:meta:token_invalido. Comando de staff en el servidor, no es un endpoint.'

    def handle(self, *args, **options):
        from core.locks import _cliente_redis

        _cliente_redis().delete(CLAVE_TOKEN_INVALIDO)
        self.stdout.write('eki:meta:token_invalido borrada')
