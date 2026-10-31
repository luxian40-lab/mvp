"""Elección pendiente antes de inscribir. No importa nada de core.

La guarda en caché (Redis en producción), por línea y teléfono, dos horas.
Si el caché no responde, el botón trae el id del curso y se inscribe: no
queda un bucle de repreguntas.
"""
from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

BOTON_SI = 'Sí, este'
BOTON_OTRO = 'Otro curso'
ID_OTRO = 'otro_curso'

_SI = frozenset({'si', 'sí', 'si, este', 'sí, este', 'si este', 'sí este'})
_OTRO = frozenset({'otro', 'otro curso', 'no', 'no, otro', 'no otro'})


def _ttl() -> int:
    from django.conf import settings

    try:
        return max(60, int(getattr(settings, 'EKI_CONFIRMA_CURSO_SEG', 7200)))
    except (TypeError, ValueError):
        return 7200


def _clave(telefono: str, linea: str) -> str:
    return f'eki:confirma_curso:{(linea or "").strip()}:{(telefono or "").strip()}'


def _cache(accion: str, *args, **kwargs) -> tuple[bool, object]:
    """(False, None) si Redis no respondió."""
    try:
        return True, getattr(cache, accion)(*args, **kwargs)
    except (ConnectionError, TimeoutError, OSError):
        logger.warning('confirma_curso_cache accion=%s', accion, exc_info=True)
        return False, None


def leer(telefono: str, linea: str) -> str | None:
    """Id pendiente, '' si no hay, None si el caché no respondió."""
    ok, valor = _cache('get', _clave(telefono, linea))
    if not ok:
        return None
    return str(valor or '')


def recordar(telefono: str, linea: str, curso_id: int) -> None:
    _cache('set', _clave(telefono, linea), str(curso_id), timeout=_ttl())


def olvidar(telefono: str, linea: str) -> None:
    _cache('delete', _clave(telefono, linea))


def cuerpo_catalogo(telefono: str, linea: str, body: str, modo: str) -> str:
    """*sí* / *otro* escritos, solo con una pregunta abierta en Formación."""
    texto = (body or '').strip()
    if modo != 'formacion':
        return texto
    bajo = texto.casefold()
    if bajo not in _SI and bajo not in _OTRO:
        return texto
    pendiente = leer(telefono, linea)
    if not pendiente:
        return texto
    if bajo in _OTRO:
        return ID_OTRO
    return f'si_curso_{pendiente}'


def texto_pregunta(nombre: str, cursos_mes: int) -> str:
    titulo = (nombre or 'este curso').strip()
    if cursos_mes == 1:
        aviso = 'Este mes puede elegir un curso. Si confirma, queda en este.'
    else:
        aviso = 'Si confirma, arranca este curso.'
    return f'¿Arrancamos *{titulo}*?\n\n{aviso}'


def decidir(
    accion: str,
    *,
    confirma: bool,
    puede: bool,
    curso_id: int | None,
    abierto: bool,
    pendiente: str | None,
) -> str:
    """'preguntar', 'repetir' o 'inscribir'."""
    if accion == 'confirmar':
        if curso_id is None:
            return 'inscribir'
        if pendiente is None or pendiente == str(curso_id):
            return 'inscribir'
        return 'repetir'
    if accion == 'ver' and confirma and puede and curso_id is not None and not abierto:
        return 'preguntar'
    return 'inscribir'
