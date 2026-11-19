"""Pausas entre burbujas: Celery countdown, sin time.sleep en el worker.

Bloque 2 / W1: cero sleep en conversación, líneas y avisos. Las pausas
DELAY y el ritmo de avisos encolan con countdown. El hueco corto entre
partes ya no bloquea el worker (sigue el siguiente mensaje al tiro).
"""
from __future__ import annotations

import math
from typing import Callable, Literal

from core.conversacion.marcas import PAUSA, Parte, partes

ResultadoRecorrido = Literal['done', 'deferred', 'fail']


def delays_por_celery() -> bool:
    """Siempre True: el worker no duerme. El setting queda por compat."""
    return True


def dormir(segundos: float) -> None:
    """No-op. Bloque 2 prohíbe time.sleep en este camino."""
    return


def encolar_tarea(tarea: str, countdown: float) -> None:
    from celery import current_app

    segundos = max(0, int(math.ceil(float(countdown or 0))))
    current_app.send_task(tarea, countdown=segundos)


def pausar_lote(segundos: float, *, tarea: str) -> bool:
    """Ritmo entre avisos: encola y el caller corta. True = salir del bucle."""
    if not segundos or segundos <= 0:
        return False
    encolar_tarea(tarea, segundos)
    return True


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
            encolar_continuacion(
                canal=canal,
                countdown=parte.segundos,
                payload={**payload_continuacion, 'desde_idx': i + 1, 'texto': texto},
            )
            return 'deferred'
        if not on_parte(parte):
            return 'fail'
        i += 1
        if i >= len(lista):
            break
        # hueco_entre_partes: no se duerme; el worker sigue.
        _ = hueco_entre_partes
    return 'done'
