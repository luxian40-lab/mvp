"""Lector único de las marcas que el curso pone en un texto armado.

Solo lee. Quien envía decide cómo pausar, qué hacer con una plantilla y por
dónde sale cada parte. Solo importa `core.conversacion.multimsg`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.conversacion.multimsg import MULTI_MSG, partir_sep

_PREFIJO_PLANTILLA = '[SEND_TEMPLATE:'
_PAUSA = re.compile(r'^\[DELAY:(\d+)\]$')
_PLANTILLA = re.compile(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]')
_MEDIA = re.compile(r'\[MEDIA:(.*?)\]')

TEXTO = 'texto'
PAUSA = 'pausa'
PLANTILLA = 'plantilla'


@dataclass(frozen=True)
class Parte:
    tipo: str
    texto: str = ''
    media: str | None = None
    segundos: int = 0
    sid: str = ''


def es_marcado(texto: str | None) -> bool:
    return str(texto or '').startswith(MULTI_MSG)


def separar_media(texto: str) -> tuple[str, str | None]:
    """Quita la primera marca de media y devuelve (texto, url o None)."""
    encontrada = _MEDIA.search(texto or '')
    if not encontrada:
        return texto, None
    return texto.replace(encontrada.group(0), '').strip(), (encontrada.group(1) or '').strip() or None


def partes(texto: str | None) -> list[Parte]:
    """Partes en orden. Las vacías no cuentan. La plantilla conserva su texto crudo."""
    salida: list[Parte] = []
    for trozo in partir_sep(str(texto or '').replace(MULTI_MSG, '', 1)):
        limpio = (trozo or '').strip()
        if not limpio:
            continue
        pausa = _PAUSA.match(limpio)
        if pausa:
            salida.append(Parte(PAUSA, segundos=int(pausa.group(1))))
            continue
        if limpio.startswith(_PREFIJO_PLANTILLA):
            sid = _PLANTILLA.match(limpio)
            salida.append(Parte(PLANTILLA, texto=limpio, sid=sid.group(1) if sid else ''))
            continue
        cuerpo, media = separar_media(limpio)
        salida.append(Parte(TEXTO, texto=cuerpo, media=media))
    return salida
