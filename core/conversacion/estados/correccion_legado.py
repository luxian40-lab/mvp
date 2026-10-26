"""ESPERANDO_AYUDA_MODIFICAR y ESPERANDO_CORRECCION_DATOS. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from django.conf import settings

from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.models import WhatsappLog

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    telefono_limpio = contexto.telefono_limpio
    # Ya no hay menú de corrección — redirigir al flujo normal
    estudiante.estado_chat = 'ACTIVO'
    estudiante.estado_onboarding = 'completado'
    estudiante.save()

    msg_lower = msg_body.strip().lower()

    # Si dice "continuar", "sí" o similar → enviar al curso
    keywords_continuar = ['continuar', 'sí', 'si', 'ok', 'listo', 'seguir', 'menu', 'menú']
    keywords_ayuda = ['ayuda', 'soporte', 'ticket', 'problema']

    if any(k in msg_lower for k in keywords_ayuda):
        from core.models import SolicitudSoporte
        SolicitudSoporte.objects.create(
            estudiante=estudiante,
            mensaje_original=f"Solicitud de soporte: {msg_body}",
            keyword_usada='soporte_legacy',
            asunto='Soporte desde flujo legacy',
            estado='pendiente'
        )
        texto_respuesta = (
            "🆘 *Solicitud Recibida*\n\n"
            f"Hola {estudiante.nombre}, hemos registrado tu solicitud.\n"
            "Nuestro equipo te contactará pronto.\n\n"
            "👉 Escribe *continuar* para seguir con tu curso"
        )
    else:
        texto_respuesta = (
            f"✅ *¡Listo, {estudiante.nombre}!*\n\n"
            "Continuemos con tu curso."
        )

    try:
        from twilio.rest import Client as TwilioClient
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
        client_tw = TwilioClient(account_sid, auth_token)
        destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
        client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
        WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
    except Exception as e:
        logger.error(f"❌ Error enviando ayuda modificar: {e}")
        import traceback; traceback.print_exc()
    return CORTAR
