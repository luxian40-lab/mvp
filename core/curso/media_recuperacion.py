"""Recuperación de media de curso: reenvío cuando el video/adjunto no llegó."""
from __future__ import annotations

import re
import unicodedata

_KEYWORDS = frozenset({
    'reenvia video',
    'reenvía video',
    'reenviar video',
    'reenvia el video',
    'reenvía el video',
    'reenviar el video',
    'no me llego el video',
    'no me llegó el video',
    'no llego el video',
    'no llegó el video',
    'video no llego',
    'video no llegó',
    'manda otra vez el video',
    'manda de nuevo el video',
    'reenvia multimedia',
    'reenvía multimedia',
    'reenviar multimedia',
    'reenvia material',
    'reenvía material',
    'reenviar material',
    'reenvia',
    'reenvía',
    'reenviar',
})


def _norm(texto: str) -> str:
    t = (texto or '').strip().lower()
    t = ''.join(
        c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn'
    )
    t = re.sub(r'\s+', ' ', t)
    return t.strip(' .!?,;:')


def es_pedido_reenvio_media(mensaje: str) -> bool:
    t = _norm(mensaje)
    if not t:
        return False
    if t in _KEYWORDS:
        return True
    # Frases cortas con "reenvi" + (video|material|modulo|módulo)
    if 'reenvi' in t and any(
        k in t for k in ('video', 'material', 'multimedia', 'modulo', 'módulo', 'audio')
    ):
        return True
    if ('no me llego' in t or 'no llego' in t or 'no llega' in t) and (
        'video' in t or 'material' in t or 'audio' in t
    ):
        return True
    return False


def _es_agri_duda_media(estudiante, mensaje: str) -> bool:
    """Solo AgriCapital: «no descarga», «no puedo ver la imagen», etc."""
    from core.lineas.agricapital_experiencia import (
        es_duda_media_agricapital,
        estudiante_es_agricapital,
    )

    return estudiante_es_agricapital(estudiante) and es_duda_media_agricapital(mensaje)


def intentar_reenvio_media_curso(estudiante, mensaje: str) -> str | None:
    """
    Si el mensaje pide reenviar video/material, reenvía el paso/módulo actual
    sin avanzar el progreso. Devuelve texto (puede ser [MULTI_MSG]…) o None.

    AgriCapital además reconoce dudas de descarga/imagen/video; si no hay
    media que reenviar, responde con tip (sin «No entendí»).
    """
    agri_duda = _es_agri_duda_media(estudiante, mensaje)
    if not es_pedido_reenvio_media(mensaje) and not agri_duda:
        return None
    from core.pqrs_acciones import texto_reenviar_modulo

    out = texto_reenviar_modulo(estudiante)
    if out:
        try:
            from core.media_entrega import marcar_paquete_recuperado_por_telefono
            marcar_paquete_recuperado_por_telefono(estudiante.telefono or '')
        except Exception:
            pass
        return out
    if agri_duda:
        from core.lineas.agricapital_experiencia import texto_tip_media_agricapital

        return texto_tip_media_agricapital()
    return None
