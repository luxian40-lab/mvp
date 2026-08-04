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
    territory_id: str = ''
    confianza: float = 0.0


@lru_cache(maxsize=1)
def _divipola_por_clave() -> dict[str, dict]:
    path = DATA_DIR / 'divipola_municipios.json'
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def codigo_divipola_para_clave(clave_municipio: str) -> str:
    """Devuelve código DIVIPOLA (5 dígitos) para clave MUNI|DEPTO del catálogo."""
    if not clave_municipio:
        return ''
    row = _divipola_por_clave().get(clave_municipio) or {}
    code = str(row.get('codigo') or '').strip()
    return code.zfill(5) if code.isdigit() else code


def _con_divipola(ubic: UbicacionResuelta) -> UbicacionResuelta:
    tid = ''
    conf = 0.0
    if ubic.nivel == 'municipio' and ubic.clave_municipio:
        tid = codigo_divipola_para_clave(ubic.clave_municipio)
        if tid:
            conf = {'exacto': 1.0, 'alias': 0.95, 'aproximado': 0.8}.get(ubic.metodo, 0.7)
    return UbicacionResuelta(
        departamento=ubic.departamento,
        municipio=ubic.municipio,
        clave_departamento=ubic.clave_departamento,
        clave_municipio=ubic.clave_municipio,
        nivel=ubic.nivel,
        metodo=ubic.metodo,
        territory_id=tid,
        confianza=conf,
    )


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
    """Resuelve texto libre contra catálogo DANE (~1122 municipios) + DIVIPOLA."""
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
        return _con_divipola(UbicacionResuelta(
            departamento=row.get('departamento') or _titulo(d_key),
            municipio=row.get('municipio') or _titulo(clave.split('|', 1)[0]),
            clave_departamento=d_key,
            clave_municipio=clave,
            nivel='municipio',
            metodo=metodo,
        ))

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
            territory_id='',
            confianza=0.4,
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
                territory_id='',
                confianza=0.3,
            )

    return UbicacionResuelta(
        departamento=_titulo(raw_d),
        municipio=_titulo(raw_m),
        clave_departamento=d_key,
        clave_municipio='',
        nivel='ninguno',
        metodo='ninguno',
        territory_id='',
        confianza=0.0,
    )


def aplicar_ubicacion_dane(
    estudiante,
    municipio: str | None = None,
    departamento: str | None = None,
    *,
    save: bool = False,
) -> bool:
    """Normaliza municipio/departamento del estudiante con catálogo DANE.

    Returns True si cambió algún campo (y opcionalmente guarda).
    """
    raw_m = (municipio if municipio is not None else (estudiante.municipio or '')).strip()
    raw_d = (
        departamento if departamento is not None else (estudiante.departamento or '')
    ).strip()
    if not raw_m and not raw_d:
        return False

    ubic = resolver_ubicacion(raw_m, raw_d)
    nuevo_m = ubic.municipio or raw_m
    nuevo_d = ubic.departamento or raw_d
    nuevo_tid = (ubic.territory_id or '').strip()
    old_tid = (getattr(estudiante, 'territory_id', '') or '').strip()
    changed = (
        (estudiante.municipio or '').strip() != (nuevo_m or '').strip()
        or (estudiante.departamento or '').strip() != (nuevo_d or '').strip()
        or old_tid != nuevo_tid
    )
    if not changed:
        return False
    estudiante.municipio = nuevo_m
    estudiante.departamento = nuevo_d
    if hasattr(estudiante, 'territory_id'):
        estudiante.territory_id = nuevo_tid
    if save:
        fields = ['municipio', 'departamento']
        if hasattr(estudiante, 'territory_id'):
            fields.append('territory_id')
        estudiante.save(update_fields=fields)
        try:
            from django.core.cache import cache

            cache.delete('eki_cobertura_global_v2')
        except Exception:
            pass
    return True


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
