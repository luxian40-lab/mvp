"""
Clima para Nat vía Open-Meteo (geocoding + forecast).

No implementa UI de mapas: solo un bloque de texto con probabilidad
de precipitación y variables útiles para asesorar por WhatsApp.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'

_RE_NECESITA_CLIMA = re.compile(
    r'\b('
    r'lluv|precip|clima|tiempo|pron[oó]stico|humedad|viento|helada|sequ[ií]a|'
    r'fumig|aspers|riego|regar|aplicaci[oó]n|aplicar|aplicarlo|'
    r'puedo\s+(fumigar|aplicar|regar)|hoy\s+es\s+buen|'
    r'ma[nñ]ana\s+(puedo|fumig|aplic|riego)|'
    r'va\s+a\s+llover|llover[aá]|moj'
    r')\b',
    re.I,
)


def clima_open_meteo_habilitado() -> bool:
    return bool(getattr(settings, 'NAT_OPEN_METEO_ENABLED', True))


def consulta_necesita_clima(pregunta: str) -> bool:
    """True si el mensaje del productor parece necesitar dato climático real."""
    return bool(_RE_NECESITA_CLIMA.search(pregunta or ''))


def _timeout() -> float:
    try:
        return float(getattr(settings, 'NAT_OPEN_METEO_TIMEOUT', 4) or 4)
    except (TypeError, ValueError):
        return 4.0


def _cache_seconds() -> int:
    try:
        return int(getattr(settings, 'NAT_OPEN_METEO_CACHE_SECONDS', 3600) or 3600)
    except (TypeError, ValueError):
        return 3600


def resolver_ubicacion_texto(ctx_agro=None, pregunta: str = '') -> str:
    """Municipio / región / mención en pregunta para geocoding."""
    from core.contexto_agro import _extraer_municipio_texto

    def _txt(val) -> str:
        if val is None:
            return ''
        if not isinstance(val, str):
            return ''
        return val.strip()

    partes: list[str] = []
    if ctx_agro is not None:
        mun = _txt(getattr(ctx_agro, 'municipio', '') or '')
        vereda = _txt(getattr(ctx_agro, 'vereda', '') or '')
        reg = _txt(getattr(ctx_agro, 'region', '') or '')
        if mun:
            partes.append(mun)
        if vereda:
            partes.append(vereda)
        if reg and reg.lower() not in ' '.join(partes).lower():
            partes.append(reg)
    if not partes:
        mun = _extraer_municipio_texto(pregunta or '')
        if mun:
            partes.append(mun)
    if not partes:
        return ''
    texto = ', '.join(partes)
    if 'colombia' not in texto.lower():
        texto = f'{texto}, Colombia'
    return texto


def persistir_ubicacion_en_contexto(ctx_agro, geo: dict[str, Any], *, fuente: str = 'open_meteo') -> None:
    """Guarda municipio/depto/coords en ContextoAgroSession para reutilizar."""
    if ctx_agro is None or not geo:
        return
    from decimal import Decimal, InvalidOperation
    from django.utils import timezone

    changed_fields: list[str] = []
    nombre = (geo.get('name') or '').strip()
    admin1 = (geo.get('admin1') or '').strip()
    if nombre and not (getattr(ctx_agro, 'municipio', '') or '').strip():
        ctx_agro.municipio = nombre[:80]
        changed_fields.append('municipio')
    elif nombre and (ctx_agro.municipio or '').strip().lower() in ('bogota', 'bogotá'):
        # Normalizar acento
        if nombre.lower().startswith('bogot'):
            ctx_agro.municipio = nombre[:80]
            changed_fields.append('municipio')
    if admin1 and not (getattr(ctx_agro, 'region', '') or '').strip():
        ctx_agro.region = admin1[:120]
        changed_fields.append('region')

    try:
        lat = Decimal(str(round(float(geo['latitude']), 6)))
        lon = Decimal(str(round(float(geo['longitude']), 6)))
        if getattr(ctx_agro, 'latitud', None) != lat:
            ctx_agro.latitud = lat
            changed_fields.append('latitud')
        if getattr(ctx_agro, 'longitud', None) != lon:
            ctx_agro.longitud = lon
            changed_fields.append('longitud')
    except (KeyError, TypeError, ValueError, InvalidOperation):
        pass

    meta = dict(getattr(ctx_agro, 'metadata', None) or {})
    meta['ubicacion_recoleccion'] = {
        'fuente': fuente,
        'nombre': nombre,
        'admin1': admin1,
        'lat': geo.get('latitude'),
        'lon': geo.get('longitude'),
        'collected_at': timezone.now().isoformat(),
    }
    ctx_agro.metadata = meta
    changed_fields.append('metadata')
    try:
        update = list(dict.fromkeys(changed_fields + ['updated_at']))
        ctx_agro.save(update_fields=update)
    except Exception as exc:
        logger.debug('No se pudo persistir ubicación clima: %s', exc)


def geocode_open_meteo(ubicacion: str) -> dict[str, Any] | None:
    """
    Resuelve nombre de lugar → lat/lon (prioriza Colombia).
    """
    q = (ubicacion or '').strip()
    if not q:
        return None
    params = {
        'name': q.split(',')[0].strip(),
        'count': 5,
        'language': 'es',
        'format': 'json',
    }
    # Si el usuario dijo "X, Colombia" o región CO, filtramos
    if 'colombia' in q.lower() or re.search(
        r'\b(cundinamarca|huila|antioquia|tolima|valle|cauca|nariño|narino|'
        r'santander|boyac|meta|caldas|risaralda|quind)\b',
        q,
        re.I,
    ):
        params['country'] = 'CO'
    try:
        r = requests.get(GEOCODE_URL, params=params, timeout=_timeout())
        r.raise_for_status()
        results = (r.json() or {}).get('results') or []
    except Exception as exc:
        logger.warning('Open-Meteo geocode falló | q=%s | %s', q[:80], exc)
        return None
    if not results:
        # Reintento sin country filter
        try:
            params.pop('country', None)
            r = requests.get(GEOCODE_URL, params=params, timeout=_timeout())
            r.raise_for_status()
            results = (r.json() or {}).get('results') or []
        except Exception as exc:
            logger.warning('Open-Meteo geocode retry falló | %s', exc)
            return None
    if not results:
        return None
    # Preferir CO si hay varios
    pick = next((x for x in results if (x.get('country_code') or '') == 'CO'), results[0])
    return {
        'name': pick.get('name') or q,
        'admin1': pick.get('admin1') or '',
        'country': pick.get('country') or '',
        'latitude': float(pick['latitude']),
        'longitude': float(pick['longitude']),
    }


def forecast_open_meteo(lat: float, lon: float) -> dict[str, Any] | None:
    """Pronóstico diario 3 días + probabilidad de precipitación."""
    params = {
        'latitude': lat,
        'longitude': lon,
        'timezone': 'America/Bogota',
        'forecast_days': 3,
        'daily': ','.join([
            'precipitation_probability_max',
            'precipitation_sum',
            'temperature_2m_max',
            'temperature_2m_min',
            'wind_speed_10m_max',
            'weather_code',
        ]),
    }
    try:
        r = requests.get(FORECAST_URL, params=params, timeout=_timeout())
        r.raise_for_status()
        return r.json() or {}
    except Exception as exc:
        logger.warning('Open-Meteo forecast falló | lat=%s lon=%s | %s', lat, lon, exc)
        return None


def _fmt_num(v, suffix: str = '', nd: int = 0) -> str:
    if v is None:
        return 'n/d'
    try:
        n = float(v)
        if nd == 0:
            return f'{int(round(n))}{suffix}'
        return f'{n:.{nd}f}{suffix}'
    except (TypeError, ValueError):
        return 'n/d'


def formatear_bloque_clima(geo: dict[str, Any], data: dict[str, Any]) -> str:
    """Bloque listo para inyectar en el prompt de Nat."""
    daily = (data or {}).get('daily') or {}
    fechas = daily.get('time') or []
    probs = daily.get('precipitation_probability_max') or []
    rains = daily.get('precipitation_sum') or []
    t_max = daily.get('temperature_2m_max') or []
    t_min = daily.get('temperature_2m_min') or []
    wind = daily.get('wind_speed_10m_max') or []

    lugar = geo.get('name') or 'ubicación'
    if geo.get('admin1'):
        lugar = f"{lugar}, {geo['admin1']}"
    if geo.get('country'):
        lugar = f"{lugar} ({geo['country']})"

    etiquetas = ['Hoy', 'Mañana', 'Pasado mañana']
    lineas_dias: list[str] = []
    for i, fecha in enumerate(fechas[:3]):
        etiqueta = etiquetas[i] if i < len(etiquetas) else fecha
        p = probs[i] if i < len(probs) else None
        mm = rains[i] if i < len(rains) else None
        mx = t_max[i] if i < len(t_max) else None
        mn = t_min[i] if i < len(t_min) else None
        w = wind[i] if i < len(wind) else None
        lineas_dias.append(
            f"- {etiqueta} ({fecha}): prob. lluvia {_fmt_num(p, '%')}, "
            f"precip. {_fmt_num(mm, ' mm', 1)}, "
            f"temp {_fmt_num(mn)}–{_fmt_num(mx)} °C, "
            f"viento máx {_fmt_num(w, ' km/h')}"
        )

    if not lineas_dias:
        return ''

    return (
        'CLIMA VERIFICADO (Open-Meteo — use estas cifras; no invente otras):\n'
        f'- Lugar resuelto: {lugar}\n'
        f"- Coordenadas: {geo['latitude']:.3f}, {geo['longitude']:.3f}\n"
        + '\n'.join(lineas_dias)
        + '\n'
        'Si el productor pregunta por fumigar/aplicar/regar, cruce este pronóstico '
        'con el producto del catálogo (deriva, lavado por lluvia, viento).\n'
        'Si no hay dato para su zona exacta, diga que la lectura es del municipio '
        'más cercano resuelto y pida confirmación de vereda si hace falta.\n'
        'Fuente: Open-Meteo.'
    )


def _cache_key(ubicacion: str) -> str:
    return (ubicacion or '').strip().lower()[:120]


def _leer_cache(ctx_agro, ubicacion: str) -> str | None:
    if ctx_agro is None:
        return None
    meta = dict(getattr(ctx_agro, 'metadata', None) or {})
    blob = meta.get('clima_open_meteo') or {}
    if not isinstance(blob, dict):
        return None
    if blob.get('query') != _cache_key(ubicacion):
        return None
    try:
        age = time.time() - float(blob.get('ts') or 0)
    except (TypeError, ValueError):
        return None
    if age > _cache_seconds():
        return None
    texto = (blob.get('bloque') or '').strip()
    return texto or None


def _guardar_cache(ctx_agro, ubicacion: str, bloque: str, geo: dict[str, Any]) -> None:
    if ctx_agro is None or not bloque:
        return
    try:
        meta = dict(getattr(ctx_agro, 'metadata', None) or {})
        meta['clima_open_meteo'] = {
            'ts': time.time(),
            'query': _cache_key(ubicacion),
            'bloque': bloque,
            'lat': geo.get('latitude'),
            'lon': geo.get('longitude'),
            'name': geo.get('name'),
        }
        ctx_agro.metadata = meta
        # update_fields evita pisar extracción concurrente innecesaria
        ctx_agro.save(update_fields=['metadata'])
    except Exception as exc:
        logger.debug('No se pudo cachear clima Open-Meteo: %s', exc)


def obtener_bloque_clima_para_nat(
    pregunta: str,
    ctx_agro=None,
    forzar: bool = False,
) -> str:
    """
    Si la consulta necesita clima y hay ubicación, consulta Open-Meteo
    y devuelve bloque para el prompt. Cadena vacía si no aplica o falla.
    """
    if not clima_open_meteo_habilitado():
        return ''
    if not forzar and not consulta_necesita_clima(pregunta):
        return ''

    ubicacion = resolver_ubicacion_texto(ctx_agro, pregunta)
    if not ubicacion:
        # Marca en metadata que pedimos ubicación (para analitica / seguimiento)
        if ctx_agro is not None:
            try:
                from django.utils import timezone

                meta = dict(getattr(ctx_agro, 'metadata', None) or {})
                meta['ubicacion_pendiente'] = {
                    'motivo': 'clima',
                    'asked_at': timezone.now().isoformat(),
                    'pregunta': (pregunta or '')[:200],
                }
                ctx_agro.metadata = meta
                ctx_agro.save(update_fields=['metadata', 'updated_at'])
            except Exception:
                pass
        return (
            'CLIMA: el productor pregunta por condiciones climáticas pero '
            'aún no hay ubicación clara en BD.\n'
            'OBLIGATORIO: pídale en un solo mensaje, de usted:\n'
            '1) municipio,\n'
            '2) departamento,\n'
            '3) vereda, localidad o zona del lote (si la conoce).\n'
            'Ejemplo: «Para darte la probabilidad de lluvia exacta, ¿en qué '
            'municipio y departamento está, y si puede la vereda o localidad?»\n'
            'Cuando responda, use esos datos; no invente probabilidad de lluvia.'
        )

    # Si ya tenemos coords guardadas en BD, úsalas (más exacto / menos API)
    lat_saved = getattr(ctx_agro, 'latitud', None) if ctx_agro is not None else None
    lon_saved = getattr(ctx_agro, 'longitud', None) if ctx_agro is not None else None
    geo = None
    if lat_saved is not None and lon_saved is not None:
        geo = {
            'name': (getattr(ctx_agro, 'municipio', None) or ubicacion.split(',')[0]).strip(),
            'admin1': (getattr(ctx_agro, 'region', None) or '').strip(),
            'country': 'Colombia',
            'latitude': float(lat_saved),
            'longitude': float(lon_saved),
        }

    cached = _leer_cache(ctx_agro, ubicacion)
    if cached:
        return cached

    if geo is None:
        geo = geocode_open_meteo(ubicacion)
    if not geo:
        return (
            f'CLIMA: no se pudo resolver la ubicación «{ubicacion}» en Open-Meteo. '
            'Pida confirmar municipio, departamento y vereda/localidad; no invente probabilidad de lluvia.'
        )

    persistir_ubicacion_en_contexto(ctx_agro, geo, fuente='open_meteo')

    data = forecast_open_meteo(geo['latitude'], geo['longitude'])
    if not data:
        return (
            f'CLIMA: falló la consulta de pronóstico para {geo.get("name")}. '
            'No invente cifras; ofrezca reintentar o pedir dato local del productor.'
        )

    bloque = formatear_bloque_clima(geo, data)
    if bloque:
        _guardar_cache(ctx_agro, ubicacion, bloque, geo)
        logger.info(
            'Nat Open-Meteo | lugar=%s lat=%.3f lon=%.3f',
            geo.get('name'),
            geo['latitude'],
            geo['longitude'],
        )
    return bloque
