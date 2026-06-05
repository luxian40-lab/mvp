"""Qué secciones del portal B2B muestra cada organización."""

from __future__ import annotations

from functools import wraps

from django.shortcuts import redirect

MODULOS_VALIDOS = frozenset({'cursos', 'gei', 'nat'})

CATEGORIAS_POR_TIPO_PROYECTO = {
    'cursos': [
        'duda_modulo',
        'problema_acceso',
        'solicitud_certificado',
        'contenido',
        'acceso',
        'otro',
        '',
    ],
    'gei': [
        'consulta_calculo',
        'correccion_datos',
        'problema_tecnico',
        'tecnico',
        'otro',
        '',
    ],
    'nat': [
        'conversacion_escalada',
        'pregunta_sin_respuesta',
        'queja',
        'otro',
        '',
    ],
}


def _parse_portal_productos(raw: str) -> set[str]:
    return {
        p.strip().lower()
        for p in (raw or '').split(',')
        if p.strip().lower() in MODULOS_VALIDOS
    }


def modulos_portal(org) -> dict[str, bool]:
    """
    Módulos activos en el portal.
    Si `portal_productos` tiene valores (ej. "cursos,gei"), manda sobre tipo_proyecto.
    Si está vacío, usa solo el tipo de producto principal.
    """
    explicit = _parse_portal_productos(getattr(org, 'portal_productos', '') or '')
    if explicit:
        return {m: m in explicit for m in MODULOS_VALIDOS}

    principal = (getattr(org, 'tipo_proyecto', None) or 'cursos').lower()
    return {
        'cursos': principal == 'cursos',
        'gei': principal == 'gei',
        'nat': principal == 'nat',
    }


def categorias_pqrs_portal(org) -> list[str] | None:
    """Unión de categorías PQRS según módulos activos; None = sin filtrar."""
    mods = modulos_portal(org)
    cats: list[str] = []
    for key in ('cursos', 'gei', 'nat'):
        if mods.get(key):
            cats.extend(CATEGORIAS_POR_TIPO_PROYECTO.get(key, []))
    if not cats:
        return None
    return list(dict.fromkeys(cats))


def requiere_modulo(modulo: str):
    """Redirige al dashboard si el módulo no está contratado para la organización."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            org = getattr(getattr(request, 'portal_usuario', None), 'organizacion', None)
            if not org or not modulos_portal(org).get(modulo):
                return redirect('/portal/dashboard/')
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
