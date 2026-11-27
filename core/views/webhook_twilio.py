import logging

from django.conf import settings
from django.utils import timezone

from ..models import Estudiante, WhatsappLog

logger = logging.getLogger(__name__)

def _intentar_aula_twilio_fuera_de_activo(post_data) -> bool:
    """*aula* en Twilio aunque el chat no esté ACTIVO. No entra al cuerpo."""
    from core.canal.sandbox_canal import inbound_es_meta

    if inbound_es_meta(post_data):
        return False
    status = (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').strip()
    if status:
        return False
    from core.puentes import emitir_acceso_desde_whatsapp, mensaje_pide_acceso_aula
    from core.conversacion.habeas_respuestas import texto_desde_webhook_twilio
    from core.agentes.nati import normalizar_telefono_whatsapp
    from core.canal.utils_telefono import estudiante_por_telefono

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
    from core.canal.envios import enviar_whatsapp_twilio

    enviar_whatsapp_twilio(post_data.get('From', ''), texto, agente_evento='aula_twilio')
    return True


def _turno_desde_post(post_data, canal):
    """Turno del mensaje: teléfono, línea, perfil y canal. Sin consultas a la base."""
    from core.conversacion.turno import Turno
    from core.lineas.meta import nombre_de_linea
    from core.lineas.variante import perfil_de
    from core.canal.wa_canal import CANAL_TWILIO

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
    from core.canal.utils_telefono import estudiante_por_telefono

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
    import importlib

    _identidad = importlib.import_module('core.lineas.identidad')
    _cortar_certificado_meta = _identidad.cortar_certificado_meta
    _cortar_habeas_meta = _identidad.cortar_habeas_meta
    _menu_tras_confirmar_datos_meta = _identidad.menu_tras_confirmar_datos_meta
    _twilio_transporte = importlib.import_module('core.views.twilio_transporte')
    _es_status_callback_twilio = _twilio_transporte._es_status_callback_twilio
    _registrar_estado_twilio_callback = _twilio_transporte._registrar_estado_twilio_callback

    from core.conversacion.medicion import medir_turno
    from core.conversacion.turno import turno_activo
    from core.canal.sandbox_canal import activar_sandbox_meta_si_inbound, inbound_es_meta
    from core.canal.wa_canal import CANAL_META, CANAL_TWILIO, canal_webhook

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
    import importlib

    _registrar_estado_twilio_callback = importlib.import_module(
        'core.views.twilio_transporte',
    )._registrar_estado_twilio_callback
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
    
    from ..conversacion.response_templates import (
        LECCION_EN_CURSO,
        activar_retencion_turno,
        cerrar_retencion_turno,
        soltar_turno_entrega_actual,
    )

    _turno_token = activar_retencion_turno()
    Contexto = importlib.import_module('core.conversacion.contexto').Contexto
    _TEXTO_NO_ENTENDI = importlib.import_module(
        'core.conversacion.avance_whatsapp',
    ).TEXTO_NO_ENTENDI
    _transcribir_audio_twilio = importlib.import_module(
        'core.views.audio',
    )._transcribir_audio_twilio
    _intentar_responder_envio_certificado = importlib.import_module(
        'core.views.certificados_wa',
    )._intentar_responder_envio_certificado
    _registrar_estado_twilio_callback = importlib.import_module(
        'core.views.twilio_transporte',
    )._registrar_estado_twilio_callback
    try:
        logger.info("🔵 TWILIO: Procesando...")
        
        # Twilio envía datos en formato form-data
        msg_body = post_data.get('Body', '')
        # Quick reply / botones Content: a veces Body vacío y solo ButtonPayload/Text
        from ..conversacion.habeas_respuestas import texto_desde_webhook_twilio

        msg_body = texto_desde_webhook_twilio(post_data, msg_body)
        msg_from = post_data.get('From', '')  # whatsapp:+573001234567
        msg_to = post_data.get('To', '')      # whatsapp:+14155238886
        msg_sid = post_data.get('MessageSid', f'twilio_{timezone.now().timestamp()}')

        # Evita procesar dos veces el mismo mensaje entrante si Twilio reintenta.
        if msg_sid and WhatsappLog.objects.filter(mensaje_id=msg_sid, tipo='INCOMING').exists():
            logger.info("♻️ Twilio inbound duplicado ignorado | sid=%s", msg_sid)
            return

        from core.agentes.eventos_ia import set_trace_id
        set_trace_id()
        
        logger.info(f"📱 Body: {msg_body} | From: {msg_from} | To: {msg_to}")

        # 🎤 DETECTAR AUDIO: Twilio envía audios como MediaUrl
        num_media = int(post_data.get('NumMedia', 0))
        media_type = post_data.get('MediaContentType0', '')
        media_url = post_data.get('MediaUrl0', '')
        latitud_raw = post_data.get('Latitude')
        longitud_raw = post_data.get('Longitude')
        print(f"🎤 DEBUG AUDIO: NumMedia={num_media}, MediaType='{media_type}', MediaUrl={bool(media_url)}, Body='{msg_body[:30] if msg_body else ''}'", flush=True)

        from core.canal.twilio_inbound_media import es_audio_inbound_twilio

        es_audio = es_audio_inbound_twilio(num_media, media_type, media_url)
        # Imagen: puede ser evidencia de un reto de campo (se resuelve en esa rama).
        es_imagen_soportada = importlib.import_module(
            'core.conversacion.reto_evidencia',
        ).es_imagen_soportada

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
        import importlib
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
            from core.agentes.eventos_ia import emit_webhook_recibido
            from core.agentes.ai_capabilities import resolver_ai_capability

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

            intercepciones = importlib.import_module('core.conversacion.estados.intercepciones')

            if intercepciones.manejar(Contexto(
                estudiante,
                msg_body,
                msg_from,
                telefono_limpio,
                msg_sid=msg_sid,
                locales={'latitud_raw': latitud_raw, 'longitud_raw': longitud_raw, 'post_data': post_data},
            )) is not None:
                return

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
            no_registrado = importlib.import_module('core.conversacion.estados.no_registrado')

            no_registrado.manejar(Contexto(
                None,
                msg_body,
                msg_from,
                telefono_limpio,
                locales={'post_data': post_data},
            ))
            return
        
        # ============================================================
        # MÁQUINA DE ESTADOS B2B (Onboarding con Botones Twilio)
        # ============================================================
        arranque = importlib.import_module('core.conversacion.estados.arranque')

        estado_chat = arranque.manejar(Contexto(estudiante, None, None, None))

        prioridad_global = importlib.import_module('core.conversacion.estados.prioridad_global')

        if prioridad_global.manejar(Contexto(
            estudiante,
            msg_body,
            msg_from,
            telefono_limpio,
            estado_chat=estado_chat,
        )) is not None:
            return
        
        # --- BARRERA 1: HABEAS DATA ---
        if estado_chat == 'ESPERANDO_HABEAS_DATA':
            habeas = importlib.import_module('core.conversacion.estados.habeas')

            if habeas.manejar(Contexto(estudiante, msg_body, msg_from, telefono_limpio)) is not None:
                return  # CORTAR EJECUCIÓN
        
        # --- BARRERAS 2, 3 y 3B: cédula (2FA), confirmación de datos y corrección legado ---
        _BARRERAS = importlib.import_module('core.conversacion.estados.despacho').BARRERAS
        _barrera = _BARRERAS.get(estado_chat)
        if _barrera is not None:
            _barrera(Contexto(estudiante, msg_body, msg_from, telefono_limpio))
            return  # CORTAR EJECUCIÓN
        
        # ============================================================
        # ESTUDIANTE ACTIVO - Procesar acciones del menú y flujo normal
        # ============================================================
        # Detectar acciones del menú principal (tanto ACTIVO como completado)
        if estado_chat == 'ACTIVO' or estudiante.estado_onboarding == 'completado':
            msg_lower = msg_body.strip().lower()
            activo_entrada = importlib.import_module('core.conversacion.estados.activo_entrada')

            if activo_entrada.manejar(Contexto(
                estudiante,
                msg_body,
                msg_from,
                telefono_limpio,
                estado_chat=estado_chat,
                locales={'msg_lower': msg_lower},
            )) is not None:
                return
            
            # PRIORIDAD: Si está seleccionando curso, NO interceptar números
            # (B2B con 2+ cursos también usa este menú numerado)
            if estudiante.estado_onboarding == 'esperando_seleccion_curso':
                if msg_lower in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    from ..conversacion.response_templates import get_response_for_intent
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
                        from ..conversacion.selector_curso import continuar_curso_seleccionado
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save(update_fields=['estado_onboarding'])
                        texto_respuesta = continuar_curso_seleccionado(estudiante.id, indice, msg_body)
                        logger.info(f"✅ Curso seleccionado: {indice}")
                    else:
                        # No es número ni menú → resetear y procesar normalmente
                        estudiante.estado_onboarding = 'completado'
                        estudiante.contexto_temporal = None
                        estudiante.save()
                        from core.agentes.eventos_ia import detectar_intent_con_evento
                        from ..conversacion.response_templates import get_response_for_intent
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

            activo_puerta = importlib.import_module('core.conversacion.estados.activo_puerta')

            if activo_puerta.manejar(Contexto(
                estudiante,
                msg_body,
                msg_from,
                telefono_limpio,
                estado_chat=estado_chat,
                locales={'msg_lower': msg_lower},
            )) is not None:
                return
        
        # ============================================================
        # PQRS: seguimiento de ticket abierto (cede a pedagogía / agentes)
        # ============================================================
        seguimiento_en_linea = importlib.import_module(
            'core.lineas.pqrs_linea',
        ).seguimiento_en_linea
        pqrs_atendido, respuesta_pqrs = seguimiento_en_linea(estudiante, msg_body)

        # ============================================================
        # FLUJO EXISTENTE: Procesamiento normal (IA tutors, módulos, etc.)
        # ============================================================
        
        # 3. 🛡️ PRIORIDAD 1: Verificar seguridad (Habeas Data) - Legacy
        from core.conversacion.security_handler import verificar_seguridad_completa
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
            agente_sync = importlib.import_module('core.conversacion.estados.agente_sync')

            agente_sync.resincronizar(Contexto(estudiante, None, None, None))

            _agente_de = importlib.import_module('core.conversacion.estados.despacho').agente_de
            _agente = _agente_de(estudiante.estado_onboarding)
            if _agente is not None:
                texto_respuesta = _agente(Contexto(
                    estudiante, msg_body, msg_from, telefono_limpio,
                    msg_sid=msg_sid, texto_respuesta=texto_respuesta,
                    evidencia_imagen_url=evidencia_imagen_url, evidencia_imagen_type=evidencia_imagen_type,
                )).texto
            
            # 4. Detectar intent y usar templates primero
            else:
                intent_ia = importlib.import_module('core.conversacion.estados.intent_ia')

                _intent_ia = intent_ia.manejar(Contexto(
                    estudiante,
                    msg_body,
                    None,
                    telefono_limpio,
                    msg_sid=msg_sid,
                    locales={'LECCION_EN_CURSO': LECCION_EN_CURSO},
                ))
                if _intent_ia.cortar:
                    return
                texto_respuesta = _intent_ia.texto
        
        envio_comun = importlib.import_module('core.conversacion.estados.envio_comun')

        envio_comun.enviar(Contexto(estudiante, None, msg_from, telefono_limpio, texto_respuesta=texto_respuesta))
    
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
