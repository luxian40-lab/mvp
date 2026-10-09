"""Respuesta de PQRS por la línea Meta. No usa Twilio."""
from __future__ import annotations


def enviar_respuesta_pqrs_meta(telefono: str, texto: str, *, agente: str = '') -> dict:
    from core.sandbox_canal import enviar_meta

    return enviar_meta(
        telefono,
        texto,
        canal_evento='pqrs',
        agente_evento=(agente or 'pqrs')[:50],
    )
