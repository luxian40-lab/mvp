"""
Feature registry IA — activar/desactivar capacidades por cliente o curso (Parte 2B).

Resolución: default global → override Cliente (JSON futuro) → override Curso.
"""

from __future__ import annotations

from typing import Any

DEFAULT_AI_CAPABILITIES: dict[str, dict[str, Any]] = {
    'checkpoint_dario': {
        'default': True,
        'label': 'Checkpoint Darío/facilitadora',
        'por_cliente': True,
    },
    'rag_comercial': {
        'default': True,
        'label': 'RAG comercial Nat',
        'por_cliente': True,
    },
    'diagnostico_agro': {
        'default': True,
        'label': 'Diagnóstico agronómico Nat',
        'por_cliente': True,
    },
    'tutor_ia_modulo': {
        'default': True,
        'label': 'Tutor IA por módulo',
        'por_curso': True,
    },
    'eventos_ia': {
        'default': True,
        'label': 'Persistencia EventoIA',
        'por_cliente': False,
    },
    'nati_structured_context': {
        'default': True,
        'label': 'Contexto agronómico estructurado Nat',
        'por_cliente': True,
    },
    'hitl_rag_publish': {
        'default': True,
        'label': 'Cola HITL Knowledge Studio',
        'por_cliente': True,
    },
}


def resolver_ai_capability(
    key: str,
    *,
    cliente=None,
    curso=None,
    default: bool | None = None,
) -> bool:
    """True si la capacidad IA está habilitada para el contexto dado."""
    spec = DEFAULT_AI_CAPABILITIES.get(key)
    if not spec:
        return bool(default) if default is not None else False

    base = spec.get('default', True)
    if default is not None:
        base = default

    overrides = {}
    if cliente is not None:
        overrides = getattr(cliente, 'ai_capabilities_override', None) or {}
        if isinstance(overrides, dict) and key in overrides:
            return bool(overrides[key])

    if curso is not None:
        curso_over = getattr(curso, 'ai_capabilities_override', None) or {}
        if isinstance(curso_over, dict) and key in curso_over:
            return bool(curso_over[key])

    return bool(base)


def listar_ai_capabilities() -> dict[str, dict[str, Any]]:
    return dict(DEFAULT_AI_CAPABILITIES)
