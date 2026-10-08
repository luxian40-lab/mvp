"""Cierres B de impacto en los agentes Meta. No inventa el dato."""
from __future__ import annotations

import logging
import unicodedata

from django.core.cache import cache

from core.nati import normalizar_telefono_whatsapp
from core.utils_telefono import estudiante_por_telefono

logger = logging.getLogger(__name__)

TTL_PENDIENTE = 7200

PREGUNTAS = {
    'finanzas': (
        'E1',
        'Para el reporte de impacto: en los últimos 3 meses, '
        '¿pudo cubrir los gastos del predio con lo que produjo? '
        'Responda *sí*, *no* o *en parte*.',
    ),
    'ventas': (
        'E2',
        'Para el reporte de impacto: este mes, ¿vendió *más*, *igual* o *menos* '
        'que el mes pasado?',
    ),
    'ia_campo': (
        'A1',
        'Para el reporte de impacto: en los últimos 3 meses, '
        '¿aplicó una recomendación de un agrónomo o de Nat? '
        'Responda *sí*, *no* o *parcial*.',
    ),
    'nat': (
        'A3',
        'Para el reporte de impacto: ¿usa el clima o Nat para decidir riego o siembra? '
        'Responda *sí*, *no* o *a veces*.',
    ),
}

_ACUSE = 'Gracias. Quedó registrado para el reporte de impacto de su organización.'


def _fold(texto: str) -> str:
    t = unicodedata.normalize('NFKD', (texto or '').strip().lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return ' '.join(t.split())


def _clave(telefono: str) -> str:
    return f'eki:impacto:pend:{normalizar_telefono_whatsapp(telefono)}'


def ya_tiene(telefono: str, codigo: str) -> bool:
    est = estudiante_por_telefono(telefono)
    if est is None:
        return False
    return codigo in (est.impacto_respuestas or {})


def preparar_cierre(agente: str, telefono: str) -> str:
    spec = PREGUNTAS.get(agente or '')
    if not spec:
        return ''
    codigo, pregunta = spec
    if ya_tiene(telefono, codigo):
        return ''
    clave = _clave(telefono)
    if cache.get(clave):
        return ''
    cache.set(clave, codigo, TTL_PENDIENTE)
    return pregunta


def anexar_cierre(agente: str, telefono: str, texto: str) -> str:
    pregunta = preparar_cierre(agente, telefono)
    if not pregunta:
        return texto
    return f'{texto}\n\n{pregunta}'


def enviar_cierre_pendiente(payload: dict, agente: str) -> None:
    tel = normalizar_telefono_whatsapp(str((payload or {}).get('From') or ''))
    pregunta = preparar_cierre(agente, tel)
    if not pregunta or not tel:
        return
    from core.sandbox_menu import enviar_texto_sandbox, sandbox_number

    destino = str((payload or {}).get('To') or sandbox_number())
    enviar_texto_sandbox(tel, destino, pregunta, agente='sandbox_impacto')


def _parsear(body: str, codigo: str) -> dict | None:
    t = _fold(body)
    if not t:
        return None
    if codigo == 'E2':
        if t in ('mas', 'mayor', 'subi', 'subio', 'aumente', 'aumento'):
            return {'valor': 'mas', 'positivo': True, 'evidencia': 'B'}
        if t in ('igual', 'mismo', 'parecido'):
            return {'valor': 'igual', 'positivo': False, 'evidencia': 'B'}
        if t in ('menos', 'menor', 'bajo', 'baje'):
            return {'valor': 'menos', 'positivo': False, 'evidencia': 'B'}
        return None
    if t in ('si', 'sip', 'claro'):
        return {'valor': 'si', 'positivo': True, 'evidencia': 'B'}
    if t in ('no'):
        return {'valor': 'no', 'positivo': False, 'evidencia': 'B'}
    if t in ('en parte', 'enparte', 'parcial', 'a veces', 'aveces'):
        return {'valor': 'parcial', 'positivo': True, 'evidencia': 'B'}
    return None


def capturar_si_pendiente(telefono: str, body: str) -> str | None:
    codigo = cache.get(_clave(telefono))
    if not codigo:
        return None
    valor = _parsear(body, str(codigo))
    if valor is None:
        return None
    est = estudiante_por_telefono(telefono)
    if est is None:
        cache.delete(_clave(telefono))
        return None
    data = dict(est.impacto_respuestas or {})
    data[str(codigo)] = valor
    est.impacto_respuestas = data
    est.save(update_fields=['impacto_respuestas'])
    cache.delete(_clave(telefono))
    return _ACUSE
