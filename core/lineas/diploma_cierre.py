"""Cierre de limbo reto+cert (C3). Flag apagado = comportamiento actual."""
from __future__ import annotations

import logging

from django.conf import settings

from core.conversacion.claves_contexto import contexto_limpio

logger = logging.getLogger(__name__)


def reto_si_cert_emitido_activo() -> bool:
    """Default OFF: no cambia prod hasta prenderlo a propósito."""
    return bool(getattr(settings, 'EKI_RETO_SI_CERT_EMITIDO', False))


def certificado_emitido_para_curso(estudiante, curso):
    """Último certificado emitido de ese estudiante×curso, o None."""
    if estudiante is None or curso is None:
        return None
    from core.certificados.models_certificados import Certificado

    return (
        Certificado.objects.filter(estudiante=estudiante, curso=curso, emitido=True)
        .order_by('-id')
        .first()
    )


def cerrar_limbo_reto_si_cert(estudiante, progreso) -> str | None:
    """Si el flag está ON y ya hay cert emitido, limpia reto y devuelve CTA.

    None = seguir el flujo normal del reto.
    """
    if not reto_si_cert_emitido_activo():
        return None
    if estudiante is None or progreso is None:
        return None
    cert = certificado_emitido_para_curso(estudiante, progreso.curso)
    if cert is None:
        return None

    estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal)
    estudiante.estado_onboarding = 'curso_finalizado'
    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
    logger.info(
        'diploma_cierre_reto_omitido estudiante_id=%s curso_id=%s cert_id=%s enviado=%s',
        estudiante.id,
        getattr(progreso.curso, 'id', None),
        cert.id,
        cert.enviado_whatsapp,
    )
    if cert.enviado_whatsapp:
        return (
            '🎓 Ya tiene el diploma de este curso.\n\n'
            'Si no lo ve en el chat, escriba *ayuda*.'
        )
    return (
        '🎓 Su diploma de este curso ya está listo.\n\n'
        'Si no le llega en unos minutos, escriba *ayuda* para reenviarlo.'
    )
