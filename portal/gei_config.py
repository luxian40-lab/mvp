"""Formularios GEI visibles/editables por organización en el portal."""

from __future__ import annotations

from django.db.models import Q

from core.models import Cliente

from .capabilities import puede_editar_config_gei_portal


def queryset_formularios_org(org: Cliente):
    from formulario.models import TipoFormulario

    return (
        TipoFormulario.objects.filter(curso__cliente_id=org.pk)
        .filter(Q(cliente_id=org.pk) | Q(cliente__isnull=True))
        .select_related('curso', 'modulo', 'cliente')
        .prefetch_related('flujo_pasos')
        .order_by('curso__nombre', 'nombre')
    )


def formulario_editable_por_org(formulario, org: Cliente, *, portal_usuario=None) -> bool:
    if formulario.curso.cliente_id != org.pk:
        return False
    if portal_usuario is not None and not puede_editar_config_gei_portal(portal_usuario):
        return False
    # Admin/profesor: formulario propio o plantilla global eki del curso de la org.
    return formulario.cliente_id in (org.pk, None)


def obtener_formulario_org(formulario_id: int, org: Cliente):
    from formulario.models import TipoFormulario

    return (
        TipoFormulario.objects.filter(
            pk=formulario_id,
            curso__cliente_id=org.pk,
        )
        .filter(Q(cliente_id=org.pk) | Q(cliente__isnull=True))
        .select_related('curso', 'modulo', 'cliente')
        .prefetch_related('flujo_pasos')
        .first()
    )
