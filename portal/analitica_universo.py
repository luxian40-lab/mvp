"""Universo de personas para analítica del portal.

No cuentan teléfonos de prueba/hook ni, si la org ya tiene cohorte de
flow de registro, quienes entraron por otro camino (p. ej. habeas de smoke).
"""
from __future__ import annotations

from django.conf import settings
from django.db.models import Q, QuerySet

from core.models import Estudiante


def _digitos(valor: str) -> str:
    return ''.join(c for c in (valor or '') if c.isdigit())


def telefonos_excluidos_analitica() -> list[str]:
    """Números de prueba (campaña) más extras de EKI_ANALITICA_EXCLUIR_TELEFONOS."""
    vistos: list[str] = []
    bruto = list(getattr(settings, 'EKI_CAMPANA_META_PRUEBA_NUMEROS', None) or [])
    extra = getattr(settings, 'EKI_ANALITICA_EXCLUIR_TELEFONOS', None) or []
    if isinstance(extra, str):
        extra = [p.strip() for p in extra.split(',') if p.strip()]
    for parte in list(bruto) + list(extra):
        d = _digitos(str(parte))
        if d and d not in vistos:
            vistos.append(d)
    return vistos


def q_excluye_telefonos_prueba(campo: str = 'telefono') -> Q:
    """Q que deja fuera los teléfonos de prueba (E.164 o celular local)."""
    excluir = Q()
    for tel in telefonos_excluidos_analitica():
        variantes = {tel}
        if len(tel) >= 10:
            variantes.add(tel[-10:])
        if tel.startswith('57') and len(tel) > 2:
            variantes.add(tel[2:])
        for v in variantes:
            excluir |= Q(**{f'{campo}__endswith': v})
    return ~excluir if excluir else Q()


def estudiantes_analitica(org) -> QuerySet:
    """Activos de la org para cajas de Uso / cursos: sin hooks; flow si ya hay cohorte."""
    qs = Estudiante.objects.filter(cliente=org, activo=True).filter(
        q_excluye_telefonos_prueba('telefono'),
    )
    con_flow = qs.filter(wa_optin_origen='flow_registro')
    if con_flow.exists():
        return con_flow
    return qs


def ids_estudiantes_analitica(org) -> set[int]:
    return set(estudiantes_analitica(org).values_list('id', flat=True))


def filtrar_estudiante_fk(qs: QuerySet, org, *, prefijo: str = 'estudiante') -> QuerySet:
    """Aplica el mismo universo a querysets con FK a Estudiante."""
    ids = ids_estudiantes_analitica(org)
    if not ids:
        return qs.none()
    return qs.filter(**{f'{prefijo}_id__in': ids})
