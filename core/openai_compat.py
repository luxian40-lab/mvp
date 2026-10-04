"""Compatibilidad OpenAI: gpt-5* usa max_completion_tokens (+ reasoning_effort)."""

from __future__ import annotations

import contextvars
import logging
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)

_uso = contextvars.ContextVar('uso_llm', default=None)


def contexto_uso_llm(*, cliente_id=None, telefono: str = '', agente: str = ''):
    """Quien llama al modelo anota a quién cobrar. No guarda el teléfono en claro."""
    return _uso.set({'cliente_id': cliente_id, 'telefono': telefono or '', 'agente': agente or ''})


def _registrar_uso(modelo: str, texto: str, resp) -> None:
    """No tumba la respuesta si el ledger falla."""
    try:
        from core.locks import telefono_hash
        from core.models_uso_llm import UsoLLM

        ctx = _uso.get() or {}
        usage = getattr(resp, 'usage', None)
        tokens_in = int(getattr(usage, 'prompt_tokens', 0) or 0) if usage else 0
        tokens_out = int(getattr(usage, 'completion_tokens', 0) or 0) if usage else 0
        detalle = getattr(usage, 'completion_tokens_details', None) if usage else None
        razon = getattr(detalle, 'reasoning_tokens', None) if detalle is not None else None
        estimado = usage is None
        if estimado:
            tokens_out = max(1, len(texto) // 4)
        precios = getattr(settings, 'LLM_PRECIOS_USD_POR_MTOK', {}) or {}
        par = precios.get(modelo) or precios.get((modelo or '').split('/')[-1])
        if par:
            costo = (Decimal(tokens_in) * Decimal(par[0]) + Decimal(tokens_out) * Decimal(par[1])) / Decimal(1000000)
        else:
            costo = Decimal('0')
            estimado = True
        UsoLLM.objects.create(
            cliente_id=ctx.get('cliente_id'),
            telefono_hash=telefono_hash(ctx.get('telefono') or '')[:64],
            agente=(ctx.get('agente') or '')[:64],
            modelo=(modelo or '')[:64],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tokens_razonamiento=None if razon is None else int(razon),
            costo_usd_est=costo,
            estimado=estimado,
        )
        from core.presupuesto_llm import anotar_gasto

        anotar_gasto(costo, ctx.get('cliente_id'))
    except Exception:
        logger.exception('uso_llm_no_guardo')


# Por debajo del soft_time_limit=45 de las tareas del webhook.
LLM_HTTP_TIMEOUT_SEG = 30


def cliente_openai(api_key: str):
    from openai import OpenAI

    return OpenAI(api_key=api_key, timeout=LLM_HTTP_TIMEOUT_SEG)


def _modelo_nuevo_api(modelo: str) -> bool:
    m = (modelo or '').strip().lower()
    if not m:
        return False
    return (
        m.startswith('gpt-5')
        or m.startswith('o1')
        or m.startswith('o3')
        or m.startswith('o4')
    )


def chat_completion_token_kwargs(
    modelo: str,
    max_out: int,
    temperature: float | None = None,
    *,
    reasoning_effort: str | None = None,
) -> dict:
    """
    Kwargs de tokens (+ temperatura / reasoning) para chat.completions.create.

    gpt-5 / o-series:
    - no aceptan max_tokens (usar max_completion_tokens)
    - suelen gastar el presupuesto en reasoning_tokens si el tope es bajo
    - reasoning_effort=low|minimal deja tokens para el texto visible
    """
    max_out = max(1, int(max_out or 1))
    kwargs: dict = {}
    if _modelo_nuevo_api(modelo):
        # Más margen: reasoning + respuesta visible
        kwargs['max_completion_tokens'] = max(max_out, 900)
        effort = reasoning_effort
        if effort is None:
            effort = getattr(settings, 'BOT_COMERCIAL_REASONING_EFFORT', 'low') or 'low'
        effort = str(effort).strip().lower()
        if effort in ('minimal', 'low', 'medium', 'high'):
            kwargs['reasoning_effort'] = effort
    else:
        kwargs['max_tokens'] = max_out
        if temperature is not None:
            kwargs['temperature'] = temperature
    return kwargs


def completar_chat(client, modelo: str, messages: list, max_out: int, temperature: float | None = None) -> str:
    """Dos intentos. Si el primero viene vacío o falla, el segundo baja el razonamiento.

    gpt-5 puede gastar el cupo pensando y devolver content vacío. Un fallo de red
    en el primer intento no debe saltarse el segundo.
    """
    intentos = (
        chat_completion_token_kwargs(modelo, max_out, temperature),
        chat_completion_token_kwargs(
            modelo, max(max_out, 500), temperature, reasoning_effort='minimal',
        ),
    )
    for i, kwargs in enumerate(intentos):
        try:
            resp = client.chat.completions.create(
                model=modelo,
                messages=messages,
                timeout=22,
                **kwargs,
            )
            msg = resp.choices[0].message
            texto = (getattr(msg, 'content', None) or '').strip()
            if texto:
                _registrar_uso(modelo, texto, resp)
                return texto
        except Exception:
            logger.exception('llm_completado_intento_%s modelo=%s', i, modelo)
    return ''
