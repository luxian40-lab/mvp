"""Cursos que ofrece cada línea.

La lista vive en Líneas de WhatsApp (`LineaWhatsapp.cursos`) y se busca por
phone id, venga la línea del entorno o de la base. Sin EKI_CURSOS_POR_LINEA,
o con la lista vacía, la línea ofrece todos los cursos, como antes.
`ProgresoEstudiante` no tiene línea: un curso es de una línea porque está en su lista.
Este módulo no importa core.models ni el canal: quien llama pasa el phone id.
"""
from __future__ import annotations

from typing import Callable

from django.apps import apps
from django.conf import settings

from core.conversacion.estado_linea import lectura_activa
from core.lineas.modelo import cursos_por_phone_id


def cursos_de_linea(phone_id: str) -> frozenset[int] | None:
    """Ids de curso de esa línea. None = todos."""
    if not getattr(settings, 'EKI_CURSOS_POR_LINEA', False):
        return None
    return cursos_por_phone_id().get(str(phone_id or '').strip()) or None


def solo_de_la_linea(progresos, phone_id: str):
    """El queryset de ProgresoEstudiante, recortado a los cursos de la línea."""
    ids = cursos_de_linea(phone_id)
    return progresos if ids is None else progresos.filter(curso_id__in=ids)


def fijar_curso_de_la_linea(phone_id: str, buscar: Callable[[], object | None]) -> bool:
    """Con la lectura prendida, pone en foco el único curso abierto de la lista de la línea.

    Sin esto, una línea cuyo contexto no tiene curso activo ofrece todos los
    cursos abiertos de la persona, también los de la otra línea. Con varios
    cursos abiertos de la misma lista no elige. Sin la lectura el contexto es
    uno solo para las dos líneas y cambiar el foco movería el de la otra.
    """
    if not lectura_activa():
        return False
    de_la_linea = cursos_de_linea(phone_id)
    if de_la_linea is None:
        return False
    estudiante = buscar()
    if estudiante is None:
        return False
    ids = list(
        apps.get_model('core', 'ProgresoEstudiante').objects.filter(
            estudiante=estudiante, completado=False, curso__activo=True, curso_id__in=de_la_linea,
        ).values_list('curso_id', flat=True)[:2]
    )
    if len(ids) != 1:
        return False
    ctx = dict(estudiante.contexto_temporal or {})
    if ctx.get('curso_activo_id') == ids[0]:
        return False
    ctx['curso_activo_id'] = ids[0]
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['contexto_temporal'])
    return True
