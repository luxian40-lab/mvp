"""Opt-in y opt-out de plantillas. El texto viejo no mencionaba WhatsApp: no se rellena solo."""
from __future__ import annotations

import re

from django.conf import settings
from django.utils import timezone

_OPTOUT = (
    'baja',
    'stop',
    'no mas mensajes',
    'cancelar notificaciones',
)


def es_optout(texto: str) -> bool:
    plano = (texto or '').strip().lower()
    plano = plano.replace('á', 'a').replace('é', 'e')
    for frase in _OPTOUT:
        if re.search(rf'(^|\s){re.escape(frase)}($|\s)', plano):
            return True
    return False


def registrar_optin(estudiante, origen: str) -> None:
    if estudiante is None or estudiante.wa_optout_fecha:
        return
    estudiante.wa_optin_fecha = timezone.now()
    estudiante.wa_optin_version = str(getattr(settings, 'HABEAS_TEXTO_VERSION', '2026-10-04'))
    estudiante.wa_optin_origen = (origen or '')[:32]
    estudiante.save(update_fields=['wa_optin_fecha', 'wa_optin_version', 'wa_optin_origen'])


def registrar_optout(estudiante) -> None:
    estudiante.wa_optout_fecha = timezone.now()
    estudiante.save(update_fields=['wa_optout_fecha'])


def puede_recibir_plantilla(estudiante) -> bool:
    if estudiante is None:
        return False
    if estudiante.wa_optout_fecha:
        return False
    return bool(estudiante.wa_optin_fecha)
