"""PQRS y corrección de datos. El curso solo pregunta si ya se atendió."""
import logging

logger = logging.getLogger(__name__)

_CLAVES_CORREGIR = (
    '4', 'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
    'me equivoqué', 'me equivoque', 'editar datos', 'modificar datos', 'modificar',
    'datos incorrectos', 'mis datos', 'actualizar datos',
)


def _enviar_respuesta(msg_from: str, texto: str) -> None:
    from core.lineas.envio import enviar_respuesta_linea

    enviar_respuesta_linea(msg_from, texto, agente='pqrs')


def respuesta_en_puerta(estudiante, msg_body, msg_from, telefono_limpio) -> bool:
    """Ayuda o ticket abierto. True si ya respondió y el curso debe salir."""
    try:
        from core.pqrs_agent import (
            intentar_procesar_seguimiento_pqrs_whatsapp,
            mensaje_activa_soporte,
            mensaje_es_solo_ayuda,
            obtener_ticket_pqrs_abierto,
            pedagogia_tiene_prioridad,
            respuesta_ayuda_con_ticket_abierto,
        )
        from core.security_handler import procesar_solicitud_soporte

        resp = None
        if not pedagogia_tiene_prioridad(estudiante):
            if mensaje_activa_soporte(msg_body):
                ticket = obtener_ticket_pqrs_abierto(estudiante)
                if ticket:
                    if mensaje_es_solo_ayuda(msg_body):
                        resp = respuesta_ayuda_con_ticket_abierto(estudiante, msg_body)
                    else:
                        resp = intentar_procesar_seguimiento_pqrs_whatsapp(estudiante, msg_body)
                else:
                    resp = procesar_solicitud_soporte(estudiante, msg_body, 'curso_ayuda')
            else:
                resp = intentar_procesar_seguimiento_pqrs_whatsapp(estudiante, msg_body)
        if not resp:
            return False
        try:
            _enviar_respuesta(msg_from, resp)
        except Exception as e:
            logger.error('❌ Error enviando PQRS/ayuda en gate curso: %s', e)
        return True
    except Exception:
        logger.exception('PQRS gate curso omitido')
        return False


def seguimiento_en_linea(estudiante, msg_body):
    """Ticket abierto más adelante en el curso. Devuelve (atendido, texto)."""
    try:
        from core.pqrs_agent import (
            intentar_procesar_seguimiento_pqrs_whatsapp,
            pedagogia_tiene_prioridad,
        )

        if pedagogia_tiene_prioridad(estudiante):
            return False, None
        respuesta = intentar_procesar_seguimiento_pqrs_whatsapp(estudiante, msg_body)
        if respuesta:
            logger.info(
                '🆘 PQRS seguimiento — respuesta automática estudiante_id=%s',
                estudiante.id,
            )
            return True, respuesta
    except Exception as e:
        logger.exception('PQRS seguimiento omitido: %s', e)
    return False, None


def corregir_datos_si_pide(estudiante, msg_lower, msg_from, telefono_limpio) -> bool:
    if msg_lower not in _CLAVES_CORREGIR:
        return False
    from core.correccion_datos import iniciar_flujo_correccion

    texto = iniciar_flujo_correccion(estudiante)
    try:
        _enviar_respuesta(msg_from, texto)
    except Exception as e:
        logger.error(f'❌ Error enviando corrección datos: {e}')
    return True
