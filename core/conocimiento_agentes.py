"""Conocimiento aprobado → prompt de los agentes; conversaciones → sugerencias para revisar."""
from __future__ import annotations

import logging
import random
import re

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

AGENTES = ('coach', 'ia_campo', 'ventas', 'finanzas')
_CACHE_KEY = 'conocimiento_agente:v1:{agente}'
_CACHE_SEGUNDOS = 300
_MAX_CHARS_PROMPT = 2500
_MIN_CHARS_PREGUNTA = 30

_RE_CORREO = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_RE_NUMERO = re.compile(r'\+?\d[\d\s-]{6,}\d')


def limpiar_cache_conocimiento() -> None:
    try:
        cache.delete_many([_CACHE_KEY.format(agente=a) for a in AGENTES])
    except Exception:
        logger.exception('conocimiento_cache_clear_fail')


def bloque_conocimiento(agente: str) -> str:
    """Texto que se suma al system prompt. Cacheado 5 min: no consulta la DB por mensaje."""
    if agente not in AGENTES:
        return ''
    key = _CACHE_KEY.format(agente=agente)
    try:
        guardado = cache.get(key)
    except Exception:
        guardado = None
    if guardado is not None:
        return guardado
    from core.models_agentes import ConocimientoAgente

    filas = ConocimientoAgente.objects.filter(
        estado=ConocimientoAgente.ESTADO_APROBADO,
        agente__in=(agente, ConocimientoAgente.AGENTE_TODOS),
    ).order_by('orden', '-actualizado_en').values_list('tipo', 'titulo', 'contenido')
    reglas, datos = [], []
    for tipo, titulo, contenido in filas:
        linea = f"- {titulo.strip()}: {' '.join(contenido.split())}"
        (reglas if tipo == ConocimientoAgente.TIPO_INSTRUCCION else datos).append(linea)
    partes = []
    if reglas:
        partes.append('REGLAS ADICIONALES DEL EQUIPO EKI\n' + '\n'.join(reglas))
    if datos:
        partes.append(
            'CONOCIMIENTO VALIDADO POR EKI (úselo si aplica; no lo recite completo)\n' + '\n'.join(datos)
        )
    texto = '\n\n'.join(partes)[:_MAX_CHARS_PROMPT]
    try:
        cache.set(key, texto, _CACHE_SEGUNDOS)
    except Exception:
        pass
    return texto


def _sin_datos_personales(texto: str) -> str:
    texto = _RE_CORREO.sub('[correo]', texto or '')
    return _RE_NUMERO.sub('[número]', texto)


def _porcentaje_captura() -> int:
    try:
        return max(0, min(int(getattr(settings, 'AGENTES_CAPTURA_PORCENTAJE', 15)), 100))
    except (TypeError, ValueError):
        return 15


def capturar_sugerencia(agente: str, pregunta: str, respuesta: str) -> None:
    """Guarda una muestra de conversaciones como «sugerido». Nunca entra al prompt sin aprobación."""
    if agente not in AGENTES:
        return
    pregunta = _sin_datos_personales((pregunta or '').strip())[:1500]
    respuesta = _sin_datos_personales((respuesta or '').strip())[:2000]
    if len(pregunta) < _MIN_CHARS_PREGUNTA or not respuesta:
        return
    if random.randint(1, 100) > _porcentaje_captura():
        return
    from core.models_agentes import ConocimientoAgente

    if ConocimientoAgente.objects.filter(
        agente=agente,
        estado=ConocimientoAgente.ESTADO_SUGERIDO,
        pregunta_origen__iexact=pregunta,
    ).exists():
        return
    ConocimientoAgente.objects.create(
        agente=agente,
        tipo=ConocimientoAgente.TIPO_CONOCIMIENTO,
        titulo=pregunta[:157] + ('...' if len(pregunta) > 157 else ''),
        contenido=respuesta,
        estado=ConocimientoAgente.ESTADO_SUGERIDO,
        origen=ConocimientoAgente.ORIGEN_CONVERSACION,
        pregunta_origen=pregunta,
        respuesta_origen=respuesta,
    )
