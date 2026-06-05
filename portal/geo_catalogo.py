"""Catálogo estático DANE: normalización, resolución y centroides."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Literal

DATA_DIR = Path(__file__).resolve().parent / 'data'

DEPTO_ALIASES: dict[str, str] = {
    'BOGOTA': 'BOGOTA, D.C.',
    'BOGOTA DC': 'BOGOTA, D.C.',
    'BOGOTA D C': 'BOGOTA, D.C.',
    'DISTRITO CAPITAL': 'BOGOTA, D.C.',
    'D C': 'BOGOTA, D.C.',
    'DC': 'BOGOTA, D.C.',
    'SAN ANDRES': 'ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA',
    'SAN ANDRES Y PROVIDENCIA': 'ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA',
    'N DE SANTANDER': 'NORTE DE SANTANDER',
    'NORTE SANTANDER': 'NORTE DE SANTANDER',
    'VALLE': 'VALLE DEL CAUCA',
    'VALLE DEL CAUCA': 'VALLE DEL CAUCA',
    'QUINDIO': 'QUINDIO',
}

MUNICIPIO_ALIASES: dict[str, str] = {
    'SANTAFE DE BOGOTA': 'BOGOTA',
    'SANTAFE DE BOGOTA DC': 'BOGOTA',
    'CAPITAL': 'BOGOTA',
}

# Municipio registrado en departamento incorrecto → (municipio, departamento) DANE
MUNICIPIO_DEPTO_CORRECCION: dict[tuple[str, str], tuple[str, str]] = {
    ('CARTAGENA', 'ATLANTICO'): ('CARTAGENA DE INDIAS', 'BOLIVAR'),
    ('MAGANGUE', 'ATLANTICO'): ('MAGANGUE', 'BOLIVAR'),
}


@dataclass(frozen=True)
class UbicacionResuelta:
    departamento: str
    municipio: str
    clave_departamento: str
    clave_municipio: str
    nivel: Literal['municipio', 'departamento', 'ninguno']
    metodo: Literal['exacto', 'alias', 'aproximado', 'solo_departamento', 'ninguno']


def normalizar_clave_geo(texto: str) -> str:
    if not texto:
        return ''
    t = unicodedata.normalize('NFD', texto.strip())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    t = re.sub(r'[^A-Za-z0-9]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip().upper()
    return t


def _titulo(texto: str) -> str:
    if not texto:
        return ''
    t = unicodedata.normalize('NFD', texto.strip())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    t = re.sub(r'\s+', ' ', t)
    return t.title()


def clave_departamento(texto: str) -> str:
    base = normalizar_clave_geo(texto)
    if not base:
        return ''
    return DEPTO_ALIASES.get(base, base)


def clave_municipio(municipio: str, departamento: str) -> str:
    m = normalizar_clave_geo(municipio)
    d = clave_departamento(departamento)
    if not m:
        return ''
    if m in MUNICIPIO_ALIASES:
        m = MUNICIPIO_ALIASES[m]
    if m in ('BOGOTA', 'SANTAFE DE BOGOTA', 'SANTAFE DE BOGOTA DC'):
        if d in ('CUNDINAMARCA', 'BOGOTA, D.C.', 'BOGOTA D C', ''):
            return 'BOGOTA, D.C.|BOGOTA, D.C.'
    if not d:
        return ''
    return f'{m}|{d}'


@lru_cache(maxsize=1)
def _centroides_municipios() -> dict[str, dict]:
    path = DATA_DIR / 'municipios_centroides.json'
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def _indice_catalogo() -> tuple[dict[str, dict], dict[str, dict[str, dict]], list[str]]:
    """(por_clave, por_depto_municipios, lista_claves_depto)."""
    data = _centroides_municipios()
    por_depto: dict[str, dict[str, dict]] = {}
    deptos: set[str] = set()
    for clave, row in data.items():
        if '|' not in clave:
            continue
        m_key, d_key = clave.split('|', 1)
        deptos.add(d_key)
        por_depto.setdefault(d_key, {})[m_key] = row
    return data, por_depto, sorted(deptos)


def resolver_ubicacion(
    municipio: str,
    departamento: str,
    *,
    permitir_aproximado: bool = True,
) -> UbicacionResuelta:
    """Resuelve texto libre contra catálogo DANE (~1122 municipios)."""
    raw_m = (municipio or '').strip()
    raw_d = (departamento or '').strip()
    m_corr, d_corr = MUNICIPIO_DEPTO_CORRECCION.get(
        (normalizar_clave_geo(raw_m), clave_departamento(raw_d)),
        (None, None),
    )
    if m_corr and d_corr:
        raw_m, raw_d = m_corr.title(), d_corr.title()
    por_clave, por_depto, deptos_catalogo = _indice_catalogo()

    def _desde_clave(clave: str, metodo: Literal['exacto', 'alias', 'aproximado', 'solo_departamento']) -> UbicacionResuelta:
        row = por_clave[clave]
        d_key = clave.split('|', 1)[1]
        return UbicacionResuelta(
            departamento=row.get('departamento') or _titulo(d_key),
            municipio=row.get('municipio') or _titulo(clave.split('|', 1)[0]),
            clave_departamento=d_key,
            clave_municipio=clave,
            nivel='municipio',
            metodo=metodo,
        )

    intentos_muni = []
    if raw_m:
        intentos_muni.append(raw_m)
        intentos_muni.append(MUNICIPIO_ALIASES.get(normalizar_clave_geo(raw_m), ''))

    for m_try in intentos_muni:
        if not m_try:
            continue
        clave = clave_municipio(m_try, raw_d)
        if clave and clave in por_clave:
            metodo = 'alias' if m_try != raw_m else 'exacto'
            return _desde_clave(clave, metodo)

    d_key = clave_departamento(raw_d)
    m_key = normalizar_clave_geo(raw_m)

    if permitir_aproximado and d_key and m_key and d_key in por_depto:
        candidatos = list(por_depto[d_key].keys())
        match = get_close_matches(m_key, candidatos, n=1, cutoff=0.82)
        if match:
            return _desde_clave(f'{match[0]}|{d_key}', 'aproximado')

    if permitir_aproximado and m_key and not d_key:
        global_hits = [k for k in por_clave if k.startswith(f'{m_key}|')]
        if len(global_hits) == 1:
            return _desde_clave(global_hits[0], 'aproximado')

    if d_key and d_key in deptos_catalogo:
        return UbicacionResuelta(
            departamento=_titulo(raw_d) or _titulo(d_key),
            municipio='',
            clave_departamento=d_key,
            clave_municipio='',
            nivel='departamento',
            metodo='solo_departamento',
        )

    if permitir_aproximado and raw_d:
        match_d = get_close_matches(d_key or normalizar_clave_geo(raw_d), deptos_catalogo, n=1, cutoff=0.88)
        if match_d:
            return UbicacionResuelta(
                departamento=_titulo(match_d[0]),
                municipio='',
                clave_departamento=match_d[0],
                clave_municipio='',
                nivel='departamento',
                metodo='aproximado',
            )

    return UbicacionResuelta(
        departamento=_titulo(raw_d),
        municipio=_titulo(raw_m),
        clave_departamento=d_key,
        clave_municipio='',
        nivel='ninguno',
        metodo='ninguno',
    )


def centroide_municipio(municipio: str, departamento: str) -> tuple[float, float] | None:
    res = resolver_ubicacion(municipio, departamento, permitir_aproximado=True)
    if res.nivel != 'municipio' or not res.clave_municipio:
        return None
    row = _centroides_municipios().get(res.clave_municipio)
    if not row:
        return None
    return float(row['lat']), float(row['lng'])


def jitter_coordenada(estudiante_id: int, lat: float, lng: float) -> tuple[float, float]:
    seed = (estudiante_id * 2654435761) % 10000
    dlat = ((seed % 100) - 50) / 8000.0
    dlng = (((seed // 100) % 100) - 50) / 8000.0
    return round(lat + dlat, 5), round(lng + dlng, 5)


def ruta_geojson_departamentos() -> Path:
    return DATA_DIR / 'colombia_departamentos.geojson'


def ruta_geojson_municipios() -> Path:
    return DATA_DIR / 'colombia_municipios_mapa.geojson'
