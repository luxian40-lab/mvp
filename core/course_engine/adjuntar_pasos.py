"""Adjunta assets del Course Engine como micros en borrador (no publica)."""
from __future__ import annotations

from typing import Any, Iterable


def adjuntar_assets_ce_a_modulo(modulo, assets: Iterable[Any], *, activo: bool = False) -> int:
    """
    Crea PasoModulo inactivos por cada asset con URL.
    No pisa pasos existentes con la misma media_url. No marca publicado_wa.
    """
    from core.models import PasoModulo, SeccionModulo

    if not modulo or not getattr(modulo, 'pk', None):
        return 0
    seccion = modulo.secciones.order_by('orden', 'id').first()
    if seccion is None:
        seccion = SeccionModulo.objects.create(
            modulo=modulo,
            orden=1,
            titulo=((modulo.titulo or '').strip() or 'Bloque 1')[:200],
            activa=True,
        )
    creados = 0
    max_orden = (
        PasoModulo.objects.filter(modulo=modulo)
        .order_by('-orden')
        .values_list('orden', flat=True)
        .first()
        or 0
    )
    for asset in assets or []:
        url = (getattr(asset, 'url', None) or '').strip()
        if not url:
            continue
        if PasoModulo.objects.filter(modulo=modulo, media_url=url).exists():
            continue
        max_orden += 1
        label = (getattr(asset, 'label', None) or getattr(asset, 'tipo', None) or 'Micro CE')[:200]
        PasoModulo.objects.create(
            modulo=modulo,
            seccion=seccion,
            orden=max_orden,
            titulo=label,
            contenido='',
            media_url=url[:2000],
            activo=bool(activo),
            requiere_listo_para_avanzar=True,
        )
        creados += 1
    return creados
