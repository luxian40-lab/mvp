"""Clasificador de señales territoriales v0 (reglas) — modo sombra."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from core.taxonomia_senales import (
    EJEMPLOS_ETIQUETADOS,
    TAXONOMIA_V0,
    TIPOS_BLOQUEADOS_V0,
)


@dataclass(frozen=True)
class ClasificacionSenal:
    tipo: str | None
    confianza: float
    metodo: str
    familia: str = ''
    motivo: str = ''


def _norm(texto: str) -> str:
    t = (texto or '').lower().strip()
    t = ''.join(
        c for c in unicodedata.normalize('NFD', t)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'\s+', ' ', t)


def _parece_salud(texto_n: str) -> bool:
    keys = (
        'diarrea', 'vomito', 'vómito', 'fiebre', 'infeccion', 'infección',
        'sintoma', 'síntoma', 'hospital', 'medico', 'médico', 'enfermo del estomago',
        'dolor de panza', 'gastro',
    )
    return any(k in texto_n for k in keys)


def clasificar_consulta_territorial(
    texto: str,
    *,
    contexto: dict | None = None,
) -> ClasificacionSenal:
    """
    Reglas v0: plagas + empleo. Salud → None (bloqueado).
    No cambia respuesta de producto; solo etiqueta.
    """
    del contexto  # reservado (cultivo/municipio) para v1
    bruto = (texto or '').strip()
    if len(bruto) < 4:
        return ClasificacionSenal(None, 0.0, 'rules_v0', motivo='texto_corto')

    n = _norm(bruto)
    if _parece_salud(n):
        return ClasificacionSenal(
            None, 0.0, 'rules_v0', motivo='familia_salud_bloqueada_v0',
        )

    # Prioridad: tipos más específicos antes que *.general
    orden = sorted(
        TAXONOMIA_V0.items(),
        key=lambda kv: (0 if kv[0].endswith('.general') else 1, -len(kv[0])),
        reverse=True,
    )
    # Re-sort: non-general first
    orden = [x for x in orden if not x[0].endswith('.general')] + [
        x for x in orden if x[0].endswith('.general')
    ]

    for tipo, meta in orden:
        if any(tipo.startswith(b) or tipo == b for b in TIPOS_BLOQUEADOS_V0):
            continue
        for kw in meta.get('keywords') or ():
            kw_n = _norm(kw)
            if kw_n and kw_n in n:
                conf = 0.92 if not tipo.endswith('.general') else 0.72
                return ClasificacionSenal(
                    tipo=tipo,
                    confianza=conf,
                    metodo='rules_v0',
                    familia=meta.get('familia') or '',
                    motivo=f'kw:{kw_n}',
                )

    return ClasificacionSenal(None, 0.0, 'rules_v0', motivo='sin_match')


def precision_ejemplos_etiquetados() -> dict:
    """Evalúa el set etiquetado; útil en tests y comando management."""
    ok = 0
    total = len(EJEMPLOS_ETIQUETADOS)
    fallos: list[dict] = []
    for texto, esperado in EJEMPLOS_ETIQUETADOS:
        got = clasificar_consulta_territorial(texto).tipo
        if got == esperado:
            ok += 1
        else:
            fallos.append({'texto': texto, 'esperado': esperado, 'obtenido': got})
    return {
        'total': total,
        'ok': ok,
        'precision': (ok / total) if total else 0.0,
        'fallos': fallos,
    }
