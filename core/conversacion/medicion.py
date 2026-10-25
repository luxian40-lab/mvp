"""Duración de cada turno del motor, por estado de entrada y por línea. Solo mide.

No importa nada de core: quien llama lee el estado y la línea antes del turno.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass

logger = logging.getLogger('eki.motor.turno')


@dataclass(frozen=True)
class EntradaTurno:
    estado: str
    chat: str
    linea: str
    canal: str


@contextmanager
def medir_turno(entrada: EntradaTurno | None):
    """None no mide (callback de estado o medición apagada)."""
    if entrada is None:
        yield
        return
    inicio = time.monotonic()
    try:
        yield
    finally:
        ms = int((time.monotonic() - inicio) * 1000)
        logger.info(
            'motor_turno estado=%s chat=%s linea=%s canal=%s ms=%d',
            entrada.estado, entrada.chat, entrada.linea, entrada.canal, ms,
            extra={'motor_turno': {**asdict(entrada), 'ms': ms}},
        )
