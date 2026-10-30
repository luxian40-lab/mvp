"""Bandera de token Meta inválido. No guarda ni registra el token."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

CLAVE_TOKEN_INVALIDO = 'eki:meta:token_invalido'
TTL_TOKEN_INVALIDO_SEG = 15 * 60


def marcar_token_invalido() -> None:
    logger.critical('meta_token_invalido')
    try:
        from core.locks import _cliente_redis

        _cliente_redis().set(CLAVE_TOKEN_INVALIDO, '1', ex=TTL_TOKEN_INVALIDO_SEG)
    except Exception:
        logger.exception('meta_token_bandera_redis')


def token_invalido() -> bool:
    try:
        from core.locks import _cliente_redis

        return bool(_cliente_redis().get(CLAVE_TOKEN_INVALIDO))
    except Exception:
        return False


def es_token_invalido(err: dict) -> bool:
    code = str((err or {}).get('code') or '')
    tipo = str((err or {}).get('type') or '')
    message = str((err or {}).get('message') or '').lower()
    if code == '190':
        return True
    if tipo != 'OAuthException':
        return False
    return any(
        frase in message
        for frase in ('expired', 'invalid oauth', 'error validating access token', 'session has expired')
    )
