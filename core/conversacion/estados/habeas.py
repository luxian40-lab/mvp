"""Estado ESPERANDO_HABEAS_DATA. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios.

Con un certificado pendiente no responde (None) y el cuerpo sigue de largo, como antes.
"""
import logging

from django.conf import settings

from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.models import WhatsappLog

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta | None:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    telefono_limpio = contexto.telefono_limpio
    if not (estudiante.contexto_temporal or {}).get('cert_envio_pendiente'):
        from core.habeas_respuestas import aplicar_respuesta_habeas

        resultado_habeas = aplicar_respuesta_habeas(estudiante, msg_body)
        accion = resultado_habeas.get('accion')
        texto_respuesta = resultado_habeas.get('texto')

        if accion == 'reenviar_plantilla':
            from core.whatsapp_service import enviar_habeas_data
            resultado_tpl = enviar_habeas_data(msg_from, cliente=estudiante.cliente)
            if resultado_tpl.get('success'):
                return CORTAR

            from core.security_handler import _url_politica_datos_cliente
            url_politica = _url_politica_datos_cliente(estudiante=estudiante)
            texto_respuesta = (
                "👋 *¡Bienvenido a eki!*\n\n"
                "🚜 Tu plataforma de soluciones educativas por WhatsApp\n\n"
                "📜 *Protección de Datos Personales*\n"
                "Antes de comenzar, necesitamos tu autorización para usar "
                "tus datos de acuerdo con la Ley 1581 de 2012.\n\n"
                f"🔗 Lee nuestra política completa aquí:\n{url_politica}\n\n"
                "*¿Aceptas el tratamiento de tus datos?*\n\n"
                "👉 Escribe *Acepto* o *No acepto*"
            )

        # Enviar y cortar
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
            logger.error(f"❌ Error enviando habeas data: {e}")
            import traceback; traceback.print_exc()
        return CORTAR  # CORTAR EJECUCIÓN
    return None
