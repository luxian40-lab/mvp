"""Pausas entre burbujas: sleep hoy, Celery countdown con flag.

Flag off: igual que siempre (time.sleep). Flag on: no duerme el worker
en una pausa DELAY; encola la continuación con countdown. El hueco de
0.5 s entre partes sigue en sleep (tope liviano de ritmo).
"""
from __future__ import annotations

import math
import time
from typing import Callable, Literal

from django.conf import settings

from core.conversacion.marcas import PAUSA, Parte, partes

ResultadoRecorrido = Literal['done', 'deferred', 'fail']


def delays_por_celery() -> bool:
    return bool(getattr(settings, 'EKI_ENTREGA_DELAYS_CELERY', False))


def dormir(segundos: float) -> None:
    if segundos and segundos > 0:
        time.sleep(float(segundos))


def encolar_continuacion(
    *,
    canal: str,
    countdown: float,
    payload: dict,
) -> None:
    from celery import current_app

    segundos = max(0, int(math.ceil(float(countdown or 0))))
    current_app.send_task(
        'core.tasks.continuar_entrega_marcada_async',
        kwargs={'canal': canal, **payload},
        countdown=segundos,
    )


def recorrer_partes(
    texto: str,
    *,
    desde_idx: int,
    on_parte: Callable[[Parte], bool],
    canal: str,
    payload_continuacion: dict,
    hueco_entre_partes: float = 0.5,
) -> ResultadoRecorrido:
    """Recorre partes desde desde_idx. on_parte False = fallo de envío."""
    lista = partes(texto)
    i = max(0, int(desde_idx or 0))
    while i < len(lista):
        parte = lista[i]
        if parte.tipo == PAUSA:
            if delays_por_celery():
                encolar_continuacion(
                    canal=canal,
                    countdown=parte.segundos,
                    payload={**payload_continuacion, 'desde_idx': i + 1, 'texto': texto},
                )
                return 'deferred'
            dormir(parte.segundos)
            i += 1
            continue
        if not on_parte(parte):
            return 'fail'
        i += 1
        if i >= len(lista):
            break
        dormir(hueco_entre_partes)
    return 'done'
