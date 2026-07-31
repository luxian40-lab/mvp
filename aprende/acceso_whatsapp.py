"""Acceso web a Aprende iniciado desde WhatsApp (no OTP saliente en frío).

Twilio no puede enviar texto libre a un número que no ha escrito reciente
(ventana 24h / plantilla Meta). Por eso el estudiante escribe *aula* al bot
y eki responde *dentro* de esa conversación con enlace firmado + código.

El código se guarda en BD (no LocMem) para que cualquier worker de gunicorn
pueda validarlo al POST de login.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

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


def mensaje_pide_acceso_aula(texto: str) -> bool:
    t = (texto or '').strip()
    if not t or len(t) > 80:
        return False
    return bool(_KEYWORDS.match(t))


def generar_codigo() -> str:
    import secrets
    return f'{secrets.randbelow(1_000_000):06d}'


def emitir_acceso_desde_whatsapp(estudiante) -> str:
    """Genera código + enlace handoff. Solo llamar tras mensaje inbound del alumno."""
    from aprende.models import CodigoAccesoAprende
    from studio.aprende_bridge import url_handoff_aprende

    # Limpiar códigos vencidos del mismo estudiante
    corte = timezone.now() - timedelta(seconds=_ttl())
    CodigoAccesoAprende.objects.filter(estudiante=estudiante, creado__lt=corte).delete()
    CodigoAccesoAprende.objects.filter(estudiante=estudiante).delete()

    codigo = generar_codigo()
    for _ in range(8):
        if not CodigoAccesoAprende.objects.filter(codigo=codigo).exists():
            break
        codigo = generar_codigo()

    CodigoAccesoAprende.objects.create(codigo=codigo, estudiante=estudiante)
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
    from aprende.models import CodigoAccesoAprende

    raw = re.sub(r'\D', '', (codigo or '').strip())
    if len(raw) != 6:
        return None, 'El código debe tener 6 dígitos.'

    row = (
        CodigoAccesoAprende.objects.select_related('estudiante')
        .filter(codigo=raw)
        .first()
    )
    if not row:
        return None, 'Código inválido o vencido. Escribe *aula* por WhatsApp para pedir uno nuevo.'

    if row.creado < timezone.now() - timedelta(seconds=_ttl()):
        row.delete()
        return None, 'Código inválido o vencido. Escribe *aula* por WhatsApp para pedir uno nuevo.'

    eid = int(row.estudiante_id)
    row.delete()
    return eid, ''


def next_aprende_seguro(raw: Optional[str]) -> str:
    nxt = (raw or '').strip() or '/aprende/estudiante/'
    if not nxt.startswith('/aprende/') or nxt.startswith('//'):
        return '/aprende/estudiante/'
    return nxt
