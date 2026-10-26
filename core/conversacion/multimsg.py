"""Lector único del formato legado [MULTI_MSG] / [SEP]. No importa nada de core."""
from __future__ import annotations

MULTI_MSG = '[MULTI_MSG]'
SEP = '[SEP]'
MEDIA = '[MEDIA:'
DELAY = '[DELAY:'


def partir_sep(texto: str) -> list[str]:
    return texto.split(SEP)


def partes_multimsg(texto: str) -> list[str]:
    """Partes de un texto; quita [MULTI_MSG] solo si va al inicio. No filtra vacías ni recorta."""
    if texto.startswith(MULTI_MSG):
        texto = texto[len(MULTI_MSG):]
    return partir_sep(texto)
