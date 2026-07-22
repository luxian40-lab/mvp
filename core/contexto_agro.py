"""
Extracción y persistencia de contexto agronómico estructurado para Nat (Parte 3).
"""

from __future__ import annotations

import re
from typing import Any

from django.utils import timezone

# Patrones ligeros (NLU rule-based) — extensible con LLM después
_PATRONES = {
    'cultivo': re.compile(
        r'\b(caf[eé]|cacao|platano|plátano|banano|aguacate|papa|tomate|ma[ií]z|arroz|'
        r'caña|mora|fr[ií]jol|frijol|hortaliza|pasto|ganado|bovino|porcino|av[ií]cola|avicola|'
        r'yuca|mandioca|cítrico|citrico|limón|limon|naranja|mango|piña|pina|panela|'
        r'cebolla|zanahoria|lechuga|pepino|berenjena|guayaba|maracuy[aá]|lulo)\b',
        re.I,
    ),
    'etapa': re.compile(
        r'\b(germinaci[oó]n|siembra|vegeta|floraci[oó]n|fructificaci[oó]n|cosecha|'
        r'beneficio|poscosecha|secado|tensi[oó]n)\b',
        re.I,
    ),
    'problema': re.compile(
        r'\b(roya|broca|manchas?|plagas?|gusanos?|trips|ácaros?|acaros?|chocolate|'
        r'deficiencia|clorosis|sequ[ií]a|humedad|hongos?|mildiu|oidio|'
        r'nutrici[oó]n|fertiliz|abono|nitr[oó]geno|f[oó]sforo|potasio|'
        r'no\s+crece|no\s+crecen|brote\s+negro|marchit|amarill)\b',
        re.I,
    ),
    'clima': re.compile(
        r'\b(lluvia|sequ[ií]a|humedad| helada|calor|viento|clima|temporal|'
        r'invierno|verano|alta humedad|baja humedad)\b',
        re.I,
    ),
    'region': re.compile(
        r'\b(cundinamarca|huila|nariño|narino|antioquia|santander|tolima|'
        r'caquet[aá]|quind[ií]o|risaralda|caldas|boyac[aá]|meta|cordoba|c[oó]rdoba|'
        r'valle|cauca|putumayo|magdalena|choc[oó])\b',
        re.I,
    ),
}

_CORRECCION = re.compile(
    r'\b(no es|no era|me equivoqu[eé]|corrijo|en realidad|sino que|perdón|perdon)\b',
    re.I,
)

# Problema, clima y etapa pueden cambiar en la misma conversación.
_CAMPOS_EVOLUTIVOS = frozenset({'problema', 'etapa', 'clima', 'municipio', 'vereda'})

_CIUDADES_CO = {
    'bogota': 'Bogotá',
    'bogotá': 'Bogotá',
    'ibague': 'Ibagué',
    'ibagué': 'Ibagué',
    'neiva': 'Neiva',
    'medellin': 'Medellín',
    'medellín': 'Medellín',
    'cali': 'Cali',
    'barranquilla': 'Barranquilla',
    'cartagena': 'Cartagena',
    'bucaramanga': 'Bucaramanga',
    'manizales': 'Manizales',
    'pereira': 'Pereira',
    'armenia': 'Armenia',
    'pasto': 'Pasto',
    'villavicencio': 'Villavicencio',
    'popayan': 'Popayán',
    'popayán': 'Popayán',
    'tunja': 'Tunja',
    'sincelejo': 'Sincelejo',
    'monteria': 'Montería',
    'montería': 'Montería',
    'valledupar': 'Valledupar',
    'santa marta': 'Santa Marta',
}

_STOP_EN = frozenset({
    'para', 'con', 'de', 'del', 'la', 'el', 'los', 'las', 'por', 'una', 'un',
    'hoy', 'manana', 'mañana', 'luego', 'fumigar', 'aplicar', 'regar', 'riego',
    'clima', 'tiempo', 'lluvia', 'llover', 'semana', 'dias', 'días',
})


