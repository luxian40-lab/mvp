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
            from core.lineas.diploma_cierre import (
                certificado_emitido_para_curso,
                reto_si_cert_emitido_activo,
            )
            from core.conversacion.claves_contexto import contexto_limpio
            from core.models import ProgresoEstudiante

            _prog_id = _ctx_agente_sync.get('progreso_id')
            _prog = ProgresoEstudiante.objects.filter(id=_prog_id).first() if _prog_id else None
            if (
                reto_si_cert_emitido_activo()
                and _prog is not None
                and certificado_emitido_para_curso(estudiante, _prog.curso) is not None
            ):
                estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal)
                estudiante.estado_onboarding = 'curso_finalizado'
                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                logger.info(
                    'Facilitadora: limbo reto+cert cerrado en sync estudiante_id=%s',
                    estudiante.id,
                )
            else:
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
