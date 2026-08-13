"""Normalización de teléfonos WhatsApp multi-país para emparejar logs y estudiantes."""
from __future__ import annotations

import re
from typing import Any

# Prefijos frecuentes LatAm + algunos internacionales (sin +).
# Si el número ya los trae, no se reescribe.
_PREFIJOS_PAIS = (
    '503',  # El Salvador
    '502',  # Guatemala
    '504',  # Honduras
    '505',  # Nicaragua
    '506',  # Costa Rica
    '507',  # Panamá
    '593',  # Ecuador
    '591',  # Bolivia
    '595',  # Paraguay
    '598',  # Uruguay
    '52',   # México
    '51',   # Perú
    '56',   # Chile
    '54',   # Argentina
    '57',   # Colombia
    '58',   # Venezuela
    '55',   # Brasil
    '34',   # España
    '33',   # Francia
    '39',   # Italia
    '44',   # Reino Unido
    '49',   # Alemania
    '351',  # Portugal
    '1',    # NANP (EE.UU. / Canadá) — solo con longitud típica 11
)

# Compat imports / tests antiguos
_PREFIJOS_LATAM = _PREFIJOS_PAIS


def normalizar_telefono(raw: str) -> str:
    """
    Solo dígitos.
    - Si ya trae código de país conocido, se deja.
    - Si son 10 dígitos y empiezan en 3 → móvil Colombia → antepone 57.
    - Otros locales cortos: NO inventar país (el Excel/campaña debe traer código).
    """
    t = re.sub(r'\D', '', (raw or '').strip())
    if not t:
        return t
    for pref in sorted(_PREFIJOS_PAIS, key=len, reverse=True):
        if pref == '1':
            if t.startswith('1') and len(t) == 11:
                return t
            continue
        # Evitar falsos positivos: "55…" / "52…" de 10 dígitos sin ser BR/MX reales
        min_total = len(pref) + 8
        if pref in ('55', '52', '54', '51', '56', '58'):
            min_total = max(min_total, 12)
        if t.startswith(pref) and len(t) >= min_total:
            return t
    if len(t) == 10 and t.startswith('3'):
        return f'57{t}'
    return t


def validar_telefono_whatsapp(raw: str) -> dict[str, Any]:
    """
    Valida para alta/Excel/campaña. Internacional-friendly.

    Returns:
      ok (bool), severity ('ok'|'warn'|'error'), telefono (str normalizado),
      mensaje (str en español para la operadora).
    """
    bruto = (raw or '').strip()
    digits = re.sub(r'\D', '', bruto)
    if not digits:
        return {
            'ok': False,
            'severity': 'error',
            'telefono': '',
            'mensaje': 'Teléfono vacío.',
        }

    norm = normalizar_telefono(bruto)

    # Colombia: 57 + 10 dígitos (móvil suele empezar en 3)
    if norm.startswith('57'):
        local = norm[2:]
        if len(norm) != 12 or not local.isdigit():
            return {
                'ok': False,
                'severity': 'error',
                'telefono': norm,
                'mensaje': (
                    f'Número Colombia incompleto o raro ({bruto}). '
                    'Use 10 dígitos (ej. 3101234567) o 57 + 10 dígitos.'
                ),
            }
        if not local.startswith('3'):
            return {
                'ok': True,
                'severity': 'warn',
                'telefono': norm,
                'mensaje': 'Colombia sin móvil típico (no empieza en 3). Revise si es correcto.',
            }
        return {'ok': True, 'severity': 'ok', 'telefono': norm, 'mensaje': 'Listo.'}

    # Prefijo país conocido + cuerpo suficiente (E.164 ≤ 15)
    for pref in sorted(_PREFIJOS_PAIS, key=len, reverse=True):
        if pref == '57':
            continue
        if pref == '1':
            if norm.startswith('1') and len(norm) == 11:
                return {'ok': True, 'severity': 'ok', 'telefono': norm, 'mensaje': 'Listo (EE.UU./Canadá).'}
            continue
        min_total = len(pref) + 8
        if pref in ('55', '52', '54', '51', '56', '58'):
            min_total = max(min_total, 12)
        if norm.startswith(pref) and min_total <= len(norm) <= 15:
            return {
                'ok': True,
                'severity': 'ok',
                'telefono': norm,
                'mensaje': 'Listo (internacional).',
            }

    # 10 dígitos que no son móvil CO → pedir país
    if len(digits) == 10 and not digits.startswith('3'):
        return {
            'ok': False,
            'severity': 'error',
            'telefono': norm,
            'mensaje': (
                f'Falta código de país en «{bruto}». '
                'Ej.: 52155… (MX), 519… (PE), 346… (ES), 57300… (CO).'
            ),
        }

    if 8 <= len(norm) <= 9:
        return {
            'ok': False,
            'severity': 'error',
            'telefono': norm,
            'mensaje': (
                f'Teléfono corto «{bruto}». Agregue código de país '
                '(Colombia: 57; México: 52; etc.).'
            ),
        }

    if 11 <= len(norm) <= 15:
        return {
            'ok': True,
            'severity': 'warn',
            'telefono': norm,
            'mensaje': 'Se guardará tal cual; confirme que el código de país sea correcto.',
        }

    if len(norm) > 15:
        return {
            'ok': False,
            'severity': 'error',
            'telefono': norm,
            'mensaje': f'Teléfono demasiado largo ({bruto}).',
        }

    return {
        'ok': False,
        'severity': 'error',
        'telefono': norm,
        'mensaje': f'Teléfono no válido para WhatsApp: «{bruto}».',
    }


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
