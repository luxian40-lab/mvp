"""Normalización de teléfonos WhatsApp multi-país para emparejar logs y estudiantes."""
from __future__ import annotations

import re

# Prefijos frecuentes LatAm (sin +). Si el número ya los trae, no se reescribe.
_PREFIJOS_LATAM = (
    '503',  # El Salvador
    '502',  # Guatemala
    '504',  # Honduras
    '505',  # Nicaragua
    '506',  # Costa Rica
    '507',  # Panamá
    '52',   # México
    '51',   # Perú
    '56',   # Chile
    '54',   # Argentina
    '57',   # Colombia
    '58',   # Venezuela
    '593',  # Ecuador
    '591',  # Bolivia
    '595',  # Paraguay
    '598',  # Uruguay
    '55',   # Brasil
)


def normalizar_telefono(raw: str) -> str:
    """
    Solo dígitos.
    - Si ya trae código de país LatAm/conocido, se deja.
    - Si son 10 dígitos y empiezan en 3 → móvil Colombia → antepone 57.
    - Otros locales cortos: NO inventar país (el Excel/campaña debe traer código).
    """
    t = re.sub(r'\D', '', (raw or '').strip())
    if not t:
        return t
    for pref in sorted(_PREFIJOS_LATAM, key=len, reverse=True):
        if t.startswith(pref) and len(t) >= len(pref) + 7:
            return t
    if len(t) == 10 and t.startswith('3'):
        return f'57{t}'
    return t


def variantes_telefono(raw: str) -> list[str]:
    """Variantes usadas en WhatsappLog / Estudiante para el mismo número."""
    base = normalizar_telefono(raw)
    if not base:
        return []
    out = {base}
    if base.startswith('57') and len(base) > 2:
        out.add(base[2:])
        out.add(f'+{base}')
    if len(base) == 10:
        out.add(f'57{base}')
    # México a veces se guarda con/sin el 1 tras 52
    if base.startswith('521') and len(base) >= 12:
        out.add('52' + base[3:])
    if base.startswith('52') and not base.startswith('521') and len(base) >= 12:
        out.add('521' + base[2:])
    return sorted(out)
