"""Entrada del bloque ACTIVO: acceso al aula con *aula* y agente de formulario GEI. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from django.conf import settings

from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.models import WhatsappLog

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
        from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp, mensaje_pide_acceso_aula
        if mensaje_pide_acceso_aula(msg_body):
            texto_respuesta = emitir_acceso_desde_whatsapp(estudiante)
            try:
                from twilio.rest import Client as TwilioClient
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                client_tw = TwilioClient(account_sid, auth_token)
                destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                client_tw.messages.create(
                    body=texto_respuesta,
                    from_=str(twilio_number).strip(),
                    to=str(destino).strip(),
                )
                WhatsappLog.objects.create(
                    telefono=telefono_limpio,
                    mensaje=texto_respuesta[:500],
                    tipo='SENT',
                )
            except Exception as e:
                logger.error('❌ Error enviando acceso aula WA: %s', e)
            return CORTAR
    except Exception:
        logger.exception('Acceso aula WhatsApp omitido')

    if estado_chat == 'ACTIVO':
        try:
            from formulario.routing import debe_usar_agente_formulario
            if debe_usar_agente_formulario(estudiante):
                from formulario.agent import manejar_mensaje_formulario
                texto_respuesta = manejar_mensaje_formulario(estudiante, msg_body)
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(
                        body=texto_respuesta,
                        from_=str(twilio_number).strip(),
                        to=str(destino).strip()
                    )
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
                except Exception as e:
                    logger.error(f"❌ Error enviando respuesta formulario GEI: {e}")
                return CORTAR
        except Exception as e:
            logger.error(f"❌ Agente formulario: {e}", exc_info=True)
    return None
