"""
mvp_project - EKI MVP
Inicializa Celery cuando Django arranca
"""
from __future__ import absolute_import, unicode_literals

# Importar Celery app para que se registre al iniciar Django
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Si Celery no está instalado, continuar sin él
    celery_app = None
    __all__ = ()
