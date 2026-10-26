"""Envío común del cuerpo del webhook: parte el texto con marcas y lo manda por el Client. Movido tal cual (fase D7)."""

import logging

from django.conf import settings

from core.conversacion.contexto import Contexto
from core.conversacion.multimsg import partir_sep
from core.models import WhatsappLog
from core.views.twilio_transporte import _enviar_mensaje_twilio_segmentado
from core.views.twilio_transporte import youtube_hace_solo_enlace_en_texto

logger = logging.getLogger('core.views.webhook_twilio')


def enviar(contexto: Contexto) -> None:
    estudiante = contexto.estudiante
    msg_from = contexto.msg_from
    telefono_limpio = contexto.telefono_limpio
    texto_respuesta = contexto.texto_respuesta
    # 3. Enviar respuesta via Twilio
    print(f"📤 ENVIANDO RESPUESTA: '{texto_respuesta[:80]}...' (len={len(texto_respuesta)})", flush=True)
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
            print(f"🖼️ Media URL detectada: {media_url_to_send}")
    
    try:
        from twilio.rest import Client
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
        twilio_number = str(twilio_number).strip()
        print(f"DEBUG TWILIO FROM (views.py): '{twilio_number}'")
        
        if not account_sid or not auth_token:
            print("❌ Credenciales Twilio faltantes")
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
                print(f"📋 Enviando Content Template standalone: {template_sid}")
                try:
                    from core.whatsapp_service import enviar_template_twilio
                    tel_limpio = msg_from.replace('whatsapp:', '').replace('+', '')
                    enviar_template_twilio(tel_limpio, template_sid)
                    print(f"✅ Template {template_sid} enviado OK")
                except Exception as tmpl_err:
                    print(f"⚠️ Error enviando template standalone: {tmpl_err}")
                return
        
        # Check if response is a multi-message (marked with [MULTI_MSG])
        if texto_respuesta.startswith('[MULTI_MSG]'):
            # Extract and send multiple messages
            partes = partir_sep(texto_respuesta.replace('[MULTI_MSG]', '', 1))
            
            for idx, parte in enumerate(partes):
                if not parte.strip():
                    continue
                
                parte_texto = parte.strip()
                parte_media = None
                
                # [DELAY:N] — pausa intencional para que WhatsApp entregue videos antes del texto siguiente
                import re as re_delay
                delay_match = re_delay.match(r'^\[DELAY:(\d+)\]$', parte_texto)
                if delay_match:
                    delay_secs = int(delay_match.group(1))
                    print(f"⏳ Pausa de {delay_secs}s para entrega de videos...")
                    import time
                    time.sleep(delay_secs)
                    continue
                
                # Detectar si esta parte es un Content Template de Twilio
                if parte_texto.startswith('[SEND_TEMPLATE:'):
                    import re
                    tmpl_match = re.match(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]', parte_texto)
                    if tmpl_match:
                        template_sid = tmpl_match.group(1)
                        print(f"📋 Enviando Content Template {template_sid} como parte {idx+1}")
                        try:
                            from core.whatsapp_service import enviar_template_twilio
                            tel_limpio = msg_from.replace('whatsapp:', '').replace('+', '')
                            enviar_template_twilio(tel_limpio, template_sid)
                            print(f"✅ Template {template_sid} enviado OK")
                        except Exception as tmpl_err:
                            print(f"⚠️ Error enviando template: {tmpl_err}")
                        import time
                        time.sleep(0.5)
                        continue
                
                # Extraer [MEDIA:url] de esta parte
                if '[MEDIA:' in parte_texto:
                    import re
                    media_match_p = re.search(r'\[MEDIA:(.*?)\]', parte_texto)
                    if media_match_p:
                        parte_media = (media_match_p.group(1) or '').strip()
                        parte_texto = parte_texto.replace(media_match_p.group(0), '').strip()
                        logger.info(
                            '📎 [MEDIA] parte %s url=%s',
                            idx + 1,
                            parte_media[:500] + ('…' if len(parte_media) > 500 else ''),
                        )
                        if parte_media and youtube_hace_solo_enlace_en_texto(parte_media):
                            logger.warning(
                                '📎 [MEDIA] URL parece página de YouTube (no MP4 directo); '
                                'Twilio suele necesitar enlace al archivo. parte=%s',
                                idx + 1,
                            )

                mensajes_enviados = _enviar_mensaje_twilio_segmentado(
                    client=client,
                    from_number=twilio_number,
                    to_number=destino_formateado,
                    body=parte_texto,
                    media_url=parte_media,
                )

                for seg_idx, (mensaje, texto_enviado) in enumerate(mensajes_enviados, start=1):
                    print(f"✅ Mensaje {idx+1}.{seg_idx} enviado via Twilio: {mensaje.sid}")
                    from core.twilio_media import mensaje_log_con_media

                    texto_log = mensaje_log_con_media(
                        texto_enviado or parte_texto,
                        parte_media if seg_idx == 1 else None,
                    )
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=texto_log[:1500],
                        mensaje_id=mensaje.sid,
                        tipo='SENT'
                    )
                    print(f"✅ Guardado SENT")
                
                # Small delay between messages to avoid rate limiting
                import time
                time.sleep(0.5)
        else:
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
                    print(f"✅ Mensaje enviado via Twilio: {mensaje.sid}")
                else:
                    print(f"✅ Mensaje segmento {seg_idx}/{len(mensajes_enviados)} enviado via Twilio: {mensaje.sid}")

                from core.twilio_media import mensaje_log_con_media

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
                print(f"✅ Guardado SENT")
        
    except Exception as e:
        print(f"❌ Error enviando respuesta Twilio: {str(e)}")
        import traceback
        traceback.print_exc()
