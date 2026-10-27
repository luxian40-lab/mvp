"""Normalización de teléfonos WhatsApp multi-país para emparejar logs y estudiantes."""
from __future__ import annotations

import re

from core.canal.telefono import (  # noqa: F401
    _PREFIJOS_PAIS,
    normalizar_telefono,
    validar_telefono_whatsapp,
    variantes_telefono,
)

# Compat imports / tests antiguos
_PREFIJOS_LATAM = _PREFIJOS_PAIS


def normalizar_e164_co(numero: str) -> str:
    """Colombia a dígitos con 57.

    Acepta +57…, 57…, 0057…, espacios y guiones. Un móvil de 10 dígitos
    recibe el 57. No inventa país si el número ya trae otro prefijo.
    """
    limpio = re.sub(r'\D', '', str(numero or ''))
    if limpio.startswith('0057'):
        limpio = limpio[2:]
    if len(limpio) == 10:
        limpio = f'57{limpio}'
    return limpio


def explicar_error_envio_whatsapp(respuesta_api: str | None, estado: str | None = None) -> str:
    """Traduce códigos Twilio frecuentes a lenguaje operativo."""
    txt = (respuesta_api or '') + ' ' + (estado or '')
    low = txt.lower()
    if '63049' in low:
        return 'WhatsApp no entregó el mensaje (límite / tipo marketing).'
    if '63024' in low:
        return 'Número inválido o no tiene WhatsApp.'
    if '63032' in low:
        return 'Esa persona no puede recibir de este negocio (bloqueo / canal).'
    if '63016' in low or '63005' in low:
        return 'Plantilla o canal rechazó el contenido.'
    if '21614' in low or 'invalid' in low and 'phone' in low:
        return 'Teléfono no válido para WhatsApp.'
    if (estado or '').upper() in ('ENVIADO', 'OK', 'EXITOSO'):
        return 'Enviado.'
    if (estado or '').upper() in ('FALLIDO', 'ERROR', 'FAILED'):
        snippet = (respuesta_api or '').strip()
        if snippet:
            return snippet[:120]
        return 'Falló el envío.'
    return (respuesta_api or estado or 'Sin detalle')[:120]


def estudiante_por_telefono(telefono: str):
    """Ficha más reciente cuyo teléfono coincida en E.164 o en 10 dígitos locales."""
    from core.models.estudiantes import estudiante_por_telefono as buscar

    return buscar(telefono)
