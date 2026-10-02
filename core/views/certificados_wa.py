import logging

logger = logging.getLogger(__name__)

def _es_respuesta_liberar_certificado(msg: str) -> bool:
    """
    Respuesta del estudiante que abre ventana WhatsApp tras plantilla de certificado.
    Acepta OK, gracias, cualquier texto o número. NO acepta 'listo'/'continuar'
    (comandos de avance de curso).
    """
    import re

    t = (msg or '').strip().lower()
    if not t:
        return False
    limpio = re.sub(r'[^0-9a-záéíóúñ ]', '', t).strip()
    if not limpio:
        return False
    if limpio in ('listo', 'continuar', 'continuar curso', 'siguiente', 'menu', 'menú'):
        return False
    return True

def _es_ack_certificado(msg: str) -> bool:
    """Alias retrocompatible para tests y plantilla inicial (pide OK)."""
    return _es_respuesta_liberar_certificado(msg)

def _intentar_responder_envio_certificado(estudiante, msg_body, telefono_limpio, msg_from):
    """
    Si el estudiante tiene un certificado pendiente (tras plantilla de aviso) y responde
    cualquier mensaje, envía el diploma (la ventana de 24 h quedó abierta por su respuesta).
    """
    ctx = estudiante.contexto_temporal or {}
    pend = ctx.get('cert_envio_pendiente')
    if not pend:
        return False
    if not _es_respuesta_liberar_certificado(msg_body):
        return False

    cert_id = pend.get('certificado_id')
    from ..models_certificados import Certificado
    from ..certificado_service import enviar_certificado_whatsapp
    from ..certificado_presencial_service import (
        cerrar_curso_si_tramo_final,
        limpiar_cert_envio_pendiente,
    )

    cert = (
        Certificado.objects.filter(id=cert_id, emitido=True)
        .select_related('estudiante', 'curso')
        .first()
    )
    if not cert:
        limpiar_cert_envio_pendiente(estudiante)
        return False

    ok = False
    try:
        ok = enviar_certificado_whatsapp(cert)
    except Exception as e:
        logger.error('🎓 Envío certificado tras OK falló est=%s: %s', estudiante.id, e, exc_info=True)

    if ok:
        limpiar_cert_envio_pendiente(estudiante)
        if pend.get('cerrar_avance'):
            cerrar_curso_si_tramo_final(estudiante, cert.curso)
        logger.info(
            '🎓 Certificado %s entregado tras respuesta de est=%s',
            cert.codigo_verificacion,
            estudiante.id,
        )
    else:
        logger.error(
            '🎓 Certificado %s NO pudo enviarse tras respuesta de est=%s (sigue pendiente)',
            cert.codigo_verificacion,
            estudiante.id,
        )
    # La respuesta era para el certificado: no seguir onboarding/curso.
    return True
