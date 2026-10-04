"""Sentry solo si hay DSN. Sin DSN no hace nada. No manda teléfonos ni cuerpos."""
from __future__ import annotations

import os
import re

_TELEFONO = re.compile(r'(?<!\d)\+?57\d{10}(?!\d)')
_CEDULA = re.compile(r'(?i)\b(?:cc|cedula|cédula|nit)\s*[:#]?\s*\d{5,12}\b')
_CABECERAS = {'authorization', 'cookie', 'x-eki-infra-token'}


def _limpiar_texto(texto: str) -> str:
    texto = _TELEFONO.sub('[telefono]', texto)
    return _CEDULA.sub('[documento]', texto)


def _caminar(valor):
    if isinstance(valor, str):
        return _limpiar_texto(valor)
    if isinstance(valor, list):
        return [_caminar(item) for item in valor]
    if isinstance(valor, dict):
        return {clave: _caminar(item) for clave, item in valor.items()}
    return valor


def limpiar_evento(event: dict) -> dict:
    if not isinstance(event, dict):
        return event
    event = _caminar(event)
    pedido = event.get('request')
    if isinstance(pedido, dict):
        pedido['data'] = '[omitido]'
        cabeceras = pedido.get('headers')
        if isinstance(cabeceras, dict):
            for clave in list(cabeceras):
                if str(clave).lower() in _CABECERAS:
                    cabeceras[clave] = '[omitido]'
    return event


def before_send(event, hint):
    return limpiar_evento(event)


def iniciar_sentry() -> bool:
    dsn = (os.environ.get('SENTRY_DSN') or '').strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError:
        return False
    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=False,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        before_send=before_send,
    )
    return True
