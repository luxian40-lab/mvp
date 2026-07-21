"""Puente firmado Studio → Aprende (sin cookie compartida)."""

from __future__ import annotations

from django.core import signing
from django.urls import reverse

from core.host_isolation import absolute_path

HANDOFF_SALT = 'eki-aprende-handoff-v1'
HANDOFF_MAX_AGE = 300  # 5 minutos


def crear_token_handoff(*, estudiante_id: int, next_path: str = '/aprende/estudiante/') -> str:
    next_path = (next_path or '/aprende/estudiante/').strip() or '/aprende/estudiante/'
    if not next_path.startswith('/aprende/'):
        next_path = '/aprende/estudiante/'
    return signing.dumps(
        {'eid': int(estudiante_id), 'next': next_path},
        salt=HANDOFF_SALT,
        compress=True,
    )


def consumir_token_handoff(token: str) -> tuple[int, str]:
    data = signing.loads(token, salt=HANDOFF_SALT, max_age=HANDOFF_MAX_AGE)
    eid = int(data['eid'])
    next_path = (data.get('next') or '/aprende/estudiante/').strip()
    if not next_path.startswith('/aprende/'):
        next_path = '/aprende/estudiante/'
    return eid, next_path


def url_handoff_aprende(*, estudiante_id: int, next_path: str = '/aprende/estudiante/', request=None) -> str:
    token = crear_token_handoff(estudiante_id=estudiante_id, next_path=next_path)
    try:
        path = reverse('aprende_handoff')
    except Exception:
        path = '/aprende/handoff/'
    sep = '&' if '?' in path else '?'
    return absolute_path('aprende', f'{path}{sep}t={token}', request=request)
