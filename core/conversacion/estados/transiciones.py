"""Tabla explícita de transiciones de estado (fase G6).

No reemplaza BARRERAS/AGENTES (despacho de lectura). Solo documenta y aplica
escrituras de estado_chat / estado_onboarding. Con flags off, aplicar() hace
el mismo setattr que hoy; la validación solo advierte.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.conf import settings

logger = logging.getLogger(__name__)

BARRERAS_CHAT: frozenset[tuple[str, str]] = frozenset({
    ('ESPERANDO_HABEAS_DATA', 'ESPERANDO_CEDULA'),
    ('ESPERANDO_CEDULA', 'CONFIRMANDO_DATOS'),
    ('CONFIRMANDO_DATOS', 'ACTIVO'),
    ('ESPERANDO_HABEAS_DATA', 'ACTIVO'),
    ('ESPERANDO_CEDULA', 'ACTIVO'),
    ('ACTIVO', 'ACTIVO'),
    ('CORRIGIENDO_DATOS', 'ACTIVO'),
    ('ACTIVO', 'CORRIGIENDO_DATOS'),
})

MOTOR_ONBOARDING: frozenset[tuple[str, str]] = frozenset({
    ('completado', 'esperando_respuesta_reto'),
    ('esperando_respuesta_reto', 'completado'),
    ('completado', 'esperando_respuesta_modulo'),
    ('esperando_respuesta_modulo', 'completado'),
    ('completado', 'esperando_respuesta_asistente'),
    ('esperando_respuesta_asistente', 'esperando_respuesta_reto'),
    ('completado', 'esperando_seleccion_curso'),
    ('esperando_seleccion_curso', 'completado'),
    ('completado', 'curso_finalizado'),
    ('esperando_respuesta_pregunta_abierta_final', 'completado'),
    ('completado', 'esperando_respuesta_pregunta_abierta_final'),
})


def _log_activo() -> bool:
    return bool(getattr(settings, 'EKI_LOG_TRANSICIONES_ESTADO', False))


def _validar_activo() -> bool:
    return bool(getattr(settings, 'EKI_VALIDAR_TRANSICIONES', False))


def _arista_ok(tabla: Iterable[tuple[str, str]], origen: str, destino: str) -> bool:
    if origen == destino:
        return True
    return (origen, destino) in tabla


def aplicar(
    estudiante,
    *,
    estado_chat: str | None = None,
    estado_onboarding: str | None = None,
    fuente: str = '',
) -> None:
    """Asigna campos de estado. No guarda: el caller sigue haciendo save()."""
    if estado_chat is not None:
        viejo = getattr(estudiante, 'estado_chat', None) or ''
        if _validar_activo() and not _arista_ok(BARRERAS_CHAT, viejo, estado_chat):
            logger.warning(
                'transicion_chat_desconocida %s -> %s fuente=%s est=%s',
                viejo, estado_chat, fuente, getattr(estudiante, 'pk', None),
            )
        if _log_activo():
            logger.debug(
                'transicion_chat %s -> %s fuente=%s est=%s',
                viejo, estado_chat, fuente, getattr(estudiante, 'pk', None),
            )
        estudiante.estado_chat = estado_chat
    if estado_onboarding is not None:
        viejo = getattr(estudiante, 'estado_onboarding', None) or ''
        if _validar_activo() and not _arista_ok(MOTOR_ONBOARDING, viejo, estado_onboarding):
            logger.warning(
                'transicion_onboarding_desconocida %s -> %s fuente=%s est=%s',
                viejo, estado_onboarding, fuente, getattr(estudiante, 'pk', None),
            )
        if _log_activo():
            logger.debug(
                'transicion_onboarding %s -> %s fuente=%s est=%s',
                viejo, estado_onboarding, fuente, getattr(estudiante, 'pk', None),
            )
        estudiante.estado_onboarding = estado_onboarding
