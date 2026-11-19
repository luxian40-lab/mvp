"""
Signals para Certificados
Auto-generación al completar cursos
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import ProgresoEstudiante
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProgresoEstudiante)
def generar_certificado_al_completar(sender, instance, created, **kwargs):
    """
    Dispara la emisión a propósito (``emitir_diploma_si_cumple``).

    Con ``EKI_DIPLOMA_LEE_REGLAS`` apagado: mismo criterio de siempre
    (completado + fecha_completado). Con el flag prendido, las reglas
    bloquean el diploma al abrir la pregunta abierta final.
    Solo genera — NO envía por WhatsApp (views.py se encarga del envío
    dentro del flujo de multi-mensaje de felicitación).
    """
    if not (instance.completado and instance.fecha_completado):
        return
    try:
        from core.certificados.diploma_reglas import emitir_diploma_si_cumple

        emitir_diploma_si_cumple(instance)
    except Exception as e:
        logger.error(
            'Error en signal de certificado para %s: %s',
            getattr(instance.estudiante, 'nombre', '?'),
            e,
            exc_info=True,
        )
