"""Intercepciones de un Estudiante antes del estado: libera la empleabilidad en pausa, carrusel demo, acuse de campaña única y ubicación. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from django.conf import settings

from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.models import WhatsappLog
from core.views.empleabilidad import _procesar_ubicacion_empleabilidad

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta | None:
    estudiante = contexto.estudiante
    latitud_raw = contexto.locales['latitud_raw']
    longitud_raw = contexto.locales['longitud_raw']
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    msg_sid = contexto.msg_sid
    post_data = contexto.locales['post_data']
    telefono_limpio = contexto.telefono_limpio
    try:
        from core.empleabilidad_pausa import liberar_estado_empleabilidad_si_pausada

        liberar_estado_empleabilidad_si_pausada(estudiante)
    except Exception:
        logger.warning("empleabilidad pausa: no se pudo liberar estado radar", exc_info=True)

    # Carrusel demo: taps Content (desc_*/info_*/in_*) también si ya es Estudiante
    # (p. ej. smoke en 3026480629). No intercepta listo ni menú LMS.
    try:
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

        _btn_demo = (
            post_data.get('ButtonPayload')
            or post_data.get('ButtonText')
            or ''
        )
        if intentar_flujo_prospecto_carrusel(
            telefono=telefono_limpio,
            msg_from=msg_from,
            msg_body=msg_body,
            button_payload=str(_btn_demo),
            solo_botones=True,
        ):
            return CORTAR
    except Exception as _e_demo:
        logger.warning('Carrusel demo (estudiante) omitido: %s', _e_demo)

    # Respuesta campaña única (Sí/No, Asistiré/No asistiré) — antes del flujo del curso
    try:
        from core.campana_respuestas import intentar_registrar_respuesta_campana_unica

        _ack_campana = intentar_registrar_respuesta_campana_unica(
            telefono_limpio=telefono_limpio,
            post_data=post_data,
            msg_body=msg_body,
            estudiante=estudiante,
            mensaje_sid=msg_sid,
        )
        if _ack_campana:
            from twilio.rest import Client as TwilioClient

            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
            client_tw = TwilioClient(account_sid, auth_token)
            destino = (
                f'whatsapp:{msg_from}'
                if not str(msg_from).startswith('whatsapp:')
                else msg_from
            )
            client_tw.messages.create(
                body=_ack_campana,
                from_=str(twilio_number).strip(),
                to=str(destino).strip(),
            )
            WhatsappLog.objects.create(
                telefono=telefono_limpio,
                mensaje=_ack_campana,
                tipo='SENT',
            )
            logger.info(
                '📣 [campana] ack enviado | est=%s tel=%s',
                estudiante.id,
                telefono_limpio[-6:],
            )
            return CORTAR
    except Exception as _e_camp:
        logger.warning('📣 [campana] error registrando respuesta: %s', _e_camp, exc_info=True)

    # Ubicación de WhatsApp (Twilio): Latitude/Longitude
    # PAUSA: radar/empleabilidad no consume el pin (no Subachoque).
    if latitud_raw is not None and longitud_raw is not None:
        from core.empleabilidad_pausa import empleabilidad_en_pausa

        if empleabilidad_en_pausa():
            logger.info(
                "empleabilidad pausada: ubicación ignorada | estudiante_id=%s",
                estudiante.id,
            )
            if not (msg_body or '').strip():
                return CORTAR
        else:
            try:
                latitud = float(latitud_raw)
                longitud = float(longitud_raw)
                texto_geo = _procesar_ubicacion_empleabilidad(estudiante, latitud, longitud)
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not str(msg_from).startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=texto_geo, from_=str(twilio_number).strip(), to=str(destino).strip())
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_geo, tipo='SENT')
                except Exception as e:
                    logger.error(f"❌ Error enviando respuesta de ubicación: {e}")
                return CORTAR
            except ValueError:
                logger.warning(f"⚠️ Coordenadas inválidas recibidas: lat={latitud_raw}, lon={longitud_raw}")
    return None
