"""Si quedó el contexto de un agente pedagógico y el estado se desincronizó, vuelve a ponerlo antes del despacho. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from core.conversacion.contexto import Contexto

logger = logging.getLogger('core.views.webhook_twilio')


def resincronizar(contexto: Contexto) -> None:
    estudiante = contexto.estudiante
    # Si el contexto de agente quedó y el estado se desincronizó, no caer
    # en continuar_leccion (saltaría Darío / facilitadora).
    try:
        _ctx_agente_sync = estudiante.contexto_temporal or {}
        _tipo_ctx = _ctx_agente_sync.get('tipo')
        if _tipo_ctx == 'asistente_dario' and estudiante.estado_onboarding != 'esperando_respuesta_asistente':
            _ob_prev = estudiante.estado_onboarding
            estudiante.estado_onboarding = 'esperando_respuesta_asistente'
            estudiante.save(update_fields=['estado_onboarding'])
            logger.warning(
                "🔄 Darío: estado resincronizado %s → esperando_respuesta_asistente "
                "(ctx=asistente_dario) estudiante_id=%s",
                _ob_prev,
                estudiante.id,
            )
        elif _tipo_ctx == 'reto_facilitador' and estudiante.estado_onboarding != 'esperando_respuesta_reto':
            _ob_prev = estudiante.estado_onboarding
            estudiante.estado_onboarding = 'esperando_respuesta_reto'
            estudiante.save(update_fields=['estado_onboarding'])
            logger.warning(
                "🔄 Facilitadora: estado resincronizado %s → esperando_respuesta_reto "
                "(ctx=reto_facilitador) estudiante_id=%s",
                _ob_prev,
                estudiante.id,
            )
        elif _tipo_ctx == 'nota_cierre' and estudiante.estado_onboarding != 'esperando_nota_cierre':
            estudiante.estado_onboarding = 'esperando_nota_cierre'
            estudiante.save(update_fields=['estado_onboarding'])
    except Exception as e:
        logger.warning("⚠️ Sync agente pedagógico omitido: %s", e)
