"""Compatibilidad OpenAI: gpt-5* usa max_completion_tokens (+ reasoning_effort)."""

from __future__ import annotations

from django.conf import settings


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
