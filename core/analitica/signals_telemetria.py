"""Signals de telemetría de aprendizaje (Centro de Éxito)."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='core.ModuloCompletado')
def telemetria_modulo_completado(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from core.models import EstudianteEventoAprendizaje
        from core.telemetria import registrar_evento

        prog = instance.progreso
        est = prog.estudiante
        registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_MODULO_COMPLETADO,
            estudiante=est,
            curso=prog.curso,
            modulo=instance.modulo,
            metadata={
                'modulo_completado_id': instance.pk,
                'respuesta_correcta': instance.respuesta_correcta,
                'respuesta_dada': instance.respuesta_dada or '',
            },
        )
    except Exception as exc:
        logger.warning('telemetria signal modulo_completado: %s', exc)
