"""Puente firmado Studio/WhatsApp → Aprende (sin cookie compartida entre hosts)."""

from __future__ import annotations

from django.core import signing
from django.urls import reverse

from aprende.session_auth import VIA_STUDIO, VIA_WHATSAPP, VIAS_ESTUDIANTE
from core.host_isolation import absolute_path

HANDOFF_SALT = 'eki-aprende-handoff-v1'
HANDOFF_MAX_AGE = 300  # 5 minutos


def crear_token_handoff(
    *,
    estudiante_id: int,
    next_path: str = '/aprende/estudiante/',
    via: str = VIA_STUDIO,
) -> str:
    next_path = (next_path or '/aprende/estudiante/').strip() or '/aprende/estudiante/'
    if not next_path.startswith('/aprende/'):
        next_path = '/aprende/estudiante/'
    via_n = (via or VIA_STUDIO).strip().lower()
    if via_n not in VIAS_ESTUDIANTE:
        via_n = VIA_STUDIO
    return signing.dumps(
        {'eid': int(estudiante_id), 'next': next_path, 'via': via_n},
        salt=HANDOFF_SALT,
        compress=True,
    )


def consumir_token_handoff(token: str) -> tuple[int, str, str]:
    """Devuelve (estudiante_id, next_path, via). via: whatsapp | studio."""
    data = signing.loads(token, salt=HANDOFF_SALT, max_age=HANDOFF_MAX_AGE)
    eid = int(data['eid'])
    next_path = (data.get('next') or '/aprende/estudiante/').strip()
    if not next_path.startswith('/aprende/'):
        next_path = '/aprende/estudiante/'
    via = (data.get('via') or VIA_STUDIO).strip().lower()
    if via not in VIAS_ESTUDIANTE:
        via = VIA_STUDIO
    return eid, next_path, via


def url_handoff_aprende(
    *,
    estudiante_id: int,
    next_path: str = '/aprende/estudiante/',
    request=None,
    via: str = VIA_STUDIO,
) -> str:
    token = crear_token_handoff(estudiante_id=estudiante_id, next_path=next_path, via=via)
    try:
        path = reverse('aprende_handoff')
    except Exception:
        path = '/aprende/handoff/'
    sep = '&' if '?' in path else '?'
    return absolute_path('aprende', f'{path}{sep}t={token}', request=request)
