"""Helpers para bloques (SeccionModulo) al crear/editar módulos."""

from __future__ import annotations

from core.models import Modulo, SeccionModulo


def parse_titulos_bloques_rapidos(raw: str) -> list[str]:
    """Una línea no vacía = un bloque. Máximo 20."""
    out: list[str] = []
    for line in (raw or '').splitlines():
        t = ' '.join(line.strip().split())
        if not t:
            continue
        out.append(t[:200])
        if len(out) >= 20:
            break
    return out


def crear_secciones_desde_titulos(modulo: Modulo, titulos: list[str]) -> int:
    """Crea SeccionModulo en orden correlativo. No borra existentes."""
    if not modulo or not modulo.pk or not titulos:
        return 0
    created = 0
    orden_base = (
        SeccionModulo.objects.filter(modulo=modulo)
        .order_by('-orden')
        .values_list('orden', flat=True)
        .first()
        or 0
    )
    for i, titulo in enumerate(titulos, start=1):
        SeccionModulo.objects.create(
            modulo=modulo,
            orden=orden_base + i,
            titulo=titulo,
            activa=True,
        )
        created += 1
    return created
