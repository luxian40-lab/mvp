"""Envío común del cuerpo del webhook: parte el texto con marcas y lo manda por el Client. Movido tal cual (fase D7)."""

import logging

from django.conf import settings

from core.conversacion.contexto import Contexto
from core.models import WhatsappLog
from core.views.twilio_transporte import _enviar_mensaje_twilio_segmentado

logger = logging.getLogger('core.views.webhook_twilio')


def enviar(contexto: Contexto) -> None:
    estudiante = contexto.estudiante
    msg_from = contexto.msg_from
    telefono_limpio = contexto.telefono_limpio
    texto_respuesta = contexto.texto_respuesta
    # 3. Enviar respuesta via Twilio
    logger.info(f"📤 ENVIANDO RESPUESTA: '{texto_respuesta[:80]}...' (len={len(texto_respuesta)})")
    if (
        'Pregunta abierta final de la Facilitadora' in texto_respuesta
        or 'Siguiente pregunta abierta final' in texto_respuesta
    ):
        logger.info(
            "📨 Respuesta de pregunta abierta final enviada | estudiante_id=%s | preview=%s",
            estudiante.id,
            texto_respuesta[:500],
        )
    # Detectar si hay media_url en la respuesta (marcado con [MEDIA:url])
    # NOTA: Solo extraer [MEDIA:] para mensajes simples (no MULTI_MSG)
    # MULTI_MSG maneja su propio [MEDIA:] por cada parte del split
    media_url_to_send = None
    if not texto_respuesta.startswith('[MULTI_MSG]') and '[MEDIA:' in texto_respuesta:
        import re
        media_match = re.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
        if media_match:
            media_url_to_send = media_match.group(1)
            texto_respuesta = texto_respuesta.replace(media_match.group(0), '').strip()
            logger.info(f"🖼️ Media URL detectada: {media_url_to_send}")
    
    try:
        from core.views.twilio_transporte import turno_sale_por_meta

        if turno_sale_por_meta():
            from core.lineas.salida_turno import entregar_en_turno

            if texto_respuesta.startswith('[MULTI_MSG]'):
                entregar_en_turno(
                    msg_from, telefono_limpio, texto_respuesta, agente='curso',
                )
            else:
                from core.lineas.salida_turno import enviar_respuesta_turno

                enviar_respuesta_turno(
                    msg_from,
                    texto_respuesta,
                    media_url=media_url_to_send,
                    agente='curso',
                )
            return

        from twilio.rest import Client
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
        twilio_number = str(twilio_number).strip()
        logger.info(f"DEBUG TWILIO FROM (views.py): '{twilio_number}'")
        
        if not account_sid or not auth_token:
            logger.error("❌ Credenciales Twilio faltantes")
            return
        
        client = Client(account_sid, auth_token)

        # Usar el teléfono original (con +) para enviar por Twilio
        destino_formateado = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
        destino_formateado = str(destino_formateado).strip()
        
        # Check if response is a standalone template send
        if texto_respuesta.strip().startswith('[SEND_TEMPLATE:'):
            import re
            tmpl_match = re.match(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]', texto_respuesta.strip())
            if tmpl_match:
                template_sid = tmpl_match.group(1)
                logger.info(f"📋 Enviando Content Template standalone: {template_sid}")
                try:
                    from core.canal.whatsapp_service import enviar_template_twilio
                    tel_limpio = msg_from.replace('whatsapp:', '').replace('+', '')
                    enviar_template_twilio(tel_limpio, template_sid)
                    logger.info(f"✅ Template {template_sid} enviado OK")
                except Exception as tmpl_err:
                    logger.exception(f"⚠️ Error enviando template standalone: {tmpl_err}")
                return
        
        # Check if response is a multi-message (marked with [MULTI_MSG])
        if texto_respuesta.startswith('[MULTI_MSG]'):
            _enviar_partes_multimsg(
                client, twilio_number, destino_formateado, msg_from, telefono_limpio, texto_respuesta,
            )
        else:
            _enviar_mensaje_unico(
                client, twilio_number, destino_formateado, telefono_limpio,
                texto_respuesta, media_url_to_send,
            )
        
    except Exception as e:
        logger.exception('❌ Error enviando respuesta Twilio: %s', e)


def _enviar_partes_multimsg(client, twilio_number, destino_formateado, msg_from, telefono_limpio, texto_respuesta):
    from core.lineas.entrega import enviar_marcado

    enviar_marcado(msg_from, telefono_limpio, texto_respuesta, registro='segmentos')


def _enviar_mensaje_unico(client, twilio_number, destino_formateado, telefono_limpio, texto_respuesta, media_url_to_send):
    # Single message (original behavior)
    mensajes_enviados = _enviar_mensaje_twilio_segmentado(
        client=client,
        from_number=twilio_number,
        to_number=destino_formateado,
        body=texto_respuesta,
        media_url=media_url_to_send,
    )

    for seg_idx, (mensaje, texto_enviado) in enumerate(mensajes_enviados, start=1):
        if len(mensajes_enviados) == 1:
            logger.info(f"✅ Mensaje enviado via Twilio: {mensaje.sid}")
        else:
            logger.info(f"✅ Mensaje segmento {seg_idx}/{len(mensajes_enviados)} enviado via Twilio: {mensaje.sid}")

        from core.canal.twilio_media import mensaje_log_con_media

        texto_log = mensaje_log_con_media(
            texto_enviado or texto_respuesta,
            media_url_to_send if seg_idx == 1 else None,
        )
        WhatsappLog.objects.create(
            telefono=telefono_limpio,
            mensaje=texto_log[:1500],
            mensaje_id=mensaje.sid,
            tipo='SENT'
        )
        logger.info(f"✅ Guardado SENT")
