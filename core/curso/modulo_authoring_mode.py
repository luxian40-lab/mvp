"""Modo de authoring al crear/editar módulo: clase rápida (A) vs Builder (B)."""
from __future__ import annotations

MODO_CLASE = 'clase'
MODO_BUILDER = 'builder'
MODOS = (MODO_CLASE, MODO_BUILDER)
SESSION_KEY = 'eki_modulo_authoring_mode'

LABELS = {
    MODO_CLASE: 'Subir una clase rápido',
    MODO_BUILDER: 'Armar por partes (WhatsApp)',
}


def normalizar_modo(raw: str | None, *, default: str = MODO_CLASE) -> str:
    m = (raw or '').strip().lower()
    if m in ('a', 'rapido', 'rápido', 'simple', MODO_CLASE):
        return MODO_CLASE
    if m in ('b', 'builder', 'partes', 'wa', MODO_BUILDER):
        return MODO_BUILDER
    return default if default in MODOS else MODO_CLASE


def set_modulo_modo(request, modulo_id, modo: str) -> str:
    modo_n = normalizar_modo(modo)
    data = dict(request.session.get(SESSION_KEY) or {})
    data[str(modulo_id)] = modo_n
    request.session[SESSION_KEY] = data
    try:
        request.session.modified = True
    except Exception:
        pass
    return modo_n


def get_modulo_modo(request, modulo_id, default: str | None = None) -> str | None:
    data = request.session.get(SESSION_KEY) or {}
    raw = data.get(str(modulo_id))
    if raw:
        return normalizar_modo(raw)
    if default is None:
        return None
    return normalizar_modo(default)


def resolver_modo_desde_request(request, modulo_id=None, *, default: str = MODO_CLASE) -> str:
    """Prioridad: GET ?modo= → POST modo_creacion → sesión → default."""
    q = request.GET.get('modo') if hasattr(request, 'GET') else None
    if q:
        return normalizar_modo(q, default=default)
    post = getattr(request, 'POST', None)
    if post is not None and post.get('modo_creacion'):
        return normalizar_modo(post.get('modo_creacion'), default=default)
    if modulo_id is not None:
        ses = get_modulo_modo(request, modulo_id)
        if ses:
            return ses
    return normalizar_modo(default)
