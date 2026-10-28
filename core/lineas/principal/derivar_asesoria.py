"""Asesoría por pregunta: el modelo lee la necesidad y elige el agente.

Solo elige entre los agentes que la línea permite. Sin modelo (sin clave,
presupuesto agotado o falla de la API) devuelve 'sin_llm' y quien llama decide.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

AGENTE_PREGUNTA = 'sandbox_asesoria'
AGENTE_REPREGUNTA = 'sandbox_asesoria_repregunta'
_REPREGUNTA_SEG = 30 * 60

_TEMAS = (
    ('nat', 'su cultivo'),
    ('ventas', 'sus ventas'),
    ('finanzas', 'sus cuentas'),
    ('coach', 'su ánimo'),
    ('ia_campo', 'el uso de la tecnología'),
)

_PERFILES = {
    'nat': 'agrónomo: cultivos, café, plagas, enfermedades, suelo, abonos, cosecha, la finca y los animales',
    'ventas': 'ventas: precios, clientes, vender más, negociar, mercados y comercializar productos',
    'finanzas': 'finanzas: plata, cuentas, gastos, ahorro, deudas, créditos, presupuesto y costos',
    'coach': 'coach: ánimo, motivación, metas, hábitos, constancia y organizar el tiempo',
    'ia_campo': 'innovación e IA: usar el celular, WhatsApp, internet, la inteligencia artificial y la tecnología en el trabajo',
}


def _enumerar(partes: list[str]) -> str:
    if len(partes) <= 1:
        return ''.join(partes)
    return f"{', '.join(partes[:-1])} o {partes[-1]}"


def temas(permitidos) -> str:
    return _enumerar([tema for modo, tema in _TEMAS if modo in permitidos])


def texto_pregunta(permitidos, tope: int) -> str:
    cupo = f"Tiene hasta {tope} preguntas este mes.\n\n" if tope > 0 else ''
    return (
        f"¿Qué quiere mejorar hoy: {temas(permitidos)}? Escríbalo con sus palabras.\n\n"
        f"{cupo}"
        "_*menu* = menú principal._"
    )


def texto_repregunta(permitidos) -> str:
    return (
        "No me quedó claro en qué le podemos ayudar.\n\n"
        f"¿Es sobre {temas(permitidos)}? Cuéntenos un poco más con sus palabras.\n\n"
        "_*menu* = menú principal._"
    )


_COMANDOS = {
    'nat': ('Agrónomo', 'agronomo'),
    'ventas': ('Ventas', 'ventas'),
    'finanzas': ('Finanzas', 'finanzas'),
    'coach': ('Coach', 'coach'),
    'ia_campo': ('Innovación e IA', 'innovacion'),
}
CIERRE = '¿Era esto lo que necesitaba? Si no, escriba *menu*.'


def cierre_derivacion(secundario: str = '') -> str:
    """Pie de la primera respuesta tras derivar: el otro asesor que también sirve y la salida."""
    tema = dict(_TEMAS).get(secundario)
    if not tema or secundario not in _COMANDOS:
        return CIERRE
    nombre, comando = _COMANDOS[secundario]
    return (
        f"Esto también tiene que ver con {tema}; si quiere, lo vemos con {nombre}: escriba *{comando}*.\n\n"
        f"{CIERRE}"
    )


def _mensajes(texto: str, opciones: list[str], contexto: str = '', con_segundo: bool = False) -> list[dict]:
    perfiles = '\n'.join(f'- {modo}: {_PERFILES[modo]}' for modo in opciones)
    sistema = (
        "Usted lee el mensaje de una persona del campo en Colombia y elige el asesor que la puede ayudar.\n\n"
        f"Asesores:\n{perfiles}\n\n"
        f"Responda solo una palabra: {', '.join(opciones)} o ninguno. "
        "ninguno si el mensaje no dice qué necesita (un saludo, «no sé», «sí», un número suelto)."
    )
    if con_segundo:
        sistema += (
            " Si el mensaje también toca de lleno el tema de otro asesor, escriba ese otro como segunda "
            "palabra (por ejemplo: ventas finanzas). Si no, una sola palabra."
        )
    if contexto:
        sistema += (
            "\n\nLo que ya sabemos de la persona. Úselo solo para desempatar cuando el mensaje "
            f"sirve para dos asesores; manda lo que la persona escribe:\n{contexto}"
        )
    return [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': texto[:600]}]


def _etiquetas(respuesta: str, opciones: list[str]) -> list[str]:
    salida: list[str] = []
    for palabra in re.findall(r'[a-z_]+', (respuesta or '').lower()):
        if palabra in opciones and palabra not in salida:
            salida.append(palabra)
    return salida[:2]


def derivar_detalle(
    texto: str, *, telefono: str, permitidos, contexto: str = '', con_segundo: bool = False,
) -> tuple[str | None, str, str]:
    """(agente o None, 'llm' | 'sin_llm', segundo agente o ''). None con 'llm': no dice qué necesita."""
    pregunta = (texto or '').strip()
    opciones = [modo for modo, _ in _TEMAS if modo in permitidos]
    if not pregunta or not opciones:
        return None, 'llm', ''
    if len(opciones) == 1:
        return opciones[0], 'llm', ''
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    from core.presupuesto_llm import debe_degradar

    if not api_key or debe_degradar():
        return None, 'sin_llm', ''
    from core.openai_compat import cliente_openai, completar_chat, contexto_uso_llm

    token = contexto_uso_llm(telefono=telefono, agente='derivar_asesoria')
    try:
        respuesta = completar_chat(
            cliente_openai(api_key),
            getattr(settings, 'EKI_ASESORIA_MODELO', 'gpt-5-mini'),
            _mensajes(pregunta, opciones, contexto, con_segundo),
            20,
        )
    finally:
        token.var.reset(token)
    if not respuesta:
        return None, 'sin_llm', ''
    elegidos = _etiquetas(respuesta, opciones)
    agente = elegidos[0] if elegidos else None
    segundo = elegidos[1] if con_segundo and len(elegidos) > 1 else ''
    logger.info('derivar_asesoria agente=%s segundo=%s', agente or 'ninguno', segundo or '-')
    return agente, 'llm', segundo


def derivar(texto: str, *, telefono: str, permitidos, contexto: str = '') -> tuple[str | None, str]:
    """(agente o None, 'llm' | 'sin_llm'). None con 'llm': el mensaje no dice qué necesita."""
    agente, fuente, _ = derivar_detalle(texto, telefono=telefono, permitidos=permitidos, contexto=contexto)
    return agente, fuente


def _clave_repregunta(telefono: str) -> str:
    return f'eki:asesoria:repregunta:{telefono}'


def marcar_repregunta(telefono: str) -> bool:
    """True si es la primera vez y toca repreguntar. Si la caché falla, False: sale la lista."""
    from django.core.cache import cache
    from redis.exceptions import RedisError

    try:
        return bool(cache.add(_clave_repregunta(telefono), 1, timeout=_REPREGUNTA_SEG))
    except (RedisError, OSError):
        logger.exception('asesoria_repregunta_cache_fail')
        return False


def olvidar_repregunta(telefono: str) -> None:
    from django.core.cache import cache
    from redis.exceptions import RedisError

    try:
        cache.delete(_clave_repregunta(telefono))
    except (RedisError, OSError):
        logger.exception('asesoria_repregunta_cache_fail')