def _extraer_municipio_texto(texto: str) -> str:
    """Municipio desde ciudades conocidas o patrón 'en <lugar>'."""
    low = (texto or '').lower()
    for key, canon in sorted(_CIUDADES_CO.items(), key=lambda x: -len(x[0])):
        if re.search(rf'\b{re.escape(key)}\b', low):
            return canon
    m = re.search(
        r'\ben\s+([A-Za-zÁÉÍÓÚáéíóúÑñ]{3,})(?:\s+([A-Za-zÁÉÍÓÚáéíóúÑñ]{3,}))?',
        texto or '',
        re.I,
    )
    if m:
        primero = m.group(1)
        segundo = m.group(2) or ''
        if segundo and segundo.lower() not in _STOP_EN and segundo[:1].isupper():
            return f'{primero.title()} {segundo.title()}'[:80]
        return primero.title()[:80]
    # "Boyacá Guateque", "Caldas Chinchiná" (depto + municipio sin "en")
    m2 = re.search(
        r'\b('
        r'boyac[aá]|cundinamarca|antioquia|santander|tolima|huila|nari[nñ]o|'
        r'caldas|risaralda|quind[ií]o|meta|valle|cauca|cordoba|c[oó]rdoba|magdalena|'
        r'caquet[aá]|putumayo|choc[oó]|cesar|sucre|atl[aá]ntico|atlantico'
        r')\s+([A-Za-zÁÉÍÓÚáéíóúÑñ]{3,})\b',
        texto or '',
        re.I,
    )
    if m2:
        return m2.group(2).title()[:80]
    # Municipio suelto cuando el mensaje es corto y parece ubicación
    if len((texto or '').split()) <= 3:
        m3 = re.search(r'\b([A-Za-zÁÉÍÓÚáéíóúÑñ]{4,})\b', texto or '')
        if m3 and m3.group(1).lower() not in _STOP_EN:
            cand = m3.group(1).title()
            if cand.lower() not in {
                'boyaca', 'boyacá', 'caldas', 'tolima', 'huila', 'primero', 'clima',
            }:
                return cand[:80]
    return ''


def _extraer_vereda(texto: str) -> str:
    m = re.search(
        r'\b(?:vereda|localidad|corregimiento|barrio)\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9][\wÁÉÍÓÚáéíóúÑñ\s\-]{2,60})',
        texto or '',
        re.I,
    )
    if not m:
        return ''
    val = m.group(1).strip()
    # Cortar en conectores
    val = re.split(r'\b(?:para|con|porque|y|en)\b', val, maxsplit=1, flags=re.I)[0].strip(' ,.-')
    return val[:120]


def _normalizar_valor(campo: str, match: re.Match) -> str:
    val = (match.group(1) or match.group(0) or '').strip()
    if campo == 'cultivo' and val.lower() in ('cafe', 'café'):
        return 'café'
    return val[:200] if campo == 'problema' else val[:80]


def extraer_campos_desde_mensaje(mensaje: str) -> dict[str, str]:
    """Detecta dimensiones agronómicas en un mensaje del productor."""
    texto = (mensaje or '').strip()
    if not texto:
        return {}
    found: dict[str, str] = {}
    for campo, patron in _PATRONES.items():
        if campo == 'cultivo':
            matches = list(patron.finditer(texto))
            if matches:
                m = matches[-1] if len(matches) > 1 else matches[0]
                found[campo] = _normalizar_valor(campo, m)
            continue
        m = patron.search(texto)
        if m:
            found[campo] = _normalizar_valor(campo, m)
    mun = _extraer_municipio_texto(texto)
    if mun:
        found['municipio'] = mun
    vereda = _extraer_vereda(texto)
    if vereda:
        found['vereda'] = vereda
    return found


def obtener_o_crear_contexto(sesion) -> 'ContextoAgroSession':
    from core.models import ContextoAgroSession

    ctx, _ = ContextoAgroSession.objects.get_or_create(sesion=sesion)
    return ctx


