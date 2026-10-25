import logging

from django.conf import settings
from django.utils import timezone

from ..avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from ..avance_whatsapp import TEXTO_NO_ENTENDI as _TEXTO_NO_ENTENDI
from ..intent_detector import mensaje_indica_listo as _mensaje_indica_listo
from ..models import Estudiante, ModuloCompletado, WhatsappLog
from ..response_templates import parte_mensaje_con_media

logger = logging.getLogger(__name__)

from .audio import _transcribir_audio_twilio
from .certificados_wa import _intentar_responder_envio_certificado
from .empleabilidad import (
    _procesar_ubicacion_empleabilidad,
    _radar_msg_si_aplica,
)
from .twilio_transporte import (
    _enviar_mensaje_twilio_segmentado,
    _es_status_callback_twilio,
    _registrar_estado_twilio_callback,
    youtube_hace_solo_enlace_en_texto,
)
from core.lineas.identidad import (
    cortar_certificado_meta as _cortar_certificado_meta,
    cortar_habeas_meta as _cortar_habeas_meta,
    menu_tras_confirmar_datos_meta as _menu_tras_confirmar_datos_meta,
)
from core.conversacion.contexto import Contexto
from .ventana_drip import _pregunta_abierta_final_pendiente

def _intentar_aula_twilio_fuera_de_activo(post_data) -> bool:
    """*aula* en Twilio aunque el chat no esté ACTIVO. No entra al cuerpo."""
    from core.sandbox_canal import inbound_es_meta

    if inbound_es_meta(post_data):
        return False
    status = (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').strip()
    if status:
        return False
    from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp, mensaje_pide_acceso_aula
    from core.habeas_respuestas import texto_desde_webhook_twilio
    from core.nati import normalizar_telefono_whatsapp
    from core.utils_telefono import estudiante_por_telefono

    body = texto_desde_webhook_twilio(post_data, post_data.get('Body', '') or '')
    if not mensaje_pide_acceso_aula(body):
        return False
    est = estudiante_por_telefono(normalizar_telefono_whatsapp(post_data.get('From', '')))
    if est is None:
        return False
    if (est.estado_chat or '') == 'ACTIVO' or (est.estado_onboarding or '') == 'completado':
        return False
    try:
        texto = emitir_acceso_desde_whatsapp(est)
    except Exception:
        logger.exception('aula_twilio_emit_fail')
        return False
    from core.utils import enviar_whatsapp_twilio

    enviar_whatsapp_twilio(post_data.get('From', ''), texto, agente_evento='aula_twilio')
    return True


def _turno_desde_post(post_data, canal):
    """Turno del mensaje: teléfono, línea, perfil y canal. Sin consultas a la base."""
    from core.conversacion.turno import Turno
    from core.lineas.meta import nombre_de_linea
    from core.lineas.variante import perfil_de
    from core.wa_canal import CANAL_TWILIO

    telefono = str(post_data.get('From', '') or '').replace('whatsapp:', '')
    if canal == CANAL_TWILIO:
        phone_id, linea = '', 'twilio'
    else:
        phone_id = str(post_data.get('_eki_phone_number_id') or '').strip()
        linea = nombre_de_linea(phone_id)
    return Turno(telefono=telefono, phone_id=phone_id, linea=linea, perfil=perfil_de(phone_id), canal=canal)


def _entrada_para_medir(post_data, turno):
    """Estado y línea al llegar el mensaje. None en callbacks de estado o con la medición apagada."""
    from django.db import DatabaseError

    from core.conversacion.medicion import EntradaTurno
    from core.utils_telefono import estudiante_por_telefono

    if not getattr(settings, 'EKI_MEDIR_TURNO', True):
        return None
    if (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').strip():
        return None
    try:
        est = estudiante_por_telefono(turno.telefono)
        estado = 'sin_estudiante' if est is None else (getattr(est, 'estado_onboarding', '') or '')
        chat = '' if est is None else (getattr(est, 'estado_chat', '') or '')
    except DatabaseError:
        logger.warning('motor_turno_estado_no_leido', exc_info=True)
        estado, chat = '', ''
    return EntradaTurno(estado=estado, chat=chat, linea=turno.linea, canal=turno.canal)


def _procesar_twilio_webhook(post_data):
    """Procesa webhooks de Twilio WhatsApp (también inbound canónico sandbox Meta)."""
    from core.conversacion.medicion import medir_turno
    from core.conversacion.turno import turno_activo
    from core.sandbox_canal import activar_sandbox_meta_si_inbound, inbound_es_meta
    from core.wa_canal import CANAL_META, CANAL_TWILIO, canal_webhook

    canal = CANAL_META if inbound_es_meta(post_data) else CANAL_TWILIO
    turno = _turno_desde_post(post_data, canal)
    entrada = _entrada_para_medir(post_data, turno)
    with (
        turno_activo(turno),
        canal_webhook(canal),
        activar_sandbox_meta_si_inbound(post_data),
        medir_turno(entrada),
    ):
        if canal == CANAL_TWILIO and _es_status_callback_twilio(post_data):
            _registrar_estado_twilio_callback(post_data)
            return None
        if canal == CANAL_META and _cortar_certificado_meta(post_data):
            return None
        if canal == CANAL_META and _cortar_habeas_meta(post_data):
            return None
        if canal == CANAL_META and _menu_tras_confirmar_datos_meta(post_data):
            return None
        if canal == CANAL_TWILIO and _intentar_aula_twilio_fuera_de_activo(post_data):
            return None
        if canal == CANAL_TWILIO:
            from .twilio_transporte import interceptar_envio_boton_twilio

            with interceptar_envio_boton_twilio():
                return _procesar_twilio_webhook_cuerpo(post_data)
        return _procesar_twilio_webhook_cuerpo(post_data)

def _procesar_twilio_webhook_cuerpo(post_data):
    """Procesa webhooks de Twilio WhatsApp"""
    # ============================================================
    # FILTRO 1: Ignorar status callbacks de Twilio (queued/sent/delivered)
    # Twilio envía callbacks de estado al mismo webhook, NO son mensajes
    # ============================================================
    message_status = post_data.get('MessageStatus', post_data.get('SmsStatus', ''))
    if message_status and message_status.lower() in ['queued', 'sending', 'sent', 'delivered', 'undelivered', 'failed', 'read']:
        _registrar_estado_twilio_callback(post_data)
        logger.debug(f"Status callback procesado: {message_status}")
        return
    
    # FILTRO 2: Ignorar si no hay Body ni Media ni botón (status callback sin MessageStatus)
    raw_body = post_data.get('Body', '')
    raw_media = int(post_data.get('NumMedia', 0))
    raw_btn = (
        post_data.get('ButtonPayload')
        or post_data.get('ButtonText')
        or post_data.get('ListId')
        or post_data.get('ListTitle')
        or ''
    )
    if not raw_body and raw_media == 0 and not raw_btn and not post_data.get('From', ''):
        logger.debug("Webhook vacio ignorado (sin Body ni Media)")
        return
    
    from ..response_templates import (
        LECCION_EN_CURSO,
        activar_retencion_turno,
        cerrar_retencion_turno,
        soltar_turno_entrega_actual,
    )

    _turno_token = activar_retencion_turno()
    try:
        logger.info("🔵 TWILIO: Procesando...")
        
        # Twilio envía datos en formato form-data
        msg_body = post_data.get('Body', '')
        # Quick reply / botones Content: a veces Body vacío y solo ButtonPayload/Text
        from ..habeas_respuestas import texto_desde_webhook_twilio

        msg_body = texto_desde_webhook_twilio(post_data, msg_body)
        msg_from = post_data.get('From', '')  # whatsapp:+573001234567
        msg_to = post_data.get('To', '')      # whatsapp:+14155238886
        msg_sid = post_data.get('MessageSid', f'twilio_{timezone.now().timestamp()}')

        # Evita procesar dos veces el mismo mensaje entrante si Twilio reintenta.
        if msg_sid and WhatsappLog.objects.filter(mensaje_id=msg_sid, tipo='INCOMING').exists():
            logger.info("♻️ Twilio inbound duplicado ignorado | sid=%s", msg_sid)
            return

        from core.eventos_ia import set_trace_id
        set_trace_id()
        
        logger.info(f"📱 Body: {msg_body} | From: {msg_from} | To: {msg_to}")

        # 🎤 DETECTAR AUDIO: Twilio envía audios como MediaUrl
        num_media = int(post_data.get('NumMedia', 0))
        media_type = post_data.get('MediaContentType0', '')
        media_url = post_data.get('MediaUrl0', '')
        latitud_raw = post_data.get('Latitude')
        longitud_raw = post_data.get('Longitude')
        print(f"🎤 DEBUG AUDIO: NumMedia={num_media}, MediaType='{media_type}', MediaUrl={bool(media_url)}, Body='{msg_body[:30] if msg_body else ''}'", flush=True)

        from core.twilio_inbound_media import es_audio_inbound_twilio

        es_audio = es_audio_inbound_twilio(num_media, media_type, media_url)
        # Imagen: puede ser evidencia de un reto de campo (se resuelve en esa rama).
        from core.reto_evidencia import es_imagen_soportada

        evidencia_imagen_url = media_url if (num_media > 0 and es_imagen_soportada(media_type)) else ''
        evidencia_imagen_type = media_type if evidencia_imagen_url else ''
        if num_media > 0:
            if es_audio:
                print(f"🎤 Audio detectado: {media_url} (type={media_type})")
                try:
                    transcripcion = _transcribir_audio_twilio(media_url, media_type=media_type)
                    print(f"✅ Audio transcrito: '{transcripcion}'")
                    if transcripcion:
                        msg_body = transcripcion
                    elif not msg_body:
                        msg_body = "[AUDIO_NO_TRANSCRITO]"
                except Exception as e:
                    print(f"❌ Error transcribiendo audio: {e}")
                    import traceback; traceback.print_exc()
                    if not msg_body:
                        msg_body = "[AUDIO_NO_TRANSCRITO]"
            elif not msg_body:
                # Imagen u otro media sin texto — ignorar media, no es audio
                print(f"📎 Media no-audio recibido: type={media_type}")
                msg_body = "listo"
        
        # Limpiar número (quitar whatsapp: y normalizar igual que el modelo)
        if msg_from.startswith('whatsapp:'):
            msg_from = msg_from.replace('whatsapp:', '')
        
        # Normalizar teléfono igual que el modelo (sin +, sin espacios, sin guiones)
        import re
        telefono_limpio = re.sub(r'\D', '', msg_from)  # Solo dígitos
        if len(telefono_limpio) == 10:
            telefono_limpio = f"57{telefono_limpio}"
        
        logger.info(f"📱 De: {msg_from} → Limpio: {telefono_limpio} | Mensaje: {msg_body}")
        logger.info(f"TWILIO MSG: From={telefono_limpio} Body='{msg_body[:50]}'")
        
        # 1. Guardar mensaje entrante con teléfono limpio
        WhatsappLog.objects.create(
            telefono=telefono_limpio,
            mensaje=msg_body,
            mensaje_id=msg_sid,
            tipo='INCOMING',
            es_audio=es_audio,
        )
        logger.info(f"✅ Guardado INCOMING")

        try:
            from core.eventos_ia import emit_webhook_recibido
            from core.ai_capabilities import resolver_ai_capability

            if resolver_ai_capability('eventos_ia'):
                emit_webhook_recibido(
                    mensaje=msg_body,
                    telefono=telefono_limpio,
                    canal='whatsapp_edu',
                )
        except Exception:
            pass
        
        # ============================================================
        # FASE 0: INTERCEPCIÓN DE NO REGISTRADOS (Lead Generation)
        # Si el número no existe en Estudiante, activar "Modo Ventas"
        # ============================================================
        try:
            estudiante = Estudiante.objects.select_related('cliente').get(telefono=telefono_limpio)
            logger.info(f"Estudiante encontrado: {estudiante.nombre} (ID: {estudiante.id})")

            try:
                from core.empleabilidad_pausa import liberar_estado_empleabilidad_si_pausada

                liberar_estado_empleabilidad_si_pausada(estudiante)
            except Exception:
                logger.warning("empleabilidad pausa: no se pudo liberar estado radar", exc_info=True)

            # Carrusel demo: taps Content (desc_*/info_*/in_*) también si ya es Estudiante
            # (p. ej. smoke en 3026480629). No intercepta listo ni menú LMS.
            try:
                from ..catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

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
                    return
            except Exception as _e_demo:
                logger.warning('Carrusel demo (estudiante) omitido: %s', _e_demo)

            # Respuesta campaña única (Sí/No, Asistiré/No asistiré) — antes del flujo del curso
            try:
                from ..campana_respuestas import intentar_registrar_respuesta_campana_unica

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
                    return
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
                        return
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
                        return
                    except ValueError:
                        logger.warning(f"⚠️ Coordenadas inválidas recibidas: lat={latitud_raw}, lon={longitud_raw}")

            # Certificado presencial pendiente: ANTES de Habeas/onboarding.
            # Si el estudiante respondió OK a la plantilla inicial, "ok" no debe
            # interpretarse como aceptación de política de datos.
            try:
                if _intentar_responder_envio_certificado(
                    estudiante, msg_body, telefono_limpio, msg_from,
                ):
                    return
            except Exception as e:
                logger.exception('Intercept certificado pendiente omitido: %s', e)

        except Estudiante.DoesNotExist:
            # Verificar si ya es un prospecto B2B existente
            from ..models import ProspectoB2B
            from ..catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

            prospecto = None
            try:
                prospecto = ProspectoB2B.objects.get(telefono=telefono_limpio)
            except ProspectoB2B.DoesNotExist:
                pass

            btn_payload = (
                post_data.get('ButtonPayload')
                or post_data.get('ButtonText')
                or ''
            )
            if intentar_flujo_prospecto_carrusel(
                telefono=telefono_limpio,
                msg_from=msg_from,
                msg_body=msg_body,
                button_payload=str(btn_payload),
            ):
                if not prospecto:
                    ProspectoB2B.objects.get_or_create(
                        telefono=telefono_limpio,
                        defaults={
                            'mensaje_original': (msg_body or btn_payload or 'carrusel_demo')[:500],
                            'origen': 'whatsapp_bot',
                        },
                    )
                return

            msg_lower = msg_body.strip().lower()
            
            if prospecto:
                # Prospecto existente - procesar su respuesta
                if prospecto.esperando_email:
                    # Validar si parece un email
                    import re as re_email
                    email_match = re_email.search(r'[\w.+-]+@[\w-]+\.[\w.]+', msg_body)
                    if email_match:
                        prospecto.email = email_match.group(0)
                        prospecto.esperando_email = False
                        prospecto.fecha_ultimo_contacto = timezone.now()
                        prospecto.save()
                        
                        # Notificar al equipo de ventas por email
                        try:
                            from django.core.mail import send_mail
                            send_mail(
                                subject=f"🏢 Nuevo Lead B2B - {prospecto.empresa or prospecto.telefono}",
                                message=f"Nuevo prospecto capturado por el bot:\n\nTeléfono: {prospecto.telefono}\nEmpresa: {prospecto.empresa}\nEmail: {prospecto.email}\nMensaje: {prospecto.mensaje_original}",
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[getattr(settings, 'EMAIL_SOPORTE', 'comunidad.educativa@eki.com.co')],
                                fail_silently=True
                            )
                        except Exception:
                            pass
                        
                        texto_respuesta = (
                            "✅ *¡Perfecto!*\n\n"
                            f"Hemos registrado tu correo: *{prospecto.email}*\n\n"
                            "Nuestro equipo de ventas te contactará muy pronto "
                            "para contarte todo sobre las capacitaciones de eki. 🚜\n\n"
                            "¡Gracias por tu interés! 🌱"
                        )
                    else:
                        texto_respuesta = "📧 Por favor envía un correo electrónico válido (ej: nombre@empresa.com)"
                elif msg_lower in ['1', 'empresa', 'eki para mi empresa']:
                    prospecto.esperando_email = True
                    prospecto.fecha_ultimo_contacto = timezone.now()
                    prospecto.save()
                    texto_respuesta = (
                        "🏢 *¡Excelente!*\n\n"
                        "Nos encantaría ayudar a capacitar a tu equipo.\n\n"
                        "📧 Por favor envíanos tu *correo electrónico* "
                        "y un asesor de ventas te contactará:\n\n"
                        "👉 Ejemplo: juan@miempresa.com"
                    )
                elif msg_lower in ['3', 'ayuda', 'soy estudiante', 'estudiante']:
                    texto_respuesta = (
                        "🙋‍♂️ *¡Entendido!*\n\n"
                        "Si eres estudiante y cambiaste de número, "
                        "por favor contacta a tu coordinador o escribe a:\n\n"
                        "📧 comunidad.educativa@eki.com.co\n\n"
                        "Incluye tu nombre completo y número de cédula para que podamos ayudarte."
                    )
                elif msg_lower in ['2', 'web', 'sitio', 'visitar sitio web', 'www.eki.com.co']:
                    texto_respuesta = (
                        "🌐 Conoce más en *www.eki.com.co*\n\n"
                        "Si quiere ver programas de ejemplo, escriba *4*.\n"
                        "Si es empresa, escriba *1*."
                    )
                elif msg_lower in ['4', 'programas', 'programa', 'catalogo', 'catálogo']:
                    if intentar_flujo_prospecto_carrusel(
                        telefono=telefono_limpio,
                        msg_from=msg_from,
                        msg_body='programas',
                        button_payload='',
                    ):
                        return
                    from ..whatsapp_service import enviar_mensaje_ventas
                    enviar_mensaje_ventas(msg_from)
                    return
                else:
                    from ..whatsapp_service import enviar_mensaje_ventas
                    enviar_mensaje_ventas(msg_from)
                    return
                
                # Enviar respuesta al prospecto
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                except Exception as e:
                    print(f"❌ Error enviando a prospecto: {e}")
                return
            
            else:
                # Nuevo prospecto - crear y enviar mensaje de ventas (o carrusel si keyword)
                ProspectoB2B.objects.create(
                    telefono=telefono_limpio,
                    mensaje_original=msg_body,
                    origen='whatsapp_bot'
                )
                if intentar_flujo_prospecto_carrusel(
                    telefono=telefono_limpio,
                    msg_from=msg_from,
                    msg_body=msg_body,
                    button_payload=str(btn_payload),
                ):
                    logger.info(f"🏢 Nuevo prospecto + carrusel demo: {telefono_limpio}")
                    return
                from ..whatsapp_service import enviar_mensaje_ventas
                enviar_mensaje_ventas(msg_from)
                logger.info(f"🏢 Nuevo prospecto B2B capturado: {telefono_limpio}")
                return
        
        # ============================================================
        # MÁQUINA DE ESTADOS B2B (Onboarding con Botones Twilio)
        # ============================================================
        estado_chat = getattr(estudiante, 'estado_chat', None)
        logger.info(f"📍 Estado estudiante {estudiante.nombre}: estado_chat={estado_chat}, onboarding={estudiante.estado_onboarding}, acepto={estudiante.acepto_terminos}")
        
        # Migrar estudiantes legacy al nuevo sistema
        if not estado_chat or estado_chat in ('', None):
            if estudiante.acepto_terminos and estudiante.estado_onboarding == 'completado':
                estudiante.estado_chat = 'ACTIVO'
            elif estudiante.acepto_terminos:
                estudiante.estado_chat = 'ESPERANDO_CEDULA'
            else:
                estudiante.estado_chat = 'ESPERANDO_HABEAS_DATA'
            estudiante.save()
            estado_chat = estudiante.estado_chat
            logger.info(f"📍 Legacy migration: estado_chat → {estado_chat}")
        
        # Auto-corregir: admin creó estudiante con acepto_terminos=True pero estado_chat quedó en ESPERANDO_HABEAS_DATA
        if estado_chat == 'ESPERANDO_HABEAS_DATA' and estudiante.acepto_terminos:
            if estudiante.estado_onboarding == 'completado':
                estudiante.estado_chat = 'ACTIVO'
            else:
                estudiante.estado_chat = 'ESPERANDO_CEDULA'
            estudiante.save()
            estado_chat = estudiante.estado_chat
            logger.info(f"📍 Auto-corrección admin: estado_chat → {estado_chat}")

        # ============================================================
        # PRIORIDAD GLOBAL: menu + corregir datos (post-habeas)
        # Debe funcionar en cualquier estado del bot una vez el usuario
        # aceptó términos.
        # ============================================================
        from ..correccion_datos import (
            construir_menu_principal_texto,
            es_keyword_correccion,
            es_keyword_menu,
            estudiante_en_flujo_correccion,
            iniciar_flujo_correccion,
            normalizar_texto,
            procesar_flujo_correccion,
        )
        texto_norm = normalizar_texto(msg_body)

        # Si el usuario quedó en estado legacy por PQRS/corrección, normalizar
        # chat a ACTIVO para que "listo" retome el curso. NUNCA pisar estados
        # de agentes (Darío / facilitadora / tutor): eso saltaba la evaluación.
        _ESTADOS_AGENTE_NO_FORZAR = frozenset({
            'completado',
            'esperando_respuesta_asistente',
            'esperando_respuesta_reto',
            'esperando_respuesta_tutor_ia',
            'esperando_respuesta_progreso',
            'esperando_respuesta_modulo',
            'esperando_respuesta_pregunta_abierta_final',
            'esperando_seleccion_curso',
            'curso_finalizado',
        })
        from core.empleabilidad_pausa import empleabilidad_en_pausa as _emp_pausa_estados
        if not _emp_pausa_estados():
            _ESTADOS_AGENTE_NO_FORZAR = _ESTADOS_AGENTE_NO_FORZAR | {
                'esperando_codigo_empleabilidad',
            }
        if texto_norm in {"listo", "continuar"}:
            from ..models import ProgresoEstudiante
            if ProgresoEstudiante.objects.filter(
                estudiante=estudiante, completado=False, curso__activo=True
            ).exists():
                cambios = []
                if estudiante.estado_chat != "ACTIVO":
                    estudiante.estado_chat = "ACTIVO"
                    cambios.append("estado_chat")
                if estudiante.estado_onboarding not in _ESTADOS_AGENTE_NO_FORZAR:
                    estudiante.estado_onboarding = "completado"
                    cambios.append("estado_onboarding")
                if cambios:
                    estudiante.save(update_fields=cambios)

        if estudiante.acepto_terminos:
            from ..utils import enviar_whatsapp_twilio
            if estudiante_en_flujo_correccion(estudiante):
                texto_respuesta = procesar_flujo_correccion(estudiante, msg_body)
                enviar_whatsapp_twilio(msg_from, texto_respuesta)
                return

            if es_keyword_correccion(texto_norm):
                texto_respuesta = iniciar_flujo_correccion(estudiante)
                enviar_whatsapp_twilio(msg_from, texto_respuesta)
                return

            # GEI / formulario activo: tiene prioridad sobre *hola*/*menú*/retomar B2B.
            # Si no, "hola" (keyword retomar) saltaba la ficha y dejaba la sesión pegada.
            try:
                from formulario.routing import debe_usar_agente_formulario
                if estado_chat == 'ACTIVO' and debe_usar_agente_formulario(estudiante):
                    from formulario.agent import manejar_mensaje_formulario
                    texto_respuesta = manejar_mensaje_formulario(estudiante, msg_body)
                    enviar_whatsapp_twilio(msg_from, texto_respuesta)
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=(texto_respuesta or '')[:500],
                        tipo='SENT',
                    )
                    return
            except Exception:
                logger.exception('Agente formulario GEI (prioridad temprana) omitido')

            from ..flujo_whatsapp_b2b import (
                es_estudiante_b2b,
                es_keyword_retomar,
                salir_seleccion_curso_legacy,
            )
            from ..response_templates import get_response_for_intent

            if es_estudiante_b2b(estudiante) and es_keyword_retomar(texto_norm):
                salir_seleccion_curso_legacy(estudiante)
                texto_respuesta = get_response_for_intent(
                    'continuar_leccion',
                    estudiante.nombre,
                    estudiante_id=estudiante.id,
                    mensaje_original=msg_body,
                )
                enviar_whatsapp_twilio(msg_from, texto_respuesta)
                return

            if es_keyword_menu(texto_norm):
                texto_respuesta = construir_menu_principal_texto(estudiante)
                enviar_whatsapp_twilio(msg_from, texto_respuesta)
                return
        
        # --- BARRERA 1: HABEAS DATA ---
        if estado_chat == 'ESPERANDO_HABEAS_DATA':
            if not (estudiante.contexto_temporal or {}).get('cert_envio_pendiente'):
                from ..habeas_respuestas import aplicar_respuesta_habeas

                resultado_habeas = aplicar_respuesta_habeas(estudiante, msg_body)
                accion = resultado_habeas.get('accion')
                texto_respuesta = resultado_habeas.get('texto')

                if accion == 'reenviar_plantilla':
                    from ..whatsapp_service import enviar_habeas_data
                    resultado_tpl = enviar_habeas_data(msg_from, cliente=estudiante.cliente)
                    if resultado_tpl.get('success'):
                        return

                    from ..security_handler import _url_politica_datos_cliente
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
                return  # CORTAR EJECUCIÓN
        
        # --- BARRERA 2: VALIDACIÓN 2FA (Cédula) ---
        from core.conversacion.estados.despacho import BARRERAS

        _barrera = BARRERAS.get(estado_chat)
        if _barrera is not None:
            _barrera(Contexto(estudiante, msg_body, msg_from, telefono_limpio))
            return  # CORTAR EJECUCIÓN
        
        # --- BARRERA 3: CONFIRMACIÓN DE DATOS ---
        if estado_chat == 'CONFIRMANDO_DATOS':
            msg_lower = msg_body.strip().lower()
            keywords_si = ['sí', 'si', 'todo bien', 'correcto', 'bien', 'ok', 'yes', 'confirmo', 'confirmar']
            keywords_modificar = ['modificar', 'no', 'error', 'mal', 'incorrecto', 'hay un error', 'cambiar']
            
            if any(k in msg_lower for k in keywords_si):
                estudiante.estado_chat = 'ACTIVO'
                estudiante.estado_onboarding = 'completado'  # Legacy compat
                estudiante.save()
                
                # Enviar curso directamente (sin menú)
                org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                try:
                    from ..models import ProgresoEstudiante
                    from ..response_templates import obtener_video_url
                    from ..selector_curso import resolver_curso_post_confirmacion

                    curso = resolver_curso_post_confirmacion(estudiante)
                    if curso:
                        progreso, creado = ProgresoEstudiante.objects.get_or_create(
                            estudiante=estudiante,
                            curso=curso,
                            defaults={'completado': False}
                        )
                        modulo = progreso.modulo_actual
                        if not modulo:
                            modulo = curso.modulos.order_by('numero').first()
                            if modulo:
                                progreso.modulo_actual = modulo
                                from ..module_steps import reset_progreso_pasos_modulo
                                reset_progreso_pasos_modulo(progreso, save=False)
                                progreso.save(
                                    update_fields=[
                                        'modulo_actual',
                                        'paso_actual_modulo',
                                        'esperando_respuesta_evaluacion_paso',
                                        'paso_evaluacion_paso_id',
                                    ]
                                )
                        if modulo:
                            from core.inicio_curso import marcar_inicio_entregado
                            marcar_inicio_entregado(estudiante, curso.id)
                            # Get agent names: Cliente > Curso > defaults
                            cliente_obj = estudiante.cliente
                            nombre_tutor = (
                                (cliente_obj.nombre_agente_tutor if cliente_obj and hasattr(cliente_obj, 'nombre_agente_tutor') and cliente_obj.nombre_agente_tutor else '') or
                                curso.nombre_agente_tutor or 'Formador'
                            )
                            nombre_asistente = (
                                (cliente_obj.nombre_agente_asistente if cliente_obj and hasattr(cliente_obj, 'nombre_agente_asistente') and cliente_obj.nombre_agente_asistente else '') or
                                curso.nombre_agente_asistente or 'Compañero'
                            )
                            
                            # Presentación de agentes
                            from ..tutor_ia_modulo import generar_presentacion_agentes
                            msg_tutor, msg_asistente = generar_presentacion_agentes(
                                curso_nombre=curso.nombre,
                                estudiante_nombre=estudiante.nombre or 'Estudiante',
                                nombre_tutor=nombre_tutor,
                                nombre_asistente=nombre_asistente,
                                curso=curso,
                            )
                            
                            # Gamification explanation message
                            msg_gamificacion = ""
                            usar_gamificacion = (cliente_obj.usar_gamificacion if cliente_obj else True)
                            if usar_gamificacion:
                                msg_gamificacion = (
                                    "*Nuestra experiencia de formación funciona a través de puntos*\n\n"
                                    "A medida que avance en el curso, tendrá retos que evaluar.\n\n"
                                    "¡Vamos a aprender y avanzar juntos!"
                                )

                            # --- Mensaje 1: Bienvenida + Gamificación + Agentes (TODO EN UNO) ---
                            partes_intro = [
                                f"*¡Datos confirmados, {estudiante.nombre}!*\n\nBienvenido al programa de *{org_nombre}*"
                            ]
                            partes_intro.append(msg_tutor)
                            partes_intro.append(msg_asistente)
                            if msg_gamificacion:
                                partes_intro.append(msg_gamificacion)
                            partes_intro.append("*Comenzamos con el primer módulo de su curso...*")
                            msg_intro = "\n\n".join(partes_intro)

                            from ..module_steps import (
                                modulo_usa_pasos,
                                pasos_activos_qs,
                                reset_progreso_pasos_modulo,
                                entregar_bloque_secciones_desde_paso,
                                log_y_mensaje_modo_pasos_sin_pasos,
                            )

                            if modulo_usa_pasos(modulo):
                                if not pasos_activos_qs(modulo).exists():
                                    _fb_conf = log_y_mensaje_modo_pasos_sin_pasos(
                                        modulo, 'confirmando_datos_primer_modulo'
                                    )
                                    texto_respuesta = '[MULTI_MSG]' + msg_intro + '[SEP]' + _fb_conf
                                else:
                                    reset_progreso_pasos_modulo(progreso, save=True)
                                    msg_pasos_conf = entregar_bloque_secciones_desde_paso(
                                        progreso, modulo, 1
                                    )
                                    _inner_conf = msg_pasos_conf[len('[MULTI_MSG]') :]
                                    _pieces = [
                                        p for p in _inner_conf.split('[SEP]') if p
                                    ]
                                    texto_respuesta = '[MULTI_MSG]' + msg_intro + '[SEP]' + '[SEP]'.join(_pieces)
                            else:
                                video_url = obtener_video_url(modulo)
                                archivos_multimedia = modulo.archivos_multimedia.filter(activo=True)
                                archivos_msg = ""
                                primera_media_url = None
                                extra_media_urls = []
                                if archivos_multimedia.exists():
                                    archivos_msg = ""
                                    for idx, archivo in enumerate(archivos_multimedia):
                                        icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                        url = archivo.get_url_para_envio()
                                        if url:
                                            if not primera_media_url:
                                                primera_media_url = url
                                                archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                            else:
                                                extra_media_urls.append((url, archivo.titulo, icono))
                                                archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                        else:
                                            archivos_msg += f"\n{icono} {archivo.titulo}"
                                if not archivos_multimedia.exists() and video_url:
                                    primera_media_url = video_url

                                # --- Mensaje 2: Contenido del módulo (con multimedia) ---
                                from ..response_templates import dividir_contenido_seguro
                                from ..module_steps import texto_legacy_whatsapp
                                contenido_modulo = texto_legacy_whatsapp(modulo)
                                chunks = dividir_contenido_seguro(contenido_modulo, max_chars=1300)
                                modulo_header = f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                                if chunks:
                                    msg_modulo = modulo_header + chunks[0]
                                    for chunk in chunks[1:]:
                                        if len(msg_modulo) + len(chunk) + 4 < 1400:
                                            msg_modulo += "\n\n" + chunk
                                        else:
                                            break
                                else:
                                    msg_modulo = modulo_header + (modulo.descripcion or '')
                                # v1.9.8: No mostrar labels de archivos en texto (se envían como mensajes separados)

                                # Orden: intro (con agentes) → módulo TEXTO → video(s) → [DELAY] → "escribe listo"
                                texto_respuesta = "[MULTI_MSG]" + msg_intro + "[SEP]" + msg_modulo
                                # Video principal como mensaje separado después del texto
                                hay_media_conf = False
                                if primera_media_url:
                                    texto_respuesta += f"[SEP]{parte_mensaje_con_media(primera_media_url)}"
                                    hay_media_conf = True
                                for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
                                    cap_extra = None  # el adjunto va solo, sin título
                                    texto_respuesta += f"[SEP]{parte_mensaje_con_media(extra_url, cap_extra)}"
                                    hay_media_conf = True
                                # "Escribe listo" AL FINAL — solo si hay más módulos
                                hay_mas_modulos = curso.modulos.filter(numero__gt=modulo.numero).exists()
                                if hay_mas_modulos:
                                    if hay_media_conf:
                                        texto_respuesta += "[SEP][DELAY:5]"
                                    from ..avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo
                                    texto_respuesta += "[SEP]" + resolver_cta_listo(
                                        estudiante, curso, CTX_FIN_ENTREGA_MODULO
                                    )
                        else:
                            texto_respuesta = f"*¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nEl curso aún no tiene módulos configurados. Le notificaremos cuando estén listos."
                    else:
                        texto_respuesta = f"*¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nAún no hay cursos disponibles. Le notificaremos cuando estén listos."
                except Exception as e:
                    logger.error(f"❌ Error enviando curso directo: {e}")
                    import traceback; traceback.print_exc()
                    texto_respuesta = f"*¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nSu organización le notificará cuando estén listos los cursos. Escriba *ayuda* si necesita asistencia."
                
                # MENÚ OCULTO (no eliminado del código):
                # from .whatsapp_service import enviar_menu_principal
                # resultado = enviar_menu_principal(msg_from, estudiante.nombre)
                # if resultado.get('success'):
                #     return
            elif any(k in msg_lower for k in keywords_modificar):
                # Botón "Modificar" presionado → crear ticket de soporte directamente
                from ..models import SolicitudSoporte
                SolicitudSoporte.objects.create(
                    estudiante=estudiante,
                    mensaje_original=f"Solicitud de corrección de datos desde verificación. Datos actuales: Nombre={estudiante.nombre}, Cédula={estudiante.cedula}, Municipio={estudiante.municipio}",
                    keyword_usada='correccion_datos',
                    asunto='Corrección de datos desde verificación',
                    estado='pendiente'
                )
                texto_respuesta = (
                    "📝 *Solicitud de Corrección Recibida*\n\n"
                    f"Hola {estudiante.nombre}, hemos creado un ticket de soporte "
                    "para la corrección de tus datos.\n\n"
                    "📧 *Nuestro equipo te contactará pronto.*"
                )
                estudiante.estado_chat = 'ACTIVO'
                estudiante.estado_onboarding = 'completado'
                estudiante.save()
            else:
                # Re-enviar la plantilla de confirmación (tiene botones Confirmar/Modificar)
                from ..whatsapp_service import enviar_confirmacion_datos
                org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                resultado_reenvio = enviar_confirmacion_datos(
                    msg_from,
                    estudiante.nombre,
                    f"{estudiante.tipo_documento} {estudiante.cedula}",
                    org_nombre,
                    edad=estudiante.edad,
                    municipio=estudiante.municipio,
                )
                if resultado_reenvio.get('success'):
                    return  # Template reenviado, no necesita texto
                texto_respuesta = (
                    "Por favor revisa tus datos y toca *Confirmar* o *Modificar* en la plantilla."
                )
            
            try:
                from core.lineas.entrega import enviar_marcado

                enviar_marcado(msg_from, telefono_limpio, texto_respuesta, registro='segmentos')
            except Exception as e:
                logger.error(f"❌ Error enviando confirmación: {e}")
                import traceback; traceback.print_exc()
            return  # CORTAR EJECUCIÓN
        
        # --- BARRERA 3B: LEGACY AUTO-CORRECCIÓN → Redirigir a ACTIVO ---
        if estado_chat in ('ESPERANDO_AYUDA_MODIFICAR', 'ESPERANDO_CORRECCION_DATOS'):
            # Ya no hay menú de corrección — redirigir al flujo normal
            estudiante.estado_chat = 'ACTIVO'
            estudiante.estado_onboarding = 'completado'
            estudiante.save()
            
            msg_lower = msg_body.strip().lower()
            
            # Si dice "continuar", "sí" o similar → enviar al curso
            keywords_continuar = ['continuar', 'sí', 'si', 'ok', 'listo', 'seguir', 'menu', 'menú']
            keywords_ayuda = ['ayuda', 'soporte', 'ticket', 'problema']
            
            if any(k in msg_lower for k in keywords_ayuda):
                from ..models import SolicitudSoporte
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
            return
        
        # ============================================================
        # ESTUDIANTE ACTIVO - Procesar acciones del menú y flujo normal
        # ============================================================
        # Detectar acciones del menú principal (tanto ACTIVO como completado)
        if estado_chat == 'ACTIVO' or estudiante.estado_onboarding == 'completado':
            msg_lower = msg_body.strip().lower()
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
                    return
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
                        return
                except Exception as e:
                    logger.error(f"❌ Agente formulario: {e}", exc_info=True)
            
            # PRIORIDAD: Si está seleccionando curso, NO interceptar números
            # (B2B con 2+ cursos también usa este menú numerado)
            if estudiante.estado_onboarding == 'esperando_seleccion_curso':
                if msg_lower in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    from ..response_templates import get_response_for_intent
                    texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                else:
                    # Extraer número del curso: soporta "tomar 1", "1", "tomar1"
                    import re as re_curso
                    indice = None
                    match_tomar = re_curso.match(r'^tomar\s*(\d+)$', msg_lower)
                    if match_tomar:
                        indice = int(match_tomar.group(1))
                    elif msg_body.strip().isdigit():
                        indice = int(msg_body.strip())
                    
                    if indice is not None:
                        from ..selector_curso import continuar_curso_seleccionado
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save(update_fields=['estado_onboarding'])
                        texto_respuesta = continuar_curso_seleccionado(estudiante.id, indice, msg_body)
                        logger.info(f"✅ Curso seleccionado: {indice}")
                    else:
                        # No es número ni menú → resetear y procesar normalmente
                        estudiante.estado_onboarding = 'completado'
                        estudiante.contexto_temporal = None
                        estudiante.save()
                        from core.eventos_ia import detectar_intent_con_evento
                        from ..response_templates import get_response_for_intent
                        _p0 = estudiante.progresos.order_by('-fecha_inicio').first()
                        intent = detectar_intent_con_evento(
                            msg_body,
                            estudiante=estudiante,
                            curso=_p0.curso if _p0 else None,
                            modulo=_p0.modulo_actual if _p0 else None,
                        )
                        if intent != 'desconocido':
                            texto_respuesta = get_response_for_intent(intent, estudiante.nombre, estudiante_id=estudiante.id, mensaje_original=msg_body)
                        else:
                            texto_respuesta = "No entendí tu selección. Escribe *tomar 1* para escoger un curso o *menú* para volver."
                # — Enviar respuesta de selección de curso y CORTAR —
                try:
                    from core.lineas.entrega import enviar_marcado

                    enviar_marcado(msg_from, telefono_limpio, texto_respuesta, registro='cierre')
                except Exception as e:
                    logger.error(f"❌ Error enviando selección curso: {e}")
                return  # CORTAR EJECUCIÓN

            # ============================================================
            # PRIORIDAD: Si el estudiante está interactuando con un AGENTE
            # (Darío, Facilitadora, Tutor IA, etc.), NO interceptar con
            # el gate de "solo listo" — dejar que el flujo caiga al handler
            # del agente más abajo en el código.
            # ============================================================
            estados_agente = [
                'esperando_respuesta_asistente',     # Darío
                'esperando_respuesta_reto',          # Facilitadora
                'esperando_respuesta_tutor_ia',      # Tutor legacy
                'esperando_respuesta_progreso',      # María
                'esperando_respuesta_modulo',         # Evaluación módulo
                'esperando_respuesta_pregunta_abierta_final',  # Respuesta final calificada por facilitadora
            ]
            from core.empleabilidad_pausa import empleabilidad_en_pausa as _emp_pausa_gate
            # Radar: código de aliado (no gate *listo*) — pausado no intercepta.
            if not _emp_pausa_gate():
                estados_agente.append('esperando_codigo_empleabilidad')
            if estudiante.estado_onboarding in estados_agente:
                logger.info(f"🤖 Agente activo ({estudiante.estado_onboarding}) — bypassing gate listo")
                # No interceptar — caerá al flujo EXISTENTE más abajo (handlers de agente)

            # Detectar "Mis cursos" → rama legacy deshabilitada (curso sin menú)
            elif False and msg_lower in ['1', 'mis cursos', 'cursos', '📚 mis cursos']:
                pass

            else:
                from core.lineas.pqrs_linea import respuesta_en_puerta
                if respuesta_en_puerta(estudiante, msg_body, msg_from, telefono_limpio):
                    return

                # 🎥 Reenvío de video/material (sin avanzar curso) — antes de eval/listo
                if estado_chat == 'ACTIVO':
                    try:
                        from ..media_recuperacion import intentar_reenvio_media_curso
                        from ..utils import enviar_whatsapp_twilio as _enviar_reenvio
                        from ..twilio_media import mensaje_log_con_media
                        import re as _re_rx

                        _resp_reenvio = intentar_reenvio_media_curso(estudiante, msg_body)
                        if _resp_reenvio:
                            logger.info('🎥 Reenvío media curso | est=%s', estudiante.id)
                            raw = _resp_reenvio
                            if raw.startswith('[MULTI_MSG]'):
                                partes = raw.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                            else:
                                partes = [raw]
                            for parte in partes:
                                parte_texto = (parte or '').strip()
                                if not parte_texto:
                                    continue
                                delay_m = _re_rx.match(r'^\[DELAY:(\d+)\]$', parte_texto)
                                if delay_m:
                                    import time as _t_delay
                                    _t_delay.sleep(int(delay_m.group(1)))
                                    continue
                                parte_media = None
                                mm = _re_rx.search(r'\[MEDIA:(.*?)\]', parte_texto)
                                if mm:
                                    parte_media = (mm.group(1) or '').strip()
                                    parte_texto = parte_texto.replace(mm.group(0), '').strip()
                                cuerpo = parte_texto or (' ' if parte_media else '')
                                _enviar_reenvio(
                                    msg_from,
                                    cuerpo,
                                    media_url=parte_media,
                                    texto_log=mensaje_log_con_media(cuerpo, parte_media),
                                )
                            WhatsappLog.objects.create(
                                telefono=telefono_limpio,
                                mensaje=(_resp_reenvio or '')[:500],
                                tipo='SENT',
                                agente_usado='REENVIAR_MEDIA',
                            )
                            return
                    except Exception:
                        logger.exception('Reenvío media curso omitido')

                from core.lineas.paso import responder_evaluacion_paso
                if responder_evaluacion_paso(
                    estudiante, msg_body, msg_from, telefono_limpio, estado_chat,
                ):
                    return

                from core.lineas.pqrs_linea import corregir_datos_si_pide
                if corregir_datos_si_pide(estudiante, msg_lower, msg_from, telefono_limpio):
                    return

                if not _mensaje_indica_listo(msg_body):
                    if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                        texto_respuesta = (
                            "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo o escríbeme. "
                            "Para avanzar, Pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
                        )
                    else:
                        texto_respuesta = (
                            "No entendí. Si quiere avanzar de módulo, pulse continuar, para seguir aprendiendo. "
                            "Si necesitas ayuda, escribe *ayuda*.\n\n" + _MARCADOR_CONTINUEMOS
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
                        logger.error(f"❌ Error enviando respuesta no entendida: {e}")
                    return

            # Detectar "Mis puntos" (botón o texto) - rama legacy
            if msg_lower in ['2', 'mis puntos', 'puntos', '🏆 mis puntos']:
                from ..whatsapp_service import enviar_gamificacion_visual
                enviar_gamificacion_visual(msg_from, estudiante)
                return
            
            # Detectar "Necesito ayuda" / PQRS / Soporte (todo unificado)
            elif msg_lower in ['3', 'necesito ayuda', 'ayuda', '🙋‍♂️ necesito ayuda', 'pqrs', 'soporte', 'queja', 'reclamo', 'solicitud']:
                from ..security_handler import procesar_solicitud_soporte
                respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'menu_ayuda')
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=respuesta, tipo='SENT')
                except Exception:
                    pass
                return
            
            # Detectar "corregir datos" / "me equivoqué" -> iniciar autocorreccion guiada
            elif msg_lower in ['4', 'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
                               'me equivoqué', 'me equivoque', 'editar datos', 'modificar datos',
                               'datos incorrectos', 'mis datos', 'actualizar datos']:
                from ..correccion_datos import iniciar_flujo_correccion
                texto_respuesta = iniciar_flujo_correccion(estudiante)
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
                    logger.error(f"❌ Error enviando corrección datos: {e}")
                return
            
            # Detectar "menú" → enviar directamente al curso asignado (sin lista)
            elif msg_lower in ['menu', 'menú', 'inicio', 'hola']:
                if estudiante.estado_onboarding in estados_agente:
                    logger.info(
                        "menu/inicio/hola durante agente pedagógico (%s) — omitir reenvío de módulo",
                        estudiante.estado_onboarding,
                    )
                else:
                    from ..models import Curso, ProgresoEstudiante
                    from ..response_templates import obtener_video_url
                    org = estudiante.cliente
                    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre') if org else Curso.objects.filter(activo=True).order_by('orden', 'nombre')
                    progreso_existente = ProgresoEstudiante.objects.filter(
                        estudiante=estudiante, completado=False, curso__activo=True
                    ).first()
                    curso = progreso_existente.curso if progreso_existente else cursos.first()
                    if curso:
                        progreso, _ = ProgresoEstudiante.objects.get_or_create(
                            estudiante=estudiante, curso=curso, defaults={'completado': False}
                        )
                        modulo = progreso.modulo_actual
                        if not modulo:
                            modulo = curso.modulos.order_by('numero').first()
                            if modulo:
                                progreso.modulo_actual = modulo
                                from ..module_steps import reset_progreso_pasos_modulo
                                reset_progreso_pasos_modulo(progreso, save=False)
                                progreso.save(
                                    update_fields=[
                                        'modulo_actual',
                                        'paso_actual_modulo',
                                        'esperando_respuesta_evaluacion_paso',
                                        'paso_evaluacion_paso_id',
                                    ]
                                )
                        if modulo:
                            from ..module_steps import (
                                modulo_usa_pasos,
                                mensaje_recordatorio_paso_actual,
                                pasos_activos_qs,
                                log_y_mensaje_modo_pasos_sin_pasos,
                            )
                            if modulo_usa_pasos(modulo):
                                if not pasos_activos_qs(modulo).exists():
                                    texto_respuesta = log_y_mensaje_modo_pasos_sin_pasos(
                                        modulo, 'views_menu_inicio'
                                    )
                                else:
                                    _np_m = pasos_activos_qs(modulo).count()
                                    if (
                                        progreso.paso_actual_modulo > _np_m
                                        and not progreso.esperando_respuesta_evaluacion_paso
                                    ):
                                        texto_respuesta = (
                                            "✅ Ya recibiste todo el material de esta unidad.\n\n"
                                            "Pulse continuar, para seguir aprendiendo.\n\n"
                                            + _MARCADOR_CONTINUEMOS
                                        )
                                    else:
                                        _rem_m = mensaje_recordatorio_paso_actual(progreso, modulo)
                                        texto_respuesta = _rem_m or (
                                            f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                                            "Escribe *continuar* o *listo* cuando quieras seguir."
                                        )
                            else:
                                video_url = obtener_video_url(modulo)
                                archivos_multimedia = modulo.archivos_multimedia.filter(activo=True)
                                archivos_msg = ""
                                primera_media_url = None
                                extra_media_urls = []
                                if archivos_multimedia.exists():
                                    archivos_msg = ""
                                    for idx, archivo in enumerate(archivos_multimedia):
                                        icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                        url = archivo.get_url_para_envio()
                                        if url:
                                            if not primera_media_url:
                                                primera_media_url = url
                                                archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                            else:
                                                extra_media_urls.append((url, archivo.titulo, icono))
                                                archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                        else:
                                            archivos_msg += f"\n{icono} {archivo.titulo}"
                                if not archivos_multimedia.exists() and video_url:
                                    primera_media_url = video_url
                                from ..module_steps import texto_legacy_whatsapp
                                msg_texto_menu = (
                                    f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                                    f"{texto_legacy_whatsapp(modulo)}"
                                )
                                partes_menu = [msg_texto_menu]
                                if primera_media_url:
                                    partes_menu.append(parte_mensaje_con_media(primera_media_url))
                                for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
                                    partes_menu.append(parte_mensaje_con_media(extra_url))
                                if len(partes_menu) > 1:
                                    texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes_menu)
                                else:
                                    texto_respuesta = msg_texto_menu
                        else:
                            texto_respuesta = f"📚 Tu curso *{curso.nombre}* aún no tiene módulos configurados."
                    else:
                        texto_respuesta = (
                            "📚 Aún no tienes un curso asignado. "
                            "Tu coordinador te lo asignará pronto.\n\n"
                            "Si acaba de reportar un problema, cuando quiera retomar, pulse continuar, para seguir aprendiendo. O escriba *menú*.\n\n"
                            + _MARCADOR_CONTINUEMOS
                        )
                    try:
                        from twilio.rest import Client as TwilioClient
                        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                        twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                        client_tw = TwilioClient(account_sid, auth_token)
                        destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                        twilio_from = str(twilio_number).strip()

                        if texto_respuesta.startswith('[MULTI_MSG]'):
                            import re as re_menu_m
                            partes_mm = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                            for parte_mm in partes_mm:
                                if not parte_mm.strip():
                                    continue
                                parte_txt = parte_mm.strip()
                                delay_mm = re_menu_m.match(r'^\[DELAY:(\d+)\]$', parte_txt)
                                if delay_mm:
                                    import time
                                    time.sleep(int(delay_mm.group(1)))
                                    continue
                                media_mm = re_menu_m.search(r'\[MEDIA:(.*?)\]', parte_txt)
                                parte_media_mm = None
                                if media_mm:
                                    parte_media_mm = media_mm.group(1).strip()
                                    parte_txt = parte_txt.replace(media_mm.group(0), '').strip()
                                cuerpo_mm = parte_txt.strip() if parte_txt else ''
                                enviados_mm = _enviar_mensaje_twilio_segmentado(
                                    client=client_tw,
                                    from_number=twilio_from,
                                    to_number=str(destino).strip(),
                                    body=cuerpo_mm if cuerpo_mm else ' ',
                                    media_url=parte_media_mm,
                                )
                                import time
                                time.sleep(0.5)
                                from ..twilio_media import mensaje_log_con_media
                                for seg_i, (msg_mm, texto_env) in enumerate(enviados_mm, start=1):
                                    WhatsappLog.objects.create(
                                        telefono=telefono_limpio,
                                        mensaje=mensaje_log_con_media(
                                            texto_env or cuerpo_mm or parte_txt,
                                            parte_media_mm if seg_i == 1 else None,
                                        )[:1500],
                                        mensaje_id=getattr(msg_mm, 'sid', None),
                                        tipo='SENT',
                                    )
                        else:
                            media_url_menu = None
                            import re as re_menu
                            media_m = re_menu.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
                            if media_m:
                                media_url_menu = media_m.group(1).strip()
                                texto_respuesta = texto_respuesta.replace(media_m.group(0), '').strip()
                            enviados_menu = _enviar_mensaje_twilio_segmentado(
                                client=client_tw,
                                from_number=twilio_from,
                                to_number=str(destino).strip(),
                                body=texto_respuesta,
                                media_url=media_url_menu,
                            )
                            from ..twilio_media import mensaje_log_con_media
                            for seg_i, (msg_menu, texto_env) in enumerate(enviados_menu, start=1):
                                WhatsappLog.objects.create(
                                    telefono=telefono_limpio,
                                    mensaje=mensaje_log_con_media(
                                        texto_env or texto_respuesta,
                                        media_url_menu if seg_i == 1 else None,
                                    )[:1500],
                                    mensaje_id=getattr(msg_menu, 'sid', None),
                                    tipo='SENT',
                                )
                    except Exception as e:
                        logger.error(f"❌ Error enviando curso: {e}")
                    return
        
        # ============================================================
        # PQRS: seguimiento de ticket abierto (cede a pedagogía / agentes)
        # ============================================================
        from core.lineas.pqrs_linea import seguimiento_en_linea
        pqrs_atendido, respuesta_pqrs = seguimiento_en_linea(estudiante, msg_body)

        # ============================================================
        # FLUJO EXISTENTE: Procesamiento normal (IA tutors, módulos, etc.)
        # ============================================================
        
        # 3. 🛡️ PRIORIDAD 1: Verificar seguridad (Habeas Data) - Legacy
        from ..security_handler import verificar_seguridad_completa
        if pqrs_atendido:
            bloqueado = True
            respuesta_seguridad = respuesta_pqrs
        else:
            bloqueado, respuesta_seguridad, estudiante = verificar_seguridad_completa(
                estudiante,
                msg_body,
                telefono_limpio,
                numero_destino=msg_to,
            )
        print(f"🛡️ Seguridad: bloqueado={bloqueado} | estudiante={estudiante} | estado={getattr(estudiante, 'estado_onboarding', 'N/A')}", flush=True)
        
        # Default safety - will be overwritten by any branch below
        texto_respuesta = _TEXTO_NO_ENTENDI
        
        if bloqueado:
            print(f"🛡️ Bloqueado por seguridad/habeas data", flush=True)
            texto_respuesta = respuesta_seguridad
        else:
            # Si el contexto de agente quedó y el estado se desincronizó, no caer
            # en continuar_leccion (saltaría Darío / facilitadora).
            try:
                _ctx_agente_sync = estudiante.contexto_temporal or {}
                _tipo_ctx = _ctx_agente_sync.get('tipo')
                if _tipo_ctx == 'asistente_dario' and estudiante.estado_onboarding != 'esperando_respuesta_asistente':
                    _ob_prev = estudiante.estado_onboarding
                    estudiante.estado_onboarding = 'esperando_respuesta_asistente'
                    estudiante.save(update_fields=['estado_onboarding'])
                    logger.warning(
                        "🔄 Darío: estado resincronizado %s → esperando_respuesta_asistente "
                        "(ctx=asistente_dario) estudiante_id=%s",
                        _ob_prev,
                        estudiante.id,
                    )
                elif _tipo_ctx == 'reto_facilitador' and estudiante.estado_onboarding != 'esperando_respuesta_reto':
                    _ob_prev = estudiante.estado_onboarding
                    estudiante.estado_onboarding = 'esperando_respuesta_reto'
                    estudiante.save(update_fields=['estado_onboarding'])
                    logger.warning(
                        "🔄 Facilitadora: estado resincronizado %s → esperando_respuesta_reto "
                        "(ctx=reto_facilitador) estudiante_id=%s",
                        _ob_prev,
                        estudiante.id,
                    )
            except Exception as e:
                logger.warning("⚠️ Sync agente pedagógico omitido: %s", e)

            from core.conversacion.estados.despacho import agente_de

            _agente = agente_de(estudiante.estado_onboarding)
            if _agente is not None:
                texto_respuesta = _agente(Contexto(
                    estudiante, msg_body, msg_from, telefono_limpio,
                    msg_sid=msg_sid, texto_respuesta=texto_respuesta,
                    evidencia_imagen_url=evidencia_imagen_url, evidencia_imagen_type=evidencia_imagen_type,
                )).texto
            
            # 4. Detectar intent y usar templates primero
            else:
                from core.eventos_ia import detectar_intent_con_evento
                from ..response_templates import get_response_for_intent

                _prog = None
                try:
                    _prog = estudiante.progresos.order_by('-fecha_inicio').first()
                except Exception:
                    pass
                intent = detectar_intent_con_evento(
                    msg_body,
                    estudiante=estudiante,
                    curso=_prog.curso if _prog else None,
                    modulo=_prog.modulo_actual if _prog else None,
                )
                print(f"🎯 Intent detectado: {intent}")
            
                # Intent especial: corregir datos → redirigir al flujo de corrección
                if intent == 'corregir_datos':
                    estudiante.estado_chat = 'ESPERANDO_CORRECCION_DATOS'
                    estudiante.save()
                    texto_respuesta = (
                        "📝 *Corrección de Datos*\n\n"
                        "Puedes corregir cualquiera de tus datos.\n\n"
                        "Escribe el campo que deseas cambiar seguido del nuevo valor:\n\n"
                        "1️⃣ *nombre:* Tu nombre completo\n"
                        "2️⃣ *municipio:* Tu municipio\n"
                        "3️⃣ *departamento:* Tu departamento\n"
                        "4️⃣ *documento:* Tipo y número (CC, TI, CE, PP)\n"
                        "5️⃣ *edad:* Tu edad\n"
                        "6️⃣ *genero:* M, F, Otro, NR\n\n"
                        "📝 _Ejemplos:_\n"
                        "_nombre: María García López_\n"
                        "_municipio: Bogotá_\n"
                        "_edad: 35_\n\n"
                        "👉 Escribe *menú* cuando termines"
                    )
                # Si hay un intent conocido, usar template
                elif intent != 'desconocido':
                    texto_respuesta = get_response_for_intent(
                        intent, 
                        estudiante.nombre,
                        estudiante_id=estudiante.id,
                        mensaje_original=msg_body
                    )
                    print(f"✅ Respuesta desde template: {texto_respuesta[:50]}...")
                    if texto_respuesta == LECCION_EN_CURSO:
                        from core.sandbox_canal import descartar_reaccion_espera

                        descartar_reaccion_espera(telefono_limpio)
                        return
                else:
                    # Solo si no hay intent, usar IA para preguntas sobre agricultura
                    # 🛑 ANTI-ABUSO IA: Verificar preguntas restantes
                    print(f"🤖 Usando IA para pregunta sobre agricultura")
                    if estudiante.preguntas_ia_restantes <= 0:
                        # Freno de mano: IA pausada
                        from ..avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo
                        _prog_ia = estudiante.progresos.order_by('-fecha_inicio').first()
                        _curso_ia = _prog_ia.curso if _prog_ia else None
                        texto_respuesta = (
                            "[MULTI_MSG]⚠️ *Has agotado tus preguntas libres a la IA para este modulo.*\n\n"
                            "Para desbloquear mas preguntas, necesitas responder "
                            "la pregunta de evaluacion del modulo actual."
                            "[SEP]"
                            + resolver_cta_listo(estudiante, _curso_ia, CTX_FIN_ENTREGA_MODULO)
                        )
                    else:
                        try:
                            from core.sandbox_canal import poner_reaccion_espera
                            from ..ai_assistant import responder_con_ia

                            poner_reaccion_espera(telefono_limpio, msg_sid)
                            texto_respuesta = responder_con_ia(msg_body, telefono_limpio)
                            # Restar pregunta usada (anti-abuso silencioso)
                            estudiante.preguntas_ia_restantes = max(0, estudiante.preguntas_ia_restantes - 1)
                            estudiante.save()
                            print(f"✅ IA generó respuesta: {texto_respuesta[:50]}...")
                        except Exception as e:
                            print(f"❌ Error IA: {e}, usando respuesta genérica")
                            texto_respuesta = "Disculpa, tengo problemas técnicos. Vuelve a escribir tu mensaje para continuar."
        
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
                        from ..whatsapp_service import enviar_template_twilio
                        tel_limpio = msg_from.replace('whatsapp:', '').replace('+', '')
                        enviar_template_twilio(tel_limpio, template_sid)
                        print(f"✅ Template {template_sid} enviado OK")
                    except Exception as tmpl_err:
                        print(f"⚠️ Error enviando template standalone: {tmpl_err}")
                    return
            
            # Check if response is a multi-message (marked with [MULTI_MSG])
            if texto_respuesta.startswith('[MULTI_MSG]'):
                # Extract and send multiple messages
                partes = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                
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
                                from ..whatsapp_service import enviar_template_twilio
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
                        from ..twilio_media import mensaje_log_con_media

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

                    from ..twilio_media import mensaje_log_con_media

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
    
    except Exception as e:
        print(f"❌ Error en _procesar_twilio_webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # ============================================================
        # SAFETY NET: Siempre enviar ALGO al usuario, nunca quedar mudo
        # ============================================================
        try:
            msg_from_fallback = post_data.get('From', '')
            if msg_from_fallback:
                from twilio.rest import Client
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                twilio_number = str(twilio_number).strip()
                
                if account_sid and auth_token:
                    client = Client(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from_fallback}' if not msg_from_fallback.startswith('whatsapp:') else msg_from_fallback
                    destino = str(destino).strip()
                    client.messages.create(
                        body="⚠️ Tuvimos un problema técnico momentáneo. Por favor vuelve a escribir tu mensaje para continuar.",
                        from_=twilio_number,
                        to=destino
                    )
                    print(f"✅ Safety net: mensaje de error enviado a {destino}")
        except Exception as fallback_err:
            print(f"❌ Safety net también falló: {fallback_err}")
    finally:
        soltar_turno_entrega_actual()
        cerrar_retencion_turno(_turno_token)
