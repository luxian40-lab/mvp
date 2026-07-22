"""Tenancy / aislamiento por organización (Cliente).

No es multi-tenant hard (schemas separados): es la capa de scoping que debe
usar portal, ops y APIs para no filtrar datos entre orgs.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet


class OrgRequired(PermissionDenied):
    """Falta organización en el request portal."""


def org_id_of(org_or_id) -> int | None:
    if org_or_id is None:
        return None
    if isinstance(org_or_id, int):
        return org_or_id
    pk = getattr(org_or_id, 'pk', None)
    return int(pk) if pk is not None else None


def _cliente_lookup(field: str) -> str:
    """Normaliza 'cliente' → 'cliente_id'; 'estudiante__cliente' → 'estudiante__cliente_id'."""
    if field.endswith('_id'):
        return field
    if '__' in field:
        return field if field.endswith('_id') else f'{field}_id'
    return f'{field}_id'


def scoped_to_org(qs: QuerySet, org, *, field: str = 'cliente') -> QuerySet:
    """Filtra queryset a una org. field: 'cliente', 'estudiante__cliente', etc."""
    oid = org_id_of(org)
    if oid is None:
        raise OrgRequired('Organización requerida para consultar datos.')
    return qs.filter(**{_cliente_lookup(field): oid})


def assert_same_org(obj, org, *, field: str = 'cliente') -> None:
    """403 si el objeto no pertenece a la org."""
    oid = org_id_of(org)
    if oid is None:
        raise OrgRequired('Organización requerida.')

    if field == 'cliente':
        obj_oid = getattr(obj, 'cliente_id', None)
        if obj_oid is None and hasattr(obj, 'cliente'):
            obj_oid = getattr(obj.cliente, 'pk', None)
    elif '__' in field:
        cur = obj
        for part in field.split('__'):
            cur = getattr(cur, part, None)
            if cur is None:
                break
        obj_oid = getattr(cur, 'pk', cur) if cur is not None else None
    else:
        obj_oid = getattr(obj, f'{field}_id', None) or getattr(
            getattr(obj, field, None), 'pk', None
        )

    if obj_oid is None or int(obj_oid) != int(oid):
        raise PermissionDenied('Recurso de otra organización.')


def portal_org_or_raise(request):
    """Org del portal usuario; falla si no hay sesión portal."""
    pu = getattr(request, 'portal_usuario', None)
    org = getattr(pu, 'organizacion', None) if pu else None
    if not org:
        raise OrgRequired('Sesión portal sin organización.')
    return org


def eki_ops_may_cross_org(request) -> bool:
    """eki_ops puede ver todas las orgs en /portal/ops/."""
    from portal.authz import es_eki_ops

    return es_eki_ops(request)