def actualizar_contexto_desde_mensaje(sesion, mensaje: str) -> 'ContextoAgroSession':
    """Fusiona extracción del mensaje con contexto previo de la sesión."""
    ctx = obtener_o_crear_contexto(sesion)
    nuevos = extraer_campos_desde_mensaje(mensaje)
    permite_corregir = bool(_CORRECCION.search(mensaje or ''))
    changed = False
    for campo, valor in nuevos.items():
        if not valor:
            continue
        actual = (getattr(ctx, campo, '') or '').strip()
        if not actual:
            setattr(ctx, campo, valor)
            changed = True
        elif campo in _CAMPOS_EVOLUTIVOS and valor.lower() != actual.lower():
            setattr(ctx, campo, valor)
            changed = True
        elif permite_corregir and valor.lower() != actual.lower():
            setattr(ctx, campo, valor)
            changed = True
    if changed:
        meta = dict(ctx.metadata or {})
        meta['ultima_extraccion'] = timezone.now().isoformat()
        ctx.metadata = meta
        ctx.save()
    return ctx


def formatear_bloque_contexto_para_prompt(ctx) -> str:
    """Bloque obligatorio en el prompt de Nati (incluye anamnesis clínica)."""
    if not ctx:
        return ''
    d = ctx.to_dict() if hasattr(ctx, 'to_dict') else {}
    lineas = []
    etiquetas = {
        'cultivo': 'Cultivo',
        'etapa': 'Etapa fenológica',
        'region': 'Región',
        'municipio': 'Municipio',
        'vereda': 'Vereda / localidad',
        'clima': 'Clima / condición',
        'problema': 'Problema reportado',
    }
    for k, lbl in etiquetas.items():
        v = (d.get(k) or '').strip() if isinstance(d.get(k), str) else d.get(k)
        if k in ('latitud', 'longitud'):
            continue
        if v:
            lineas.append(f'- {lbl}: {v}')
    lat, lon = d.get('latitud'), d.get('longitud')
    if lat is not None and lon is not None:
        lineas.append(f'- Coordenadas guardadas: {lat}, {lon}')

    meta = getattr(ctx, 'metadata', None) or {}
    if isinstance(meta, dict):
        anamnesis = [
            ('extension_afectada', 'Extensión / parte afectada'),
            ('tiempo_problema', 'Tiempo y evolución'),
            ('manejo_previo', 'Manejo previo reportado'),
            ('fertilizacion_reciente', 'Fertilización / manejo reciente'),
        ]
        vistos = set()
        for key, lbl in anamnesis:
            val = (meta.get(key) or '').strip()
            if not val or key in vistos:
                continue
            # Evitar duplicar manejo_previo y fertilizacion_reciente si son iguales
            if key == 'fertilizacion_reciente' and val == (meta.get('manejo_previo') or '').strip():
                continue
            lineas.append(f'- {lbl}: {val}')
            vistos.add(key)

    if not lineas:
        return (
            'CONTEXTO AGRONÓMICO: parcial. Haga anamnesis breve (estilo consulta de campo): '
            'como máximo 2 preguntas concretas personalizadas antes de recomendar.'
        )
    pct = d.get('completitud_pct', ctx.completitud_pct() if ctx else 0)
    return (
        f'CONTEXTO AGRONÓMICO ESTRUCTURADO (completitud {pct}%):\n'
        + '\n'.join(lineas)
        + '\n\nUsa este contexto explícitamente (anamnesis de campo). '
        'No des recomendaciones genéricas fuera de él.'
    )


def campos_faltantes(ctx) -> list[str]:
    if not ctx:
        return ['cultivo', 'problema', 'region']
    faltan = []
    for k in ('cultivo', 'problema', 'region'):
        if not (getattr(ctx, k, '') or '').strip():
            faltan.append(k)
    return faltan
