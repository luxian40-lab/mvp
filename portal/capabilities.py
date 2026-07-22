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
    GEI operativo solo se fuerza cuando el contrato ya incluye cursos o gei
    (nunca en orgs solo-Nat).
    """
    explicit = _parse_portal_productos(getattr(org, 'portal_productos', '') or '')
    if explicit:
        result = {m: m in explicit for m in MODULOS_VALIDOS}
        if ('cursos' in explicit or 'gei' in explicit) and org_tiene_gei_operativo(org):
            result['gei'] = True
        return result

    principal = (getattr(org, 'tipo_proyecto', None) or 'cursos').lower()
    result = {
        'cursos': principal == 'cursos',
        'gei': principal == 'gei',
        'nat': principal == 'nat',
        'empleabilidad': False,
    }
    if principal in ('cursos', 'gei') and org_tiene_gei_operativo(org):
        result['gei'] = True
    return result


def productos_contratados(org) -> set[str]:
    """Módulos del contrato (sin auto-activar GEI por fichas legacy)."""
    explicit = _parse_portal_productos(getattr(org, 'portal_productos', '') or '')
    if explicit:
        return explicit
    principal = (getattr(org, 'tipo_proyecto', None) or 'cursos').lower()
    if principal in MODULOS_VALIDOS:
        return {principal}
    return {'cursos'}


def portal_solo_nat(org) -> bool:
    """Organización con contrato únicamente Nat (sin cursos/GEI/empleabilidad)."""
    return productos_contratados(org) == {'nat'}


def portal_home_url(org) -> str:
    if portal_solo_nat(org):
        return '/portal/nat/'
    return '/portal/dashboard/'


def portal_home_url_para_usuario(pu) -> str:
    """Home según rol: eki_ops → /portal/ops/; resto según org."""
    if pu and getattr(pu, 'rol', None) == 'eki_ops':
        return '/portal/ops/'
    org = getattr(pu, 'organizacion', None) if pu else None
    return portal_home_url(org) if org else '/portal/login/'


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
