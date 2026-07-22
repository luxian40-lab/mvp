"""Qué secciones del portal B2B muestra cada organización."""

from __future__ import annotations

from functools import wraps

from django.shortcuts import redirect

MODULOS_VALIDOS = frozenset({'cursos', 'gei', 'nat', 'empleabilidad'})

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


def org_tiene_gei_operativo(org) -> bool:
    """GEI activo si hay ficha/formulario en cursos de la org (aunque portal_productos no liste gei)."""
    if not org or not getattr(org, 'pk', None):
        return False
    try:
        from core.models import Curso

        if Curso.objects.filter(
            cliente_id=org.pk,
            tiene_formulario_gei=True,
        ).exists():
            return True
    except Exception:
        pass
    try:
        from formulario.models import TipoFormulario

        if TipoFormulario.objects.filter(curso__cliente_id=org.pk).exists():
            return True
    except Exception:
        pass
    try:
        from formulario.models import FichaGEI

        if FichaGEI.objects.filter(cliente_id=org.pk).exists():
            return True
    except Exception:
        pass
    return False


def puede_editar_config_gei_portal(portal_usuario) -> bool:
    return getattr(portal_usuario, 'rol', None) in ('admin', 'profesor')


def modulos_portal(org) -> dict[str, bool]:
    """
    Módulos activos en el portal.
    Si `portal_productos` tiene valores (ej. "cursos,gei"), manda sobre tipo_proyecto.
    Si está vacío, usa solo el tipo de producto principal.
    """
    explicit = _parse_portal_productos(getattr(org, 'portal_productos', '') or '')
    if explicit:
        result = {m: m in explicit for m in MODULOS_VALIDOS}
        if org_tiene_gei_operativo(org):
            result['gei'] = True
        return result

    principal = (getattr(org, 'tipo_proyecto', None) or 'cursos').lower()
    result = {
        'cursos': principal == 'cursos',
        'gei': principal == 'gei',
        'nat': principal == 'nat',
        'empleabilidad': False,
    }
    if org_tiene_gei_operativo(org):
        result['gei'] = True
    return result


def portal_solo_nat(org) -> bool:
    """Organización con contrato únicamente Nat (Knowledge Hub)."""
    mods = modulos_portal(org)
    return (
        mods.get('nat')
        and not mods.get('cursos')
        and not mods.get('gei')
        and not mods.get('empleabilidad')
    )


def portal_home_url(org) -> str:
    if portal_solo_nat(org):
        return '/portal/nat/'
    return '/portal/dashboard/'


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
    """Redirige al home del portal si el módulo no está contratado para la organización."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.contrib import messages

            org = getattr(getattr(request, 'portal_usuario', None), 'organizacion', None)
            if not org or not modulos_portal(org).get(modulo):
                messages.warning(
                    request,
                    'Ese módulo no está disponible para su organización.',
                )
                return redirect(portal_home_url(org) if org else '/portal/login/')
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
