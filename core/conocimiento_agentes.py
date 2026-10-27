"""Conocimiento aprobado → prompt de los agentes; conversaciones → sugerencias para revisar."""
from __future__ import annotations

import logging
import random
import re

from django.conf import settings
from django.core.cache import cache

from core.models_agentes import (  # noqa: F401
    _CACHE_KEY,
    AGENTES,
    limpiar_cache_conocimiento,
)

logger = logging.getLogger(__name__)

_CACHE_SEGUNDOS = 300
_MAX_CHARS_PROMPT = 2500
_MIN_CHARS_PREGUNTA = 30

_RE_CORREO = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_RE_NUMERO = re.compile(r'\+?\d[\d\s-]{6,}\d')


def cliente_id_para_conocimiento(telefono: str):
    """Organización de esa persona. Vacío si no tiene."""
    tel = (telefono or '').strip()
    if not tel:
        return None
    from core.models import Estudiante, SesionComercial

    cid = Estudiante.objects.filter(telefono=tel).values_list('cliente_id', flat=True).first()
    if cid:
        return cid
    return SesionComercial.objects.filter(telefono=tel).values_list('cliente_id', flat=True).first()


def bloque_conocimiento(agente: str, cliente_id=None) -> str:
    """Texto que se suma al system prompt. Cacheado 5 min: no consulta la DB por mensaje.

    Sin cliente solo entra lo de alcance Todos. Con cliente, también lo de esa organización.
    """
    if agente not in AGENTES:
        return ''
    key = _CACHE_KEY.format(agente=agente, cliente=cliente_id or '0')
    try:
        guardado = cache.get(key)
    except Exception:
        guardado = None
    if guardado is not None:
        return guardado
    from django.db.models import Q

    from core.models_agentes import ConocimientoAgente

    filas = ConocimientoAgente.objects.filter(
        estado=ConocimientoAgente.ESTADO_APROBADO,
        agente__in=(agente, ConocimientoAgente.AGENTE_TODOS),
    )
    if cliente_id:
        filas = filas.filter(
            Q(alcance=ConocimientoAgente.ALCANCE_TODOS) | Q(cliente_id=cliente_id)
        )
    else:
        filas = filas.exclude(alcance=ConocimientoAgente.ALCANCE_CLIENTE)
    filas = filas.order_by('orden', '-actualizado_en').values_list('tipo', 'titulo', 'contenido')
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


_CODIGOS_CONOCIMIENTO = {
    'coach': 'coach',
    'ia_campo': 'ia_campo',
    'profe': 'ia_campo',
    'ventas': 'ventas',
    'finanzas': 'finanzas',
    'cafe': 'cafe',
}


def copiar_candidata_a_agentes(candidata, usuario) -> int:
    """Copia la respuesta ya revisada al conocimiento aprobado de cada agente elegido."""
    from core.models_agentes import ConocimientoAgente

    codigos = candidata.agentes or []
    if isinstance(codigos, str):
        codigos = [codigos]
    texto = _sin_datos_personales(
        (candidata.respuesta_revisada or candidata.respuesta_nati or '').strip()
    )[:2000]
    if not texto:
        return 0
    pregunta = _sin_datos_personales((candidata.pregunta or '').strip())[:1500]
    if len(pregunta) > 157:
        titulo = pregunta[:157] + '...'
    else:
        titulo = pregunta or 'Conocimiento revisado'
    alcance = candidata.alcance or ConocimientoAgente.ALCANCE_TODOS
    cliente = candidata.cliente if alcance == ConocimientoAgente.ALCANCE_CLIENTE else None
    if alcance == ConocimientoAgente.ALCANCE_CLIENTE and cliente is None:
        return 0
    creados = 0
    for crudo in codigos:
        agente = _CODIGOS_CONOCIMIENTO.get(crudo)
        if not agente:
            continue
        ConocimientoAgente.objects.update_or_create(
            agente=agente,
            origen=ConocimientoAgente.ORIGEN_CONVERSACION,
            pregunta_origen=pregunta,
            cliente=cliente,
            defaults={
                'tipo': ConocimientoAgente.TIPO_CONOCIMIENTO,
                'titulo': titulo[:160],
                'contenido': texto,
                'estado': ConocimientoAgente.ESTADO_APROBADO,
                'respuesta_origen': texto,
                'revisado_por': usuario,
                'alcance': alcance,
            },
        )
        creados += 1
    return creados
