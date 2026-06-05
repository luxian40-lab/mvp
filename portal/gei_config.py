"""Formularios GEI visibles/editables por organización en el portal."""

from __future__ import annotations

from django.db.models import Q

from core.models import Cliente


def queryset_formularios_org(org: Cliente):
    from formulario.models import TipoFormulario

    return (
        TipoFormulario.objects.filter(curso__cliente_id=org.pk)
        .filter(Q(cliente_id=org.pk) | Q(cliente__isnull=True))
        .select_related('curso', 'modulo', 'cliente')
        .prefetch_related('flujo_pasos')
        .order_by('curso__nombre', 'nombre')
    )


def formulario_editable_por_org(formulario, org: Cliente) -> bool:
    return formulario.cliente_id == org.pk


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
