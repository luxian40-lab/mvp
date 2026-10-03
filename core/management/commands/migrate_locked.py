"""migrate con pg_advisory_lock en la misma conexión de Postgres."""
from django.core.management.base import BaseCommand

_CANDADO = 727274


def migrate_con_candado(connection, correr):
    """Sostiene el advisory lock en `connection` mientras corre `correr`.

    close() queda anulado en ese lapso para que Django no abra otra sesión
    y suelte el candado antes de terminar.
    """
    if connection.vendor != 'postgresql':
        correr()
        return

    connection.ensure_connection()
    cerrar = connection.close
    connection.close = lambda: None
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [_CANDADO])
        try:
            correr()
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [_CANDADO])
    finally:
        connection.close = cerrar


class Command(BaseCommand):
    help = 'migrate --noinput sosteniendo pg_advisory_lock(727274) en la misma sesión.'

    def handle(self, *args, **options):
        from django.core.management import call_command
        from django.db import connection

        migrate_con_candado(
            connection,
            lambda: call_command('migrate', interactive=False),
        )
