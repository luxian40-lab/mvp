"""Facade Analytics — reexporta cálculo de métricas desde módulo legacy."""

from django.db.models import Q

from core.metricas_empresa import (
    calcular_metricas_empresa,
    calcular_metricas_nati,
    calcular_semaforo,
    semaforo_label,
)

# EnvioLog: el código de producto escribe ENVIADO / FALLIDO / ERROR (no «exitoso»).
ENVIOLOG_OK = ('ENVIADO', 'enviado', 'exitoso')
ENVIOLOG_FAIL = ('FALLIDO', 'ERROR', 'FAILED', 'fallido', 'error', 'failed')

# WhatsappLog: Twilio callback (sent/delivered/read/failed) + ERROR interno.
def q_enviolog_ok() -> Q:
    q = Q()
    for estado in ENVIOLOG_OK:
        q |= Q(estado__iexact=estado)
    return q


def q_enviolog_fail() -> Q:
    q = Q()
    for estado in ENVIOLOG_FAIL:
        q |= Q(estado__iexact=estado)
    return q


def q_whatsapp_fallo() -> Q:
    return (
        Q(estado__iexact='undelivered')
        | Q(estado__iexact='failed')
        | Q(estado__iexact='error')
    )


def q_whatsapp_ok() -> Q:
    return (
        Q(estado__iexact='sent')
        | Q(estado__iexact='delivered')
        | Q(estado__iexact='read')
    )


__all__ = [
    'calcular_metricas_empresa',
    'calcular_metricas_nati',
    'calcular_semaforo',
    'semaforo_label',
    'ENVIOLOG_OK',
    'ENVIOLOG_FAIL',
    'q_enviolog_ok',
    'q_enviolog_fail',
    'q_whatsapp_fallo',
    'q_whatsapp_ok',
]
