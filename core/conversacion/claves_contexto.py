"""Cambiar de estado sin borrar lo que no es del estado.

Cuando un estado del motor termina o empieza, `contexto_temporal` se pisaba
entero. Con EKI_CONTEXTO_CONSERVA_CLAVES se conservan las claves de la
persona en la línea (curso en foco, certificado por enviar, empleabilidad) y
se borran las del estado que sale. Apagado, el resultado es el de siempre.
Este módulo no importa nada de core.
"""
from __future__ import annotations

from django.conf import settings

CLAVES_QUE_SOBREVIVEN = (
    'curso_activo_id',
    'cert_envio_pendiente',
    'radar_empleabilidad_activo',
    'empleabilidad_habilitado_en',
    'aliado_empleabilidad_objetivo_id',
    'mision_empleabilidad_id',
    'distancia_aliado_m',
    'ultimo_match_empleabilidad_aliado_id',
    'ultimo_match_empleabilidad_fecha',
    'ultimo_push_curso_id',
)


def contexto_limpio(actual: dict | None, nuevo: dict | None = None) -> dict | None:
    """El contexto del estado que entra (`nuevo`, o ninguno) más las claves que sobreviven."""
    if not getattr(settings, 'EKI_CONTEXTO_CONSERVA_CLAVES', False):
        return nuevo
    previo = actual if isinstance(actual, dict) else {}
    quedan = {k: v for k, v in previo.items() if k in CLAVES_QUE_SOBREVIVEN}
    quedan.update(nuevo or {})
    return quedan or None
