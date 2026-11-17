"""Entrada del bloque ACTIVO: acceso al aula con *aula* y agente de formulario GEI. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from core.conversacion.contexto import CORTAR, Contexto, Respuesta

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta | None:
    estado_chat = contexto.estado_chat
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    msg_lower = contexto.locales['msg_lower']
    telefono_limpio = contexto.telefono_limpio
    logger.info(f"📍 ACTIVO handler: msg='{msg_lower}', onboarding={estudiante.estado_onboarding}")

    # Acceso web Aprende: el alumno escribe *aula* (respuesta inbound = ventana WA abierta)
    try:
        from core.puentes import emitir_acceso_desde_whatsapp, mensaje_pide_acceso_aula
        if mensaje_pide_acceso_aula(msg_body):
            texto_respuesta = emitir_acceso_desde_whatsapp(estudiante)
            try:
                from core.lineas.salida_turno import enviar_respuesta_turno

                enviar_respuesta_turno(msg_from, texto_respuesta, agente='aula_meta')
            except Exception as e:
                logger.error('❌ Error enviando acceso aula WA: %s', e)
            return CORTAR
    except Exception:
        logger.exception('Acceso aula WhatsApp omitido')

    if estado_chat == 'ACTIVO':
        try:
            from core.puentes import debe_usar_agente_formulario
            if debe_usar_agente_formulario(estudiante):
                from core.puentes import manejar_mensaje_formulario
                texto_respuesta = manejar_mensaje_formulario(estudiante, msg_body)
                try:
                    from core.lineas.salida_turno import enviar_respuesta_turno

                    enviar_respuesta_turno(msg_from, texto_respuesta, agente='formulario_gei')
                except Exception as e:
                    logger.error(f"❌ Error enviando respuesta formulario GEI: {e}")
                return CORTAR
        except Exception as e:
            logger.error(f"❌ Agente formulario: {e}", exc_info=True)
    return None
