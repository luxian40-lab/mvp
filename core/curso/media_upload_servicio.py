# -*- coding: utf-8 -*-
"""Validación previa de un archivo antes de subirlo.

No importa el Module Builder ni Unfold. No habla con S3 y no cambia rutas.
La vista que recibe el POST decide el permiso y el destino.
"""
from __future__ import annotations

import os

from django.conf import settings


_VIDEO = {'.mp4', '.m4v', '.mov', '.webm', '.3gp'}
_IMAGEN = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
_AUDIO = {'.mp3', '.ogg', '.m4a', '.aac', '.amr', '.opus', '.wav'}
_PDF = {'.pdf'}


def clasificar_nombre(nombre: str) -> str:
    ext = os.path.splitext((nombre or '').lower())[1]
    if ext in _VIDEO:
        return 'video'
    if ext in _IMAGEN:
        return 'imagen'
    if ext in _AUDIO:
        return 'audio'
    if ext in _PDF:
        return 'pdf'
    return ''


def topes_bytes() -> dict[str, int]:
    return {
        'video': int(getattr(settings, 'WHATSAPP_VIDEO_MAX_BYTES', 16 * 1024 * 1024)),
        'imagen': int(getattr(settings, 'WHATSAPP_IMAGE_MAX_BYTES', 5 * 1024 * 1024)),
        'audio': int(getattr(settings, 'WHATSAPP_AUDIO_MAX_BYTES', 16 * 1024 * 1024)),
        'pdf': int(getattr(settings, 'WHATSAPP_DOCUMENT_MAX_BYTES', 100 * 1024 * 1024)),
    }


def validar_archivo(nombre: str, tamano: int, content_type: str = '') -> dict:
    """Devuelve ok o un error en español. No escribe nada."""
    tipo = clasificar_nombre(nombre)
    ctype = (content_type or '').lower()
    if not tipo:
        if ctype.startswith('video/'):
            tipo = 'video'
        elif ctype.startswith('image/'):
            tipo = 'imagen'
        elif ctype.startswith('audio/'):
            tipo = 'audio'
        elif ctype == 'application/pdf':
            tipo = 'pdf'
    if not tipo:
        return {
            'ok': False,
            'tipo': '',
            'error': 'Ese tipo de archivo no está permitido. Use video, imagen, audio o PDF.',
        }
    try:
        n = int(tamano)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return {'ok': False, 'tipo': tipo, 'error': 'El archivo está vacío.'}
    tope = topes_bytes()[tipo]
    if n > tope:
        mb = max(1, tope // (1024 * 1024))
        return {
            'ok': False,
            'tipo': tipo,
            'error': f'El archivo es demasiado grande. El tope para {tipo} es {mb} MB.',
        }
    return {'ok': True, 'tipo': tipo, 'error': ''}
