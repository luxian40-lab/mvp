"""Postgres de prueba: Docker local, nunca RDS.

settings_test llama esto al armar DATABASES. CI pasa POSTGRES_PORT=5432
(el servicio de GitHub). En el PC el default es 5433 (eki-test-pg).
"""
from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

PUERTO_LOCAL = '5433'


def host_puerto_postgres_prueba(host: str | None, port: str | None, *, default_port: str = PUERTO_LOCAL):
    """Host y puerto para tests. Rechaza RDS. Puerto vacío → 5433."""
    h = (host or 'localhost').strip() or 'localhost'
    if 'rds.amazonaws.com' in h.lower():
        raise ImproperlyConfigured(
            'settings_test no usa RDS. Levante eki-test-pg en el puerto 5433 '
            '(docs/ENTORNO_PRUEBAS_LOCAL.md). El 5432 de esta máquina es otra base.'
        )
    p = (port if port is not None else default_port).strip() or default_port
    return h, p
