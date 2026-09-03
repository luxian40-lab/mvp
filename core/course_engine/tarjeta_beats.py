"""Beats de lámina tarjeta — texto en pantalla alineado al guion TTS."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TarjetaBeat:
    """Un momento de la lámina: lo que dice la voz y lo que se muestra."""

    headline: str
    narracion: str
    detalle: str
    filas: list[tuple[str, str]]


def _parse_punto(p: str) -> tuple[str, str]:
    p = (p or '').strip()
    for sep in (' — ', ' – ', ' - ', ': '):
        if sep in p:
            a, b = p.split(sep, 1)
            return a.strip()[:48], b.strip()[:72]
    return p[:48], ''


def _oraciones(guion: str) -> list[str]:
    g = (guion or '').strip()
    if not g:
        return []
    partes = [s.strip() for s in re.split(r'(?<=[.!?])\s+', g) if s.strip()]
    return partes if partes else [g]


def _mapear_oraciones(oraciones: list[str], n: int) -> list[str]:
    """Una narración por beat; sin repetir la última frase en todos los beats."""
    if n <= 0:
        return []
    if not oraciones:
        return [''] * n
    if len(oraciones) == n:
        return list(oraciones)
    if len(oraciones) > n:
        out = list(oraciones[: n - 1])
        out.append(' '.join(oraciones[n - 1 :]))
        return out
    out = list(oraciones)
    while len(out) < n:
        out.append('')
    return out


def beats_desde_tarjeta(
    *,
    titulo: str,
    puntos: list[str],
    guion: str,
) -> list[TarjetaBeat]:
    """
    Alinea typing en pantalla con la narración del segmento tarjeta.
    Un beat por punto (tabla); guion repartido sin duplicar la última oración.
    """
    titulo = (titulo or 'Lección eki').strip()[:100]
    pts = [str(p).strip() for p in (puntos or []) if str(p).strip()][:4]
    oraciones = _oraciones(guion)

    if not pts and not oraciones:
        return [
            TarjetaBeat(
                headline=titulo,
                narracion=titulo,
                detalle='',
                filas=[],
            )
        ]

    if pts:
        narrs = _mapear_oraciones(oraciones, len(pts))
        beats: list[TarjetaBeat] = []
        filas: list[tuple[str, str]] = []
        for i, punto in enumerate(pts):
            concepto, accion = _parse_punto(punto)
            filas.append((concepto, accion or ''))
            narr = (narrs[i] or '').strip()
            if not narr:
                narr = concepto or titulo
            if i == 0:
                headline = titulo if not concepto else concepto
            else:
                headline = concepto or narr[:48]
            detalle = accion if accion and accion != narr[:72] else ''
            beats.append(
                TarjetaBeat(
                    headline=headline[:48],
                    narracion=narr[:220],
                    detalle=detalle[:72],
                    filas=list(filas),
                )
            )
        return beats

    return [
        TarjetaBeat(
            headline=titulo if i == 0 else oracion[:48],
            narracion=oracion[:220],
            detalle='',
            filas=[],
        )
        for i, oracion in enumerate(oraciones)
    ]
