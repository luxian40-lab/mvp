"""Acceso web a Aprende iniciado desde WhatsApp (no OTP saliente en frío).

Twilio no puede enviar texto libre a un número que no ha escrito reciente
(ventana 24h / plantilla Meta). Por eso el estudiante escribe *aula* al bot
y eki responde *dentro* de esa conversación con enlace firmado + código.
"""

from __future__ import annotations

import logging
import re
import secrets
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_KEYWORDS = re.compile(
    r'^\s*(?:'
    r'aula|aprende|'
    r'entrar\s+(?:al\s+)?aula|'
    r'acceso\s+(?:al\s+)?aula|'
    r'codigo\s+(?:aula|aprende)|'
    r'código\s+(?:aula|aprende)|'
    r'link\s+aula|enlace\s+aula'
    r')\s*$',
    re.IGNORECASE,
)


def _ttl() -> int:
    return int(getattr(settings, 'APRENDE_ACCESO_WA_TTL', 600) or 600)


def _code_key(codigo: str) -> str:
    return f'aprende_wa_acceso:v1:{codigo}'


def mensaje_pide_acceso_aula(texto: str) -> bool:
    t = (texto or '').strip()
    if not t or len(t) > 80:
        return False
    return bool(_KEYWORDS.match(t))


def generar_codigo() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def emitir_acceso_desde_whatsapp(estudiante) -> str:
    """Genera código + enlace handoff. Solo llamar tras mensaje inbound del alumno."""
    from studio.aprende_bridge import url_handoff_aprende

    codigo = generar_codigo()
    # Evitar colisión improbable
    for _ in range(5):
        if not cache.get(_code_key(codigo)):
            break
        codigo = generar_codigo()

    cache.set(_code_key(codigo), int(estudiante.pk), timeout=_ttl())
    url = url_handoff_aprende(
        estudiante_id=int(estudiante.pk),
        next_path='/aprende/estudiante/',
    )
    nombre = (estudiante.nombre or '').split()[0] or 'Hola'
    mins = max(1, _ttl() // 60)
    return (
        f"{nombre}, aquí tienes acceso a *eki Aprende*:\n\n"
        f"🔗 {url}\n\n"
        f"Si abres el aula en otro dispositivo, usa el código: *{codigo}*\n"
        f"(válido {mins} min)\n\n"
        "Cuando quieras seguir el curso por WhatsApp, escribe *listo*.\n\n"
        "No compartas el enlace ni el código."
    )


def verificar_codigo_web(codigo: str) -> tuple[Optional[int], str]:
    raw = re.sub(r'\D', '', (codigo or '').strip())
    if len(raw) != 6:
        return None, 'El código debe tener 6 dígitos.'
    eid = cache.get(_code_key(raw))
    if not eid:
        return None, 'Código inválido o vencido. Escribe *aula* por WhatsApp para pedir uno nuevo.'
    cache.delete(_code_key(raw))
    return int(eid), ''


def next_aprende_seguro(raw: Optional[str]) -> str:
    nxt = (raw or '').strip() or '/aprende/estudiante/'
    if not nxt.startswith('/aprende/') or nxt.startswith('//'):
        return '/aprende/estudiante/'
    return nxt
