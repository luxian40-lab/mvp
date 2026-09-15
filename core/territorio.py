"""Resolución territorial canónica (DIVIPOLA) para el plano de experiencia."""

from __future__ import annotations

from portal.geo_catalogo import UbicacionResuelta, aplicar_ubicacion_dane, resolver_ubicacion


def resolver_territorio(municipio: str, departamento: str = '') -> UbicacionResuelta:
    """Resuelve texto libre → municipio DANE + territory_id DIVIPOLA."""
    return resolver_ubicacion(municipio, departamento)


def aplicar_territorio_estudiante(estudiante, *, save: bool = True) -> UbicacionResuelta:
    """Normaliza municipio/departamento y escribe territory_id en el estudiante."""
    ubic = resolver_ubicacion(estudiante.municipio or '', estudiante.departamento or '')
    aplicar_ubicacion_dane(
        estudiante,
        municipio=estudiante.municipio,
        departamento=estudiante.departamento,
        save=save,
    )
    return ubic


def obtener_territory_id_estudiante(estudiante, *, persistir: bool = True) -> str:
    """
    Territory id listo para EventOutbox.
    Si el estudiante ya lo tiene, lo usa; si no, intenta resolver desde municipio/depto.
    Nunca lanza: falla → ''.
    """
    if estudiante is None:
        return ''
    try:
        tid = (getattr(estudiante, 'territory_id', None) or '').strip()
        if tid:
            return tid[:32]
        mun = (getattr(estudiante, 'municipio', None) or '').strip()
        if not mun:
            return ''
        ubic = aplicar_territorio_estudiante(estudiante, save=persistir)
        return ((ubic.territory_id if ubic else '') or '').strip()[:32]
    except Exception:
        return ''
