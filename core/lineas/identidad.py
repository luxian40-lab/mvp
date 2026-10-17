"""Identidad en Meta: habeas, cédula confirmada y diploma pendiente.

El curso no vuelve a preguntar esto. Si alguna corta, el cuerpo no corre.
"""
import logging

from core.models import WhatsappLog

logger = logging.getLogger(__name__)

_SI_CONFIRMA_DATOS = {
    'si', 'sí', 'todo bien', 'correcto', 'ok', 'yes', 'confirmo', 'confirmar',
}


def cortar_certificado_meta(post_data) -> bool:
    """Si hay un diploma pendiente, se entrega aquí. El curso no elige el canal."""
    from core.sandbox_canal import inbound_es_meta

    if not inbound_es_meta(post_data):
        return False
    status = (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').strip()
    if status:
        return False
    from core.habeas_respuestas import texto_desde_webhook_twilio
    from core.nati import normalizar_telefono_whatsapp
    from core.utils_telefono import estudiante_por_telefono
    from core.views.certificados_wa import _intentar_responder_envio_certificado

    tel = normalizar_telefono_whatsapp(post_data.get('From', ''))
    est = estudiante_por_telefono(tel)
    if est is None or not (est.contexto_temporal or {}).get('cert_envio_pendiente'):
        return False
    body = (texto_desde_webhook_twilio(post_data, post_data.get('Body', '') or '') or '').strip()
    try:
        return bool(_intentar_responder_envio_certificado(
            est, body, tel, post_data.get('From', '') or est.telefono,
        ))
    except Exception:
        logger.exception('certificado_meta_corte')
        return False


def cortar_habeas_meta(post_data) -> bool:
    """En Meta, sin autorización no se entra al curso. Botones Acepto / No acepto."""
    from core.sandbox_canal import inbound_es_meta

    if not inbound_es_meta(post_data):
        return False
    status = (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').strip()
    if status:
        return False
    from core.habeas_respuestas import aplicar_respuesta_habeas, texto_desde_webhook_twilio
    from core.nati import normalizar_telefono_whatsapp
    from core.utils_telefono import estudiante_por_telefono

    body = (texto_desde_webhook_twilio(post_data, post_data.get('Body', '') or '') or '').strip()
    if not body:
        return False
    tel = normalizar_telefono_whatsapp(post_data.get('From', ''))
    from core.sandbox_menu import _habeas_listo, alinear_ficha_con_sesion_habeas

    est = estudiante_por_telefono(tel)
    pide_avance = body.strip().lower() in ('continuemos', 'continuar')
    if not (pide_avance and est is not None and not est.acepto_terminos) and _habeas_listo(tel):
        alinear_ficha_con_sesion_habeas(tel)
        return False
    if est is None or est.acepto_terminos:
        return False
    if (est.contexto_temporal or {}).get('cert_envio_pendiente'):
        return False
    sid = str(post_data.get('MessageSid') or '').strip()
    if sid and WhatsappLog.objects.filter(mensaje_id=sid, tipo='INCOMING').exists():
        return True
    if sid:
        WhatsappLog.objects.create(
            telefono=est.telefono,
            mensaje=body[:500],
            mensaje_id=sid,
            tipo='INCOMING',
        )
    try:
        resultado = aplicar_respuesta_habeas(est, body)
    except Exception:
        logger.exception('habeas_meta_corte')
        resultado = {'accion': 'reenviar_plantilla', 'texto': None}
    from core.sandbox_canal import enviar_sandbox_habeas
    from core.utils import enviar_whatsapp_twilio

    destino = post_data.get('From', '') or est.telefono
    if resultado.get('accion') == 'reenviar_plantilla':
        enviar_sandbox_habeas(destino)
    else:
        texto = resultado.get('texto') or ''
        if texto:
            enviar_whatsapp_twilio(destino, texto, agente_evento='habeas_meta')
    return True


def menu_tras_confirmar_datos_meta(post_data) -> bool:
    """En Meta, el sí de la cédula abre el menú. El curso empieza al elegirlo."""
    from core.sandbox_canal import inbound_es_meta

    if not inbound_es_meta(post_data):
        return False
    status = (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').strip()
    if status:
        return False
    from core.habeas_respuestas import texto_desde_webhook_twilio
    from core.nati import normalizar_telefono_whatsapp
    from core.utils_telefono import estudiante_por_telefono

    body = (texto_desde_webhook_twilio(post_data, post_data.get('Body', '') or '') or '').strip().lower()
    if body not in _SI_CONFIRMA_DATOS:
        return False
    est = estudiante_por_telefono(normalizar_telefono_whatsapp(post_data.get('From', '')))
    if est is None or est.estado_chat != 'CONFIRMANDO_DATOS':
        return False
    sid = str(post_data.get('MessageSid') or '').strip()
    if sid and WhatsappLog.objects.filter(mensaje_id=sid, tipo='INCOMING').exists():
        return True
    if sid:
        WhatsappLog.objects.create(
            telefono=est.telefono,
            mensaje=body[:500],
            mensaje_id=sid,
            tipo='INCOMING',
        )
    est.estado_chat = 'ACTIVO'
    est.estado_onboarding = 'completado'
    est.save(update_fields=['estado_chat', 'estado_onboarding'])
    from core.sandbox_menu import MODO_MENU, _get_or_create_sesion, _set_modo, enviar_menu_sandbox

    sesion = _get_or_create_sesion(est.telefono)
    sesion.habeas_aceptado = True
    sesion.save(update_fields=['habeas_aceptado', 'actualizado_en'])
    _set_modo(sesion, MODO_MENU)
    enviar_menu_sandbox(est.telefono, post_data.get('From', '') or est.telefono)
    return True
