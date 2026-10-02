from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt


from django.http import HttpResponse, JsonResponse, FileResponse, HttpResponseBadRequest
from django.core.files.storage import default_storage
import mimetypes
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, Max, Count
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from django.utils import timezone
import math
import requests
import tempfile
import os
import logging

# Logger para debugging
logger = logging.getLogger(__name__)

from ..models import Campana, Estudiante, WhatsappLog, EnvioLog, Cliente, Curso, ProgresoEstudiante, ModuloCompletado
from ..models_extras import ArchivoModulo, GrupoEstudiantes
from ..utils import enviar_whatsapp, enviar_whatsapp_twilio
from ..intent_detector import detect_intent, mensaje_indica_listo as _mensaje_indica_listo
from ..response_templates import (
    MENSAJE_CAPTION_SOLO_MEDIA as TWILIO_CAPTION_ADJUNTO,
    get_response_for_intent,
    parte_mensaje_con_media,
)

from django.views.decorators.csrf import csrf_exempt



def _audio_path_para_whisper(audio_path: str, mime_base: str) -> str:
    """Ogg/opus de WhatsApp a wav si pydub/ffmpeg están; si no, el original."""
    low = (mime_base or '').lower()
    if not any(x in low for x in ('ogg', 'opus', 'amr', 'aac')):
        return audio_path
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.rsplit('.', 1)[0] + '_w.wav'
        audio.export(wav_path, format='wav')
        try:
            os.remove(audio_path)
        except OSError:
            pass
        return wav_path
    except Exception as exc:
        print(f"⚠️ Conversión audio→wav omitida: {exc}")
        return audio_path


def _transcribir_audio_twilio(media_url, media_type='audio/ogg'):
    """
    Transcribe un audio de Twilio.
    
    Prioridad: OpenAI Whisper (confiable en producción), luego VOSK (offline).
    
    Args:
        media_url: URL del audio en Twilio
        media_type: MIME type del audio
    
    Returns:
        str: Texto transcrito o None si falla
    """
    if media_url and not str(media_url).startswith(('http://', 'https://')):
        from core.sandbox_canal import transcribir_audio_meta

        return transcribir_audio_meta(media_url, media_type)
    try:
        from core.twilio_inbound_media import descargar_bytes_twilio

        audio_bytes, ctype_dl = descargar_bytes_twilio(media_url, timeout=25)
        if not audio_bytes:
            print("⚠️ Audio Twilio vacío tras descarga")
            return None
        if ctype_dl and (not media_type or media_type in ('', 'application/octet-stream')):
            media_type = ctype_dl

        audio_size = len(audio_bytes)
        print(f"🎤 Transcribiendo audio ({audio_size} bytes)...")
        
        # Guardar temporalmente con extensión acorde al MIME enviado por Twilio
        # Normalizar: quitar parámetros MIME (e.g. "audio/ogg; codecs=opus" → "audio/ogg")
        mime_base = (media_type or '').split(';')[0].strip().lower()
        suffix_map = {
            'audio/ogg': '.ogg',
            'audio/opus': '.ogg',
            'audio/mpeg': '.mp3',
            'audio/mp3': '.mp3',
            'audio/mp4': '.m4a',
            'audio/aac': '.ogg',   # Whisper no soporta .aac, guardar como .ogg
            'audio/amr': '.ogg',   # Whisper no soporta .amr, guardar como .ogg
            'audio/webm': '.webm',
            'audio/wav': '.wav',
        }
        suffix = suffix_map.get(mime_base, '.ogg')

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(audio_bytes)
            audio_path = tmp_file.name
        audio_path = _audio_path_para_whisper(audio_path, mime_base)
        
        try:
            # OPCIÓN 1: WHISPER (OpenAI — confiable en producción)
            openai_api_key = getattr(settings, 'OPENAI_API_KEY', '')
            if openai_api_key:
                max_whisper_size = 20 * 1024 * 1024  # 20MB
                if audio_size <= max_whisper_size:
                    print(f"🎤 Transcribiendo con Whisper (archivo: {suffix}, {audio_size} bytes)...")
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_api_key)

                        with open(audio_path, 'rb') as audio_file:
                            transcription = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                language="es",
                            )

                        texto = (transcription.text or '').strip()
                        print(f"✅ Whisper transcribió: '{texto}'")
                        return texto if texto else None
                    except Exception as whisper_error:
                        print(f"❌ Error Whisper: {whisper_error}")
                        import traceback; traceback.print_exc()
                else:
                    print(f"⚠️ Audio demasiado grande para Whisper ({audio_size} bytes)")
            else:
                print(f"⚠️ OPENAI_API_KEY no configurada — Whisper no disponible")

            # OPCIÓN 2: VOSK (gratuito, offline — si modelo disponible)
            try:
                texto = _transcribir_con_vosk(audio_path)
                if texto:
                    print(f"✅ Vosk transcribió: '{texto}'")
                    return texto
                print(f"⚠️ Vosk retornó vacío")
            except Exception as vosk_error:
                print(f"⚠️ Vosk no disponible: {vosk_error}")
            
            # OPCIÓN 3: FALLBACK — no se pudo transcribir
            print("⚠️ Sin transcripción disponible - retornando None")
            return None
            
        finally:
            # Eliminar archivo temporal
            if os.path.exists(audio_path):
                os.remove(audio_path)
    
    except Exception as e:
        print(f"❌ Error en transcripción: {e}")
        return None


def _transcribir_con_vosk(audio_path):
    """
    Transcribe audio usando VOSK (gratuito, offline).
    
    Instalación requerida:
    - pip install vosk
    - Descargar modelo: https://alphacephei.com/vosk/models
    - Colocar en: models/vosk-model-small-es-0.42/
    """
    try:
        import json
        from vosk import Model, KaldiRecognizer
        from pydub import AudioSegment
        import wave
        
        # Ruta al modelo de Vosk (configurar en settings)
        model_path = getattr(settings, 'VOSK_MODEL_PATH', 'models/vosk-model-small-es-0.42')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo Vosk no encontrado en {model_path}")
        
        # Cargar modelo (se cachea automáticamente)
        model = Model(model_path)
        
        # Convertir audio a formato WAV 16kHz mono (requerido por Vosk)
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(16000).set_channels(1)

        # Guardar como WAV temporal — SIEMPRE en ruta distinta al original
        base, _ = os.path.splitext(audio_path)
        wav_path = base + '_vosk.wav'
        audio.export(wav_path, format='wav')

        try:
            # Transcribir usando wave module (más confiable)
            recognizer = KaldiRecognizer(model, 16000)

            wf = wave.open(wav_path, "rb")

            # Procesar por chunks
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                recognizer.AcceptWaveform(data)

            wf.close()

            # Obtener resultado final
            result = json.loads(recognizer.FinalResult())
            texto = result.get('text', '').strip()

            print(f"✅ Vosk transcribió: '{texto}'")
            return texto if texto else None
        finally:
            # Limpiar archivo WAV temporal (siempre, incluso en error)
            if os.path.exists(wav_path):
                os.remove(wav_path)

    except Exception as e:
        print(f"❌ Error Vosk: {e}")
        raise  # Re-lanzar para que el fallback funcione




_TWILIO_STATUS_CALLBACKS = frozenset({
    'queued', 'sending', 'sent', 'delivered', 'undelivered', 'failed', 'read',
})


def _twilio_post_plano(post_data) -> dict:
    if hasattr(post_data, 'keys'):
        return {k: post_data.get(k) for k in post_data.keys()}
    return dict(post_data)


def _es_status_callback_twilio(post_data) -> bool:
    message_status = (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').lower()
    return bool(message_status and message_status in _TWILIO_STATUS_CALLBACKS)


def _encolar_twilio_edu_si_async(post_data, *, reply_from_number: str | None = None) -> bool:
    """Encola webhook educativo en Celery si WEBHOOK_CELERY_ASYNC=true."""
    if not getattr(settings, 'WEBHOOK_CELERY_ASYNC', False):
        return False
    if _es_status_callback_twilio(post_data):
        return False
    from core.tasks import procesar_twilio_webhook_async

    plano = _twilio_post_plano(post_data)
    # Menú sandbox dual: el worker debe responder desde el mismo From.
    from_override = (reply_from_number or '').strip()
    if not from_override:
        try:
            from core.wa_reply_context import get_reply_from_override

            from_override = (get_reply_from_override() or '').strip()
        except Exception:
            from_override = ''
    if from_override:
        plano['_eki_reply_from'] = from_override

    procesar_twilio_webhook_async.delay(plano)
    logger.info("📤 Webhook educativo encolado en Celery | sid=%s", post_data.get('MessageSid', ''))
    return True


def _encolar_bot_comercial_si_async(post_data, *, forzar_canal: bool = False) -> bool:
    """Encola Nat (RAG/LLM) en Celery si NAT_WEBHOOK_CELERY_ASYNC=true."""
    if not getattr(settings, 'NAT_WEBHOOK_CELERY_ASYNC', False):
        return False
    if _es_status_callback_twilio(post_data):
        return False
    from core.tasks import procesar_bot_comercial_webhook_async

    try:
        procesar_bot_comercial_webhook_async.delay(
            _twilio_post_plano(post_data),
            forzar_canal=forzar_canal,
        )
    except Exception:
        logger.exception(
            "❌ No se pudo encolar Nat (Redis/Celery) | sid=%s — fallback síncrono",
            post_data.get('MessageSid', ''),
        )
        return False
    logger.info(
        "📤 Webhook Nat encolado en Celery | sid=%s | forzar=%s",
        post_data.get('MessageSid', ''),
        forzar_canal,
    )
    return True


def _sandbox_inbound_repetido(inbound) -> bool:
    """Meta reintenta si tardamos: el mismo wamid no debe responder ni gastar cupo dos veces."""
    sid = str(inbound.get('MessageSid') or '').strip()
    if not sid:
        return False
    try:
        from django.core.cache import cache

        if cache.add(f'sandbox_in:{sid}', 1, timeout=6 * 3600):
            return False
    except Exception:
        logger.exception('sandbox_dedupe_cache_fail')
        return False
    logger.info('sandbox_inbound_duplicado sid=%s', sid)
    return True


def _encolar_sandbox_si_async(inbound) -> bool:
    """Menú, agentes y cursos de la línea Meta en Celery si SANDBOX_CELERY_ASYNC=true."""
    if not getattr(settings, 'SANDBOX_CELERY_ASYNC', False):
        return False
    try:
        from core.tasks import procesar_sandbox_meta_async

        procesar_sandbox_meta_async.delay(dict(inbound))
    except Exception:
        logger.exception('sandbox_encolar_fail sid=%s — fallback síncrono', inbound.get('MessageSid', ''))
        return False
    return True


def _aplicar_sandbox_menu(data):
    """Menú agentes | cursos del sandbox Meta. No toca WABA Twilio de producción."""
    from core.sandbox_canal import (
        canal_sandbox_si_meta,
        es_inbound_twilio_http,
        sandbox_via_meta,
        to_es_sandbox,
    )
    from core.sandbox_menu import dispatch_sandbox_menu, sandbox_menu_enabled, sandbox_number
    from core.wa_reply_context import reply_from

    if (
        sandbox_menu_enabled()
        and sandbox_via_meta()
        and es_inbound_twilio_http(data)
        and to_es_sandbox(data)
    ):
        logger.info('sandbox_twilio_inbound_ignorado To=%s (canal=meta)', data.get('To', ''))
        return HttpResponse('OK')

    with canal_sandbox_si_meta():
        ruta = dispatch_sandbox_menu(data)
        if ruta is None:
            return None
        if ruta == 'handled':
            return HttpResponse('OK')
        if ruta == 'nat':
            from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook

            if not _encolar_bot_comercial_si_async(data, forzar_canal=True):
                _procesar_bot_comercial_twilio_webhook(data, forzar_canal=True)
            return HttpResponse('OK')
        if ruta == 'cursos':
            sb = sandbox_number()
            with reply_from(sb):
                if _encolar_twilio_edu_si_async(data, reply_from_number=sb):
                    return HttpResponse('OK')
                tw = _procesar_twilio_webhook(data)
                if isinstance(tw, HttpResponse):
                    return tw
            return HttpResponse('OK')
        return None


# ---------- Webhook para WhatsApp Cloud API ----------
@csrf_exempt
def whatsapp_webhook(request):
    """
    Webhook universal para WhatsApp (Meta + Twilio)
    GET: Verificación del token
    POST: Procesa mensajes entrantes de ambos proveedores
    """
    if request.method == 'GET':
        # Verificación para Meta WhatsApp
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        expected = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'eki_webhook_verify_token')
        if verify_token and expected and verify_token == expected:
            return HttpResponse(challenge)
        return HttpResponse('Forbidden', status=403)

    if request.method == 'POST':
        import sys
        print("🔵 WEBHOOK RECIBIÓ POST", flush=True)
        logger.info("🔵 WEBHOOK RECIBIÓ POST")

        # Raw body → firma Twilio (HMAC/compare_digest) antes de procesar inbound Twilio.
        # Meta Cloud API (JSON con entry) no usa X-Twilio-Signature.
        from core.twilio_webhook_security import (
            looks_like_meta_whatsapp_payload,
            validate_twilio_request,
        )
        raw_body = request.body
        if not looks_like_meta_whatsapp_payload(raw_body):
            denied = validate_twilio_request(request)
            if denied is not None:
                return denied

        def _es_destino_bot_comercial(data):
            from core.bot_comercial_routing import es_destino_bot_comercial
            return es_destino_bot_comercial(data)

        try:
            # Intentar parsear como JSON (Meta)
            payload = json.loads(request.body.decode('utf-8'))
            print(f"🔵 Payload (JSON): {payload}", flush=True)
            logger.info(f"🔵 Payload (JSON): {payload}")
            
            # Detectar si es Meta o Twilio
            if 'entry' in payload:
                logger.info("📍 Detectado: META WhatsApp")
                try:
                    from core.meta_waba import aplicar_eventos_plantilla

                    aplicar_eventos_plantilla(
                        payload,
                        raw_body,
                        request.META.get('HTTP_X_HUB_SIGNATURE_256', ''),
                    )
                except Exception:
                    logger.exception('meta_template_status_update_fail')
                from core.sandbox_canal import iter_mensajes_inbound_meta, sandbox_via_meta
                from core.sandbox_menu import es_destino_sandbox

                if sandbox_via_meta():
                    last_sb = None
                    sandbox_hit = False
                    for inbound in iter_mensajes_inbound_meta(payload):
                        if es_destino_sandbox(inbound):
                            sandbox_hit = True
                            if _sandbox_inbound_repetido(inbound):
                                continue
                            if _encolar_sandbox_si_async(inbound):
                                continue
                            last_sb = _aplicar_sandbox_menu(inbound)
                    if sandbox_hit:
                        if isinstance(last_sb, HttpResponse):
                            return last_sb
                        return HttpResponse('OK')
                _procesar_meta_webhook(payload)
            else:
                # Podría ser Twilio con JSON — intentar procesarlo como Twilio también
                print("⚠️ JSON recibido pero no es Meta — intentando como Twilio", flush=True)
                logger.info("⚠️ JSON recibido pero no es Meta, verificando si tiene datos Twilio")
                # Algunos webhooks de Twilio pueden llegar como JSON
                if 'Body' in payload or 'From' in payload or 'MessageStatus' in payload:
                    print("🔵 JSON con datos Twilio detectado — procesando", flush=True)
                    logger.info(
                        "🧪 Twilio JSON inbound | path=%s | from=%s | to=%s | sid=%s",
                        request.path,
                        payload.get('From', ''),
                        payload.get('To', ''),
                        payload.get('MessageSid', ''),
                    )
                    sb = _aplicar_sandbox_menu(payload)
                    if sb is not None:
                        return sb
                    if _es_destino_bot_comercial(payload):
                        logger.info("🧭 Router webhook: Twilio destino comercial/agro detectado (JSON)")
                        if not _encolar_bot_comercial_si_async(payload):
                            _procesar_bot_comercial_twilio_webhook(payload)
                    else:
                        logger.info("🧭 Router webhook: Twilio destino educativo detectado (JSON)")
                        if not _encolar_twilio_edu_si_async(payload):
                            _procesar_twilio_webhook(payload)
                else:
                    print("⚠️ JSON desconocido — ignorando", flush=True)
                return HttpResponse('OK')
                
        except json.JSONDecodeError:
            # Podría ser Twilio (form-data)
            print("🔵 Payload (Form-Data) - Probablemente Twilio", flush=True)
            print(f"POST keys: {list(request.POST.keys())}", flush=True)
            logger.info("🔵 Payload (Form-Data) - Probablemente Twilio")
            logger.info(
                "🧪 Twilio Form inbound | path=%s | from=%s | to=%s | sid=%s",
                request.path,
                request.POST.get('From', ''),
                request.POST.get('To', ''),
                request.POST.get('MessageSid', ''),
            )
            sb = _aplicar_sandbox_menu(request.POST)
            if sb is not None:
                return sb
            if _es_destino_bot_comercial(request.POST):
                logger.info("🧭 Router webhook: Twilio destino comercial/agro detectado (Form-Data)")
                if not _encolar_bot_comercial_si_async(request.POST):
                    _procesar_bot_comercial_twilio_webhook(request.POST)
                twilio_result = None
            else:
                logger.info("🧭 Router webhook: Twilio destino educativo detectado (Form-Data)")
                if _encolar_twilio_edu_si_async(request.POST):
                    twilio_result = None
                else:
                    twilio_result = _procesar_twilio_webhook(request.POST)
            # Si _procesar_twilio_webhook devuelve TwiML HttpResponse, retornarlo
            if isinstance(twilio_result, HttpResponse):
                return twilio_result
        
        except Exception as e:
            print(f"❌ Error en webhook: {str(e)}", flush=True)
            logger.error(f"❌ Error en webhook: {str(e)}")
            import traceback
            traceback.print_exc()
            return HttpResponse('Error', status=500)

        return HttpResponse('OK')


def _cliente_en_ventana(cliente, campo_habilitar, campo_inicio, campo_fin):
    """Evalúa si una funcionalidad está habilitada para un cliente según ventana de fechas."""
    if not cliente:
        return True
    if not getattr(cliente, campo_habilitar, False):
        return False

    hoy = timezone.localdate()
    inicio = getattr(cliente, campo_inicio, None)
    fin = getattr(cliente, campo_fin, None)

    if inicio and hoy < inicio:
        return False
    if fin and hoy > fin:
        return False
    return True


def _cliente_habilita_pregunta_abierta_final(cliente):
    return _cliente_en_ventana(
        cliente,
        'habilitar_pregunta_abierta_final',
        'fecha_inicio_pregunta_abierta_final',
        'fecha_fin_pregunta_abierta_final',
    )


def _cliente_habilita_proximidad(cliente):
    from core.empleabilidad_pausa import empleabilidad_en_pausa

    # PAUSA: radar/empleabilidad territorial fuera de circulación.
    if empleabilidad_en_pausa():
        return False
    habilitado_legacy = _cliente_en_ventana(
        cliente,
        'habilitar_gamificacion_proximidad',
        'fecha_inicio_gamificacion_proximidad',
        'fecha_fin_gamificacion_proximidad',
    )
    return bool(habilitado_legacy or (cliente and getattr(cliente, 'empleabilidad_exploracion_activa', False)))


# --- Nat / bot comercial: lógica en core.bot_comercial.webhook ---
from core.bot_comercial.webhook import (  # noqa: E402
    _actualizar_sesion_comercial,
    _bot_comercial_diagnosticar_imagen,
    _bot_comercial_historial_reciente,
    _bot_comercial_respuesta_catalogo,
    _bot_comercial_sin_contexto_natural,
    _contexto_fallback_desde_documentos,
    _contexto_fallback_web_agro,
    _obtener_o_crear_sesion_comercial,
    _procesar_bot_comercial_twilio_webhook,
)


@csrf_exempt
def bot_comercial_webhook(request):
    """Webhook dedicado para el número de WhatsApp del bot comercial."""
    if request.method != 'POST':
        return HttpResponse('Method Not Allowed', status=405)

    from core.twilio_webhook_security import validate_twilio_request

    denied = validate_twilio_request(request)
    if denied is not None:
        return denied

    try:
        try:
            payload = json.loads(request.body.decode('utf-8'))
            sb = _aplicar_sandbox_menu(payload)
            if sb is not None:
                return sb
            if not _encolar_bot_comercial_si_async(payload, forzar_canal=True):
                _procesar_bot_comercial_twilio_webhook(payload, forzar_canal=True)
        except json.JSONDecodeError:
            sb = _aplicar_sandbox_menu(request.POST)
            if sb is not None:
                return sb
            if not _encolar_bot_comercial_si_async(request.POST, forzar_canal=True):
                _procesar_bot_comercial_twilio_webhook(request.POST, forzar_canal=True)
        return HttpResponse('OK')
    except Exception as e:
        logger.error(f"❌ Error webhook bot comercial: {e}")
        return HttpResponse('Error', status=500)


def _escape_twiml(text):
    """Escapa caracteres especiales para TwiML XML."""
    if not text:
        return text
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def _reenviar_media_fallida_como_enlace(log, error_code: str = '') -> None:
    """
    Ante 63019/63021/63005: reintento automático del mismo MediaUrl (1–2 veces).
    No envía links S3 en el cuerpo. Si agota reintentos, queda estado fallido
    y el productor puede pedir *reenvía video*.
    """
    from ..media_entrega import reintentar_media_desde_log
    from ..twilio_media import es_error_media_twilio

    if not es_error_media_twilio(error_code):
        return
    ok = reintentar_media_desde_log(log, error_code)
    if not ok:
        logger.warning(
            '📎 Media undelivered/failed tras reintento(s) | sid=%s code=%s tel=%s',
            getattr(log, 'mensaje_id', ''),
            error_code,
            getattr(log, 'telefono', ''),
        )


def _registrar_estado_twilio_callback(post_data):
    """
    Actualiza estado de WhatsappLog (SENT) con callbacks de Twilio.
    Permite métricas de entregado/abierto/fallido por mensaje.
    Ante 63019/63021/63005 solo registra el fallo (no envía links S3).
    """
    try:
        sid = (
            post_data.get('MessageSid')
            or post_data.get('SmsSid')
            or post_data.get('message_sid')
            or ''
        )
        status_raw = (
            post_data.get('MessageStatus')
            or post_data.get('SmsStatus')
            or post_data.get('status')
            or ''
        )
        status = str(status_raw).strip().upper()
        error_code = str(
            post_data.get('ErrorCode') or post_data.get('error_code') or ''
        ).strip()
        error_message = str(
            post_data.get('ErrorMessage') or post_data.get('error_message') or ''
        ).strip()

        if not sid or not status:
            return

        # Tomar el último envío con este SID para no tocar INCOMING.
        log = (
            WhatsappLog.objects.filter(mensaje_id=sid, tipo='SENT')
            .order_by('-fecha')
            .first()
        )
        if log:
            campos = []
            if log.estado != status:
                log.estado = status
                campos.append('estado')
            detalle = ' '.join(x for x in (error_code, error_message) if x).strip()
            if detalle and detalle != (log.error_detalle or '').strip():
                # Conservar marcador FALLBACK_ENLACE si ya existía.
                prev = log.error_detalle or ''
                if 'FALLBACK_ENLACE' in prev and 'FALLBACK_ENLACE' not in detalle:
                    detalle = f'{detalle} | FALLBACK_ENLACE'
                log.error_detalle = detalle[:2000]
                campos.append('error_detalle')
            if campos:
                log.save(update_fields=campos)
            if status in ('UNDELIVERED', 'FAILED') and error_code:
                _reenviar_media_fallida_como_enlace(log, error_code)
            # Telemetría entrega media (Centro de Éxito).
            try:
                from core.models import Estudiante, EstudianteEventoAprendizaje
                from core.telemetria import registrar_evento
                from core.utils_telefono import variantes_telefono

                est = log.estudiante
                if est is None and log.telefono:
                    for v in variantes_telefono(log.telefono):
                        est = Estudiante.objects.filter(telefono=v).first()
                        if est:
                            break
                if est:
                    tipo_ev = (
                        EstudianteEventoAprendizaje.TIPO_MEDIA_FALLIDA
                        if status in ('UNDELIVERED', 'FAILED')
                        else EstudianteEventoAprendizaje.TIPO_MEDIA_ENTREGADA
                        if status in ('DELIVERED', 'READ', 'RECEIVED')
                        else None
                    )
                    if tipo_ev:
                        registrar_evento(
                            tipo=tipo_ev,
                            estudiante=est,
                            metadata={
                                'twilio_sid': sid,
                                'status': status,
                                'error_code': error_code,
                                'whatsapp_log_id': log.pk,
                            },
                        )
            except Exception as te:
                logger.debug('telemetria status twilio: %s', te)
            return

        # Fallback para no perder trazabilidad de callbacks huérfanos.
        WhatsappLog.objects.create(
            telefono='desconocido',
            mensaje=f'[STATUS_CALLBACK:{status}]',
            mensaje_id=sid,
            tipo='SENT',
            estado=status,
            error_detalle=(
                f"{' '.join(x for x in (error_code, error_message) if x)} | "
                'Callback Twilio sin log SENT previo.'
            ).strip(' |'),
        )
    except Exception as e:
        logger.warning(f"⚠️ No se pudo registrar callback Twilio: {e}")


def _twilio_max_body_chars() -> int:
    """Retorna límite seguro para cuerpo de mensajes Twilio WhatsApp."""
    try:
        valor = int(getattr(settings, 'TWILIO_MAX_BODY_CHARS', 1500) or 1500)
    except (TypeError, ValueError):
        valor = 1500

    if valor < 200 or valor > 1590:
        return 1500
    return valor


def _segmentar_texto_twilio(texto: str, max_chars: int = None) -> list:
    """Divide texto en segmentos compatibles con límite de Twilio."""
    texto = str(texto or '').strip()
    if not texto:
        return ['']

    limite = max_chars or _twilio_max_body_chars()

    try:
        from ..response_templates import dividir_contenido_seguro
        chunks = dividir_contenido_seguro(texto, max_chars=limite)
        if chunks:
            return chunks
    except Exception:
        pass

    # Fallback simple por longitud si la utilidad no está disponible.
    return [texto[i:i + limite] for i in range(0, len(texto), limite)]


def youtube_hace_solo_enlace_en_texto(url: str) -> bool:
    """True si la URL es página/embed (YouTube/Drive/…), no archivo directo adjuntarle por Twilio."""
    from ..twilio_media import url_no_es_media_directo

    return url_no_es_media_directo(url)


def _enviar_mensaje_twilio_segmentado(client, from_number: str, to_number: str, body: str, media_url: str = None) -> list:
    """Envía mensaje Twilio en segmentos seguros y devuelve [(sid, texto_enviado), ...]."""
    try:
        from core.sandbox_canal import _MetaSid, enviar_meta, sandbox_meta_activo

        if sandbox_meta_activo():
            result = enviar_meta(to_number, body or '', media_url=media_url)
            # Los llamadores leen mensaje.sid como en Twilio.
            sid = _MetaSid(result.get('mensaje_id') or '')
            return [(sid, body or '')] if result.get('success') else []
    except Exception:
        logger.exception('sandbox_meta_intercept_segmentado')

    from ..twilio_media import (
        cuerpo_con_enlace_archivo,
        es_error_media_twilio,
        es_url_s3_o_firmada,
        normalizar_media_url_s3,
        preparar_url_media_whatsapp,
        url_no_es_media_directo,
    )

    body_limpio = str(body or '').strip()
    media_limpia = normalizar_media_url_s3(media_url)
    # Páginas (YouTube/Drive): no adjuntar; solo enlace externo (nunca S3).
    if media_limpia and url_no_es_media_directo(media_limpia):
        if not es_url_s3_o_firmada(media_limpia):
            body_limpio = cuerpo_con_enlace_archivo(body_limpio or TWILIO_CAPTION_ADJUNTO, media_limpia)
        else:
            logger.warning('📎 URL página apunta a S3; no se envía en texto | %s', media_limpia[:120])
        media_limpia = None
    elif media_limpia:
        try:
            preparada = preparar_url_media_whatsapp(media_limpia)
            # None = video ilegible: no adjuntar y no enviar link S3.
            if preparada is None:
                logger.warning(
                    '📎 Video no adjuntable; se omite media (sin enlace S3) | %s',
                    media_limpia[:120],
                )
                media_limpia = None
            else:
                media_limpia = preparada or media_limpia
        except Exception as prep_err:
            logger.warning('📎 preparar_url_media_whatsapp falló (se envía original): %s', prep_err)
    # Adjunto sin texto: va solo, sin relleno genérico.
    # Sin media y sin texto útil: no spamear al estudiante.
    if not body_limpio and not media_limpia:
        return []

    enviados = []
    from_limpio = str(from_number or '').strip()
    to_limpio = str(to_number or '').strip()
    status_cb = str(getattr(settings, 'TWILIO_STATUS_CALLBACK_URL', '') or '').strip()

    segmentos = _segmentar_texto_twilio(body_limpio)

    for idx, segmento in enumerate(segmentos):
        seg_txt = (segmento or '').strip()
        params = {
            'from_': from_limpio,
            'to': to_limpio,
        }
        # Solo llega vacío cuando el adjunto va sin texto: Twilio lo manda solo.
        if seg_txt:
            params['body'] = seg_txt
        if status_cb:
            params['status_callback'] = status_cb

        # Adjuntar media solo en el primer segmento (Twilio descarga la URL; el alumno no ve el link).
        if media_limpia and idx == 0:
            params['media_url'] = [media_limpia]

        try:
            mensaje = client.messages.create(**params)
        except Exception as media_err:
            if es_error_media_twilio(media_err) and media_limpia and idx == 0:
                # Sin fallback a link S3: solo caption/texto.
                params.pop('media_url', None)
                if not (params.get('body') or '').strip():
                    params['body'] = TWILIO_CAPTION_ADJUNTO
                logger.warning(
                    '📎 Media Twilio falló en create (%s); reintento solo texto (sin URL S3) | url=%s',
                    media_err,
                    media_limpia[:120],
                )
                mensaje = client.messages.create(**params)
            else:
                raise

        enviados.append((mensaje, params.get('body', '') or seg_txt))

    return enviados


def _haversine_metros(lat1, lon1, lat2, lon2):
    """Distancia Haversine en metros."""
    radio_tierra = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radio_tierra * c


def _mensaje_bloqueo_drip_view(fecha_desbloqueo):
    from ..response_templates import _mensaje_bloqueo_drip
    return _mensaje_bloqueo_drip(fecha_desbloqueo)


def _activar_radar_empleabilidad_si_aplica(estudiante):
    from django.db.models import Q
    from core.empleabilidad_pausa import empleabilidad_en_pausa
    from ..models import AliadoEmpleabilidad

    # PAUSA PRODUCTO: no desbloquear radar Subachoque.
    if empleabilidad_en_pausa():
        return False

    if not _cliente_habilita_proximidad(estudiante.cliente):
        return False

    if estudiante.cliente_id:
        hay_aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).filter(
            Q(cliente__isnull=True) | Q(cliente=estudiante.cliente)
        ).exists()
    else:
        hay_aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).exists()

    if not hay_aliados:
        return False

    ctx = estudiante.contexto_temporal or {}
    ctx['radar_empleabilidad_activo'] = True
    ctx['empleabilidad_habilitado_en'] = timezone.now().isoformat()
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['contexto_temporal'])
    return True


def _pregunta_abierta_final_pendiente(estudiante, progreso):
    from ..models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal

    preguntas_qs = PreguntaAbiertaFinalCurso.objects.filter(
        curso=progreso.curso,
        activa=True
    ).order_by('orden', 'id')

    if not preguntas_qs.exists():
        return None

    cliente_habilita = _cliente_habilita_pregunta_abierta_final(estudiante.cliente)
    curso_habilita = bool(getattr(progreso.curso, 'habilitar_pregunta_abierta_final', False))
    if not (cliente_habilita and curso_habilita):
        logger.info(
            "⚠️ Fallback pregunta abierta final por configuración | estudiante_id=%s | curso_id=%s | cliente_habilita=%s | curso_habilita=%s",
            estudiante.id,
            progreso.curso.id,
            cliente_habilita,
            curso_habilita,
        )

    preguntas = list(preguntas_qs[:3])

    for pregunta in preguntas:
        existe = RespuestaAbiertaFinal.objects.filter(
            pregunta=pregunta,
            estudiante=estudiante
        ).exists()
        if not existe:
            return pregunta

    return None


def _radar_msg_si_aplica(estudiante):
    """Copy de radar solo si la pausa está off y hay aliados. No envía Subachoque en pausa."""
    from core.empleabilidad_pausa import mensaje_radar_desbloqueado

    if not _activar_radar_empleabilidad_si_aplica(estudiante):
        return ''
    return mensaje_radar_desbloqueado()


def _procesar_ubicacion_empleabilidad(estudiante, latitud, longitud):
    """
    Evalúa proximidad del estudiante a aliados activos y construye respuesta.
    Guarda aliado objetivo en contexto para validación de código secreto.
    """
    from django.db.models import Q
    from core.empleabilidad_pausa import empleabilidad_en_pausa
    from ..models import AliadoEmpleabilidad, MisionEmpleabilidad

    # PAUSA PRODUCTO: no crear misiones ni pedir código de aliado.
    if empleabilidad_en_pausa():
        return ''

    if not _cliente_habilita_proximidad(estudiante.cliente):
        return (
            "📍 El radar de empleabilidad por ubicación no está activo para tu organización en esta fecha. "
            "Si lo esperabas, escribe *ayuda* para que el equipo valide tu acceso."
        )

    if estudiante.cliente_id:
        aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).filter(
            Q(cliente__isnull=True) | Q(cliente=estudiante.cliente)
        )
    else:
        aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True)

    aliados = list(aliados)
    if not aliados:
        return "📍 En este momento no hay vacantes activas de aliados en tu zona. Te avisaremos cuando se habiliten."

    cliente_cfg = estudiante.cliente
    radio_metros = int(getattr(cliente_cfg, 'empleabilidad_radio_metros', 800) or 800)
    max_misiones_dia = int(getattr(cliente_cfg, 'empleabilidad_max_misiones_dia', 3) or 3)
    hoy = timezone.localdate()
    misiones_hoy = MisionEmpleabilidad.objects.filter(
        estudiante=estudiante,
        fecha_descubierta__date=hoy,
    ).exclude(estado='cancelada').count()
    if misiones_hoy >= max_misiones_dia:
        return (
            f"📌 Ya completaste tu límite diario de exploración ({max_misiones_dia} misiones).\n"
            "Vuelve mañana para descubrir nuevas oportunidades."
        )

    mejor = None
    mejor_dist = None
    for aliado in aliados:
        dist = _haversine_metros(latitud, longitud, aliado.latitud, aliado.longitud)
        if mejor_dist is None or dist < mejor_dist:
            mejor_dist = dist
            mejor = aliado

    if not mejor:
        return "No pude procesar tu ubicación en este momento. Inténtalo nuevamente."

    if mejor_dist > radio_metros:
        return (
            "📍 Aún no hay oportunidades dentro de tu radio de exploración actual.\n\n"
            f"Distancia más cercana a {mejor.nombre_empresa}: *{int(round(mejor_dist))} m*.\n"
            f"Radio activo de tu organización: *{int(radio_metros)} m*."
        )

    mision = MisionEmpleabilidad.objects.create(
        cliente=estudiante.cliente,
        estudiante=estudiante,
        aliado=mejor,
        estado='descubierta',
        latitud=latitud,
        longitud=longitud,
        distancia_metros=round(mejor_dist, 1),
        metadata={'fuente': 'whatsapp_location'},
    )

    ctx = estudiante.contexto_temporal or {}
    ctx['radar_empleabilidad_activo'] = True
    ctx['aliado_empleabilidad_objetivo_id'] = mejor.id
    ctx['mision_empleabilidad_id'] = mision.id
    ctx['distancia_aliado_m'] = round(mejor_dist, 1)
    estudiante.contexto_temporal = ctx
    estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

    if mejor_dist <= 100:
        return (
            f"🎯 *¡Estás a {int(round(mejor_dist))} metros de {mejor.nombre_empresa}!*\n\n"
            "Acércate a la entrada y envía el *código secreto* que verás en la puerta."
        )

    sector = mejor.indicacion_sector or "del parque principal"
    return (
        "📍 Aún estás lejos de nuestras empresas aliadas.\n\n"
        f"Vas por buen camino. Acércate al sector *{sector}* y vuelve a enviarme tu ubicación.\n"
        f"Distancia aproximada actual a {mejor.nombre_empresa}: *{int(round(mejor_dist))} m*."
    )


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


def _procesar_twilio_webhook(post_data):
    """Procesa webhooks de Twilio WhatsApp (también inbound canónico sandbox Meta)."""
    from core.sandbox_canal import activar_sandbox_meta_si_inbound

    with activar_sandbox_meta_si_inbound(post_data):
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
        if estado_chat == 'ESPERANDO_CEDULA':
            # Limpiar input del usuario
            cedula_input = re.sub(r'[\s\.\-]', '', msg_body.strip())
            msg_lower_cedula = msg_body.strip().lower()
            
            # Detectar "ayuda" → crear ticket de soporte
            if msg_lower_cedula in ['ayuda', 'help', 'soporte']:
                from ..models import SolicitudSoporte
                solicitud = SolicitudSoporte.objects.create(
                    estudiante=estudiante,
                    mensaje_original=f"Ayuda en verificación de cédula - no coincide con registros",
                    keyword_usada='ayuda_cedula',
                    asunto='Problema con verificación de cédula',
                    prioridad='media'
                )
                texto_respuesta = (
                    f"🆘 *Ticket de Soporte #{solicitud.id}*\n\n"
                    f"Hola {estudiante.nombre}, hemos registrado tu solicitud.\n\n"
                    "📝 Un asesor revisará tu caso y te contactará pronto.\n"
                    "🕐 *Tiempo de respuesta:* menos de 24 horas.\n\n"
                    "Si recuerdas tu cédula, puedes intentar de nuevo escribiéndola aquí."
                )
            # Comparar con la cédula sanitizada en BD
            elif cedula_input == estudiante.cedula:
                estudiante.estado_chat = 'CONFIRMANDO_DATOS'
                estudiante.save()
                
                # Enviar confirmación con datos + botones (5 variables)
                org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                from ..whatsapp_service import enviar_confirmacion_datos
                resultado = enviar_confirmacion_datos(
                    msg_from,
                    estudiante.nombre,
                    f"{estudiante.tipo_documento} {estudiante.cedula}",
                    org_nombre,
                    edad=estudiante.edad,
                    municipio=estudiante.municipio,
                )
                if resultado.get('success'):
                    return  # Template enviado
                
                # Fallback texto plano
                texto_respuesta = (
                    "✅ *¡Cédula verificada!*\n\n"
                    "Tus datos registrados:\n\n"
                    f"👤 *Nombre:* {estudiante.nombre}\n"
                    f"🆔 *Documento:* {estudiante.tipo_documento} {estudiante.cedula}\n"
                    f"📍 *Municipio:* {estudiante.municipio or 'No registrado'}\n"
                    f"🏢 *Organización:* {org_nombre}\n"
                    f"🎂 *Edad:* {estudiante.edad or 'No registrada'}\n"
                    f"👫 *Género:* {estudiante.get_genero_display() if estudiante.genero else 'No registrado'}\n\n"
                    "*¿Tus datos están correctos?*\n\n"
                    "👉 Escribe *Sí* si todo está bien\n"
                    "👉 Escribe *No* si hay un error"
                )
            else:
                texto_respuesta = (
                    "❌ *Cédula no coincide*\n\n"
                    "El número que ingresaste no coincide con "
                    "nuestros registros.\n\n"
                    "Por favor verifica y escribe tu cédula nuevamente "
                    "(solo números, sin puntos ni espacios).\n\n"
                    "👉 Ejemplo: 1234567890\n\n"
                    "Si crees que hay un error, escribe *ayuda*"
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
                logger.error(f"❌ Error enviando validación 2FA: {e}")
                import traceback; traceback.print_exc()
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
                            # Get agent names: Cliente > Curso > defaults
                            cliente_obj = estudiante.cliente
                            nombre_tutor = (
                                (cliente_obj.nombre_agente_tutor if cliente_obj and hasattr(cliente_obj, 'nombre_agente_tutor') and cliente_obj.nombre_agente_tutor else '') or
                                curso.nombre_agente_tutor or 'Claudia'
                            )
                            nombre_asistente = (
                                (cliente_obj.nombre_agente_asistente if cliente_obj and hasattr(cliente_obj, 'nombre_agente_asistente') and cliente_obj.nombre_agente_asistente else '') or
                                curso.nombre_agente_asistente or 'Darío'
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
                from twilio.rest import Client as TwilioClient
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                client_tw = TwilioClient(account_sid, auth_token)
                destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                
                # Handle multi-message (process [MULTI_MSG]/[SEP]/[MEDIA:] markers)
                if texto_respuesta.startswith('[MULTI_MSG]'):
                    import re as re_conf
                    partes_conf = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                    for parte_c in partes_conf:
                        if not parte_c.strip():
                            continue
                        parte_texto_c = parte_c.strip()
                        # [DELAY:N] — pausa intencional para que WhatsApp entregue videos
                        delay_m_c = re_conf.match(r'^\[DELAY:(\d+)\]$', parte_texto_c)
                        if delay_m_c:
                            import time; time.sleep(int(delay_m_c.group(1)))
                            continue
                        # Detectar Content Template → enviar como template, NO como texto
                        if parte_texto_c.startswith('[SEND_TEMPLATE:'):
                            tmpl_m_c = re_conf.match(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]', parte_texto_c)
                            if tmpl_m_c:
                                from ..whatsapp_service import enviar_template_twilio
                                tel_limpio_t = msg_from.replace('whatsapp:', '').replace('+', '')
                                enviar_template_twilio(tel_limpio_t, tmpl_m_c.group(1))
                            import time; time.sleep(0.5)
                            continue
                        parte_media_c = None
                        media_m_c = re_conf.search(r'\[MEDIA:(.*?)\]', parte_texto_c)
                        if media_m_c:
                            parte_media_c = (media_m_c.group(1) or '').strip()
                            parte_texto_c = parte_texto_c.replace(media_m_c.group(0), '').strip()
                        enviados_c = _enviar_mensaje_twilio_segmentado(
                            client=client_tw,
                            from_number=str(twilio_number).strip(),
                            to_number=str(destino).strip(),
                            body=parte_texto_c,
                            media_url=parte_media_c,
                        )
                        import time; time.sleep(0.5)
                        from ..twilio_media import mensaje_log_con_media
                        for seg_i, (msg_sent, texto_env) in enumerate(enviados_c, start=1):
                            WhatsappLog.objects.create(
                                telefono=telefono_limpio,
                                mensaje=mensaje_log_con_media(
                                    texto_env or parte_texto_c,
                                    parte_media_c if seg_i == 1 else None,
                                )[:1500],
                                mensaje_id=getattr(msg_sent, 'sid', None),
                                tipo='SENT',
                            )
                else:
                    client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
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
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    # Check for multi-message or media markers
                    if texto_respuesta.startswith('[MULTI_MSG]'):
                        partes = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                        for parte in partes:
                            if not parte.strip():
                                continue
                            import re as re_multi
                            parte_texto = parte.strip()
                            # [DELAY:N] — pausa intencional para entrega de videos
                            delay_m = re_multi.match(r'^\[DELAY:(\d+)\]$', parte_texto)
                            if delay_m:
                                import time; time.sleep(int(delay_m.group(1)))
                                continue
                            # Detectar Content Template
                            if parte_texto.startswith('[SEND_TEMPLATE:'):
                                tmpl_m = re_multi.match(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]', parte_texto)
                                if tmpl_m:
                                    from ..whatsapp_service import enviar_template_twilio
                                    tel_limpio_t = msg_from.replace('whatsapp:', '').replace('+', '')
                                    enviar_template_twilio(tel_limpio_t, tmpl_m.group(1))
                                import time; time.sleep(0.5)
                                continue
                            parte_media = None
                            media_m = re_multi.search(r'\[MEDIA:(.*?)\]', parte_texto)
                            if media_m:
                                parte_media = media_m.group(1).strip()
                                parte_texto = parte_texto.replace(media_m.group(0), '').strip()
                            _enviar_mensaje_twilio_segmentado(
                                client=client_tw,
                                from_number=str(twilio_number).strip(),
                                to_number=str(destino).strip(),
                                body=parte_texto,
                                media_url=parte_media,
                            )
                            import time; time.sleep(0.5)
                    else:
                        media_url_sel = None
                        import re as re_sel
                        media_m = re_sel.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
                        if media_m:
                            media_url_sel = media_m.group(1).strip()
                            texto_respuesta = texto_respuesta.replace(media_m.group(0), '').strip()
                        _enviar_mensaje_twilio_segmentado(
                            client=client_tw,
                            from_number=str(twilio_number).strip(),
                            to_number=str(destino).strip(),
                            body=texto_respuesta,
                            media_url=media_url_sel,
                        )
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta[:500], tipo='SENT')
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
                # 🆘 PQRS / ayuda — cede a evaluación/agentes; no duplicar tickets
                try:
                    from ..pqrs_agent import (
                        intentar_procesar_seguimiento_pqrs_whatsapp,
                        mensaje_activa_soporte,
                        mensaje_es_solo_ayuda,
                        obtener_ticket_pqrs_abierto,
                        pedagogia_tiene_prioridad,
                        respuesta_ayuda_con_ticket_abierto,
                    )
                    from ..security_handler import procesar_solicitud_soporte

                    _resp_pqrs_gate = None
                    if not pedagogia_tiene_prioridad(estudiante):
                        if mensaje_activa_soporte(msg_body):
                            _ticket_abierto = obtener_ticket_pqrs_abierto(estudiante)
                            if _ticket_abierto:
                                if mensaje_es_solo_ayuda(msg_body):
                                    _resp_pqrs_gate = respuesta_ayuda_con_ticket_abierto(
                                        estudiante, msg_body,
                                    )
                                else:
                                    # ayuda + detalle con ticket abierto → seguimiento, no 2.º ticket
                                    _resp_pqrs_gate = intentar_procesar_seguimiento_pqrs_whatsapp(
                                        estudiante, msg_body,
                                    )
                            else:
                                _resp_pqrs_gate = procesar_solicitud_soporte(
                                    estudiante, msg_body, 'curso_ayuda',
                                )
                        else:
                            _resp_pqrs_gate = intentar_procesar_seguimiento_pqrs_whatsapp(
                                estudiante, msg_body,
                            )

                    if _resp_pqrs_gate:
                        try:
                            from twilio.rest import Client as TwilioClient

                            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                            twilio_number = getattr(
                                settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806',
                            )
                            client_tw = TwilioClient(account_sid, auth_token)
                            destino = (
                                f'whatsapp:{msg_from}'
                                if not msg_from.startswith('whatsapp:')
                                else msg_from
                            )
                            client_tw.messages.create(
                                body=_resp_pqrs_gate,
                                from_=str(twilio_number).strip(),
                                to=str(destino).strip(),
                            )
                            WhatsappLog.objects.create(
                                telefono=telefono_limpio,
                                mensaje=_resp_pqrs_gate[:500],
                                tipo='SENT',
                            )
                        except Exception as e:
                            logger.error('❌ Error enviando PQRS/ayuda en gate curso: %s', e)
                        return
                except Exception:
                    logger.exception('PQRS gate curso omitido')

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

                # 📚 Paso módulo: evaluación / reto — antes del gate "solo listo" (A, texto libre, etc.)
                if estado_chat == 'ACTIVO':
                    from ..module_steps import procesar_respuesta_evaluacion_paso
                    from ..models import ProgresoEstudiante

                    _prog_eval = (
                        ProgresoEstudiante.objects.filter(
                            estudiante=estudiante,
                            completado=False,
                        )
                        .order_by('-fecha_inicio')
                        .first()
                    )
                    _ctx_eval = estudiante.contexto_temporal or {}
                    _fid_eval = _ctx_eval.get('curso_activo_id')
                    if (
                        _fid_eval
                        and _prog_eval
                        and _prog_eval.curso_id != int(_fid_eval)
                    ):
                        _prog_eval = (
                            ProgresoEstudiante.objects.filter(
                                estudiante=estudiante,
                                completado=False,
                                curso_id=int(_fid_eval),
                            ).first()
                            or _prog_eval
                        )
                    if _prog_eval:
                        _resp_paso = procesar_respuesta_evaluacion_paso(
                            estudiante, _prog_eval, msg_body
                        )
                        if _resp_paso is not None:
                            logger.info(
                                "📚 [pasos] respuesta evaluación procesada en webhook | est=%s",
                                estudiante.id,
                            )
                            try:
                                from twilio.rest import Client as TwilioClient
                                import re as _re_paso

                                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                                twilio_number = getattr(
                                    settings,
                                    'TWILIO_PHONE_NUMBER',
                                    'whatsapp:+573202948806',
                                )
                                client_tw = TwilioClient(account_sid, auth_token)
                                destino = (
                                    f'whatsapp:{msg_from}'
                                    if not msg_from.startswith('whatsapp:')
                                    else msg_from
                                )
                                twilio_from = str(twilio_number).strip()
                                destino_st = str(destino).strip()

                                def _log_twilio_segments_pasos(mensajes_enviados, parte_texto, parte_media):
                                    for _seg_idx, (mensaje, texto_enviado) in enumerate(
                                        mensajes_enviados, start=1
                                    ):
                                        texto_log = texto_enviado or parte_texto or (
                                            f'[MEDIA:{parte_media}]' if parte_media else ''
                                        )
                                        WhatsappLog.objects.create(
                                            telefono=telefono_limpio,
                                            mensaje=texto_log[:1500],
                                            mensaje_id=mensaje.sid,
                                            tipo='SENT',
                                        )

                                if _resp_paso.startswith('[MULTI_MSG]'):
                                    partes = _resp_paso.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                                    for parte in partes:
                                        if not parte.strip():
                                            continue
                                        parte_texto = parte.strip()
                                        delay_m = _re_paso.match(
                                            r'^\[DELAY:(\d+)\]$', parte_texto
                                        )
                                        if delay_m:
                                            import time as _time_p

                                            _time_p.sleep(int(delay_m.group(1)))
                                            continue
                                        parte_media = None
                                        if '[MEDIA:' in parte_texto:
                                            mm = _re_paso.search(r'\[MEDIA:(.*?)\]', parte_texto)
                                            if mm:
                                                parte_media = (mm.group(1) or '').strip()
                                                parte_texto = parte_texto.replace(
                                                    mm.group(0), ''
                                                ).strip()
                                                if parte_media and youtube_hace_solo_enlace_en_texto(
                                                    parte_media
                                                ):
                                                    logger.warning(
                                                        '📎 [pasos] URL parece YouTube (no MP4 directo) | est=%s',
                                                        estudiante.id,
                                                    )
                                        enviados_p = _enviar_mensaje_twilio_segmentado(
                                            client=client_tw,
                                            from_number=twilio_from,
                                            to_number=destino_st,
                                            body=parte_texto,
                                            media_url=parte_media,
                                        )
                                        _log_twilio_segments_pasos(enviados_p, parte_texto, parte_media)
                                        import time as _time_p

                                        _time_p.sleep(0.5)
                                else:
                                    parte_media = None
                                    parte_texto = (_resp_paso or '').strip()
                                    if '[MEDIA:' in parte_texto:
                                        mm = _re_paso.search(r'\[MEDIA:(.*?)\]', parte_texto)
                                        if mm:
                                            parte_media = (mm.group(1) or '').strip()
                                            parte_texto = parte_texto.replace(
                                                mm.group(0), ''
                                            ).strip()
                                    enviados_p = _enviar_mensaje_twilio_segmentado(
                                        client=client_tw,
                                        from_number=twilio_from,
                                        to_number=destino_st,
                                        body=parte_texto,
                                        media_url=parte_media,
                                    )
                                    _log_twilio_segments_pasos(enviados_p, parte_texto, parte_media)
                            except Exception as e:
                                logger.error(f"❌ Error enviando respuesta paso módulo: {e}", exc_info=True)
                            return

                keywords_corregir_curso = [
                    '4', 'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
                    'me equivoqué', 'me equivoque', 'editar datos', 'modificar datos', 'modificar',
                    'datos incorrectos', 'mis datos', 'actualizar datos'
                ]

                if msg_lower in keywords_corregir_curso:
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

                if not _mensaje_indica_listo(msg_body):
                    if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                        texto_respuesta = "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo o escríbeme. Para avanzar escribe *listo* o *continuar*."
                    else:
                        texto_respuesta = "No entendí. Si quieres avanzar de módulo escribe *listo* o *continuar*. Si necesitas ayuda, escribe *ayuda*."
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
                                            "Escribe *listo* para registrar tu avance y seguir 👇"
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
                            "Si acabas de reportar un problema, cuando quieras retomar escribe *listo* o *menú*."
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
        pqrs_atendido = False
        respuesta_pqrs = None
        try:
            from ..pqrs_agent import (
                intentar_procesar_seguimiento_pqrs_whatsapp,
                pedagogia_tiene_prioridad,
            )

            if not pedagogia_tiene_prioridad(estudiante):
                respuesta_pqrs = intentar_procesar_seguimiento_pqrs_whatsapp(
                    estudiante, msg_body,
                )
                if respuesta_pqrs:
                    pqrs_atendido = True
                    logger.info(
                        '🆘 PQRS seguimiento — respuesta automática estudiante_id=%s',
                        estudiante.id,
                    )
        except Exception as e:
            logger.exception('PQRS seguimiento omitido: %s', e)

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
        texto_respuesta = "No entendí. Si quieres avanzar de módulo escribe *listo*. Si necesitas ayuda, escribe *ayuda*."
        
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

            from core.empleabilidad_pausa import empleabilidad_en_pausa as _emp_pausa_codigo

            if (
                estudiante.estado_onboarding == 'esperando_codigo_empleabilidad'
                and not _emp_pausa_codigo()
            ):
                from ..models import AliadoEmpleabilidad, MisionEmpleabilidad
                from ..gamificacion import PerfilGamificacion, Badge, BadgeEstudiante
                ctx_emp = estudiante.contexto_temporal or {}
                aliado_id = ctx_emp.get('aliado_empleabilidad_objetivo_id')
                mision_id = ctx_emp.get('mision_empleabilidad_id')
                aliado = None
                if aliado_id:
                    aliado = AliadoEmpleabilidad.objects.filter(id=aliado_id, vacantes_activas=True).first()
                mision = None
                if mision_id:
                    mision = MisionEmpleabilidad.objects.filter(id=mision_id, estudiante=estudiante).first()

                codigo_ingresado = msg_body.strip().lower()
                codigo_esperado = str(aliado.codigo_secreto).strip().lower() if aliado else ''
                if aliado and codigo_ingresado == codigo_esperado:
                    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                    puntos_cfg = int(getattr(estudiante.cliente, 'empleabilidad_puntos_validacion', 30) or 30)
                    perfil.agregar_puntos(puntos_cfg, f"Radar Empleabilidad: {aliado.nombre_empresa}")
                    badge = Badge.objects.filter(tipo='ESPECIAL', activo=True, nombre__icontains='emple').first()
                    if badge:
                        BadgeEstudiante.objects.get_or_create(estudiante=estudiante, badge=badge)

                    if mision and mision.estado != 'completada':
                        mision.estado = 'completada'
                        mision.codigo_validado = True
                        mision.puntos_otorgados = puntos_cfg
                        mision.fecha_completada = timezone.now()
                        mision.save(update_fields=['estado', 'codigo_validado', 'puntos_otorgados', 'fecha_completada'])

                    try:
                        from ..tasks import enviar_email_org_admin_async

                        asunto = f"Match empleabilidad: {estudiante.nombre} - {aliado.nombre_empresa}"
                        mensaje_html = (
                            f"<p>El estudiante <strong>{estudiante.nombre}</strong> "
                            f"(tel: {estudiante.telefono}) validó el código secreto de "
                            f"<strong>{aliado.nombre_empresa}</strong>.</p>"
                            f"<p>Iniciar contacto para proceso de contratación.</p>"
                        )
                        enviar_email_org_admin_async.delay(estudiante.id, asunto, mensaje_html)
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo encolar notificación de empleabilidad: {e}")

                    ctx_emp['ultimo_match_empleabilidad_aliado_id'] = aliado.id
                    ctx_emp['ultimo_match_empleabilidad_fecha'] = timezone.now().isoformat()
                    estudiante.contexto_temporal = ctx_emp
                    estudiante.estado_onboarding = 'curso_finalizado'
                    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                    texto_respuesta = (
                        f"🏆 *¡Logro desbloqueado!*\n\n"
                        f"Validaste el código de *{aliado.nombre_empresa}*.\n"
                        "✅ Ya notificamos al equipo para iniciar el proceso de empleabilidad."
                    )
                    estudiante.estado_onboarding = 'curso_finalizado'
                elif codigo_ingresado in ('listo', 'continuar'):
                    texto_respuesta = (
                        "📍 Estás en el *radar de empleabilidad*.\n\n"
                        "No uses *listo* aquí: envía el *código secreto* del punto "
                        "(el que te indiquemos en la prueba / en la entrada)."
                    )
                    estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
                else:
                    if mision and mision.estado == 'descubierta':
                        mision.estado = 'reclamada'
                        mision.fecha_reclamada = timezone.now()
                        mision.save(update_fields=['estado', 'fecha_reclamada'])
                    texto_respuesta = (
                        "🔐 El código no coincide.\n\n"
                        "Verifica el código secreto en la entrada de la empresa y vuelve a enviarlo."
                    )
                    estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
                estudiante.save(update_fields=['estado_onboarding'])

            elif estudiante.estado_onboarding == 'esperando_respuesta_pregunta_abierta_final':
                from ..models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal, ProgresoEstudiante
                if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    texto_respuesta = (
                        "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta abierta final."
                    )
                else:
                    ctx_open = estudiante.contexto_temporal or {}
                    pregunta_id = ctx_open.get('pregunta_abierta_final_id')
                    progreso_id = ctx_open.get('progreso_id')
                    pregunta = PreguntaAbiertaFinalCurso.objects.filter(id=pregunta_id, activa=True).first()
                    progreso = ProgresoEstudiante.objects.filter(id=progreso_id).first() if progreso_id else None

                    if pregunta:
                        logger.info(
                            "🧾 Pregunta abierta final en contexto | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                            estudiante.id,
                            getattr(pregunta.curso, 'id', None),
                            pregunta.id,
                            getattr(pregunta, 'orden', None),
                            (pregunta.pregunta or '')[:180],
                        )
                        respuesta_final, _ = RespuestaAbiertaFinal.objects.update_or_create(
                            pregunta=pregunta,
                            estudiante=estudiante,
                            defaults={
                                'curso': pregunta.curso,
                                'progreso': progreso,
                                'respuesta_texto': msg_body,
                                'fecha_respuesta': timezone.now(),
                                'estado': 'pendiente',
                            }
                        )
                        logger.info(
                            "📝 Respuesta abierta final registrada | estudiante_id=%s | curso_id=%s | progreso_id=%s",
                            estudiante.id,
                            getattr(pregunta.curso, 'id', None),
                            getattr(progreso, 'id', None),
                        )

                        # Evaluar con la misma rúbrica de facilitadora para dar feedback
                        # inmediato y mantener coherencia de gamificación.
                        curso_obj = pregunta.curso if pregunta and pregunta.curso_id else (progreso.curso if progreso else None)
                        modulos_eval = list(curso_obj.modulos.all().order_by('numero')) if curso_obj else []
                        puntaje_final_10 = 7
                        feedback_final = (
                            "1. Gracias por su respuesta; usted sí propone una línea de acción.\n\n"
                            "2. Para subir nivel, faltó precisión objetiva en dos partes: "
                            "(a) diagnóstico: qué señales mediría, cuánto y en qué tiempo; "
                            "(b) control: qué acción exacta aplicaría, con qué frecuencia y criterio de verificación.\n\n"
                            "3. Puntaje total: 7/10\n"
                            "4. Desglose: Enfoque 2/3 | Fundamentación 3/4 | Claridad 2/3\n\n"
                            "Diagnóstico: parcial | Acción/Control: parcial."
                        )
                        try:
                            from ..tutor_ia_modulo import evaluar_reto_facilitador
                            from core.gamificacion_modo import (
                                get_modo_gamificacion,
                                modo_usa_calificacion,
                                gamificacion_otorga_puntos,
                                formatear_nota,
                                registrar_nota_gamificacion,
                                resumen_calificaciones_estudiante,
                            )

                            modo_gami = get_modo_gamificacion(
                                getattr(estudiante, 'cliente', None),
                            )
                            from core.sandbox_canal import poner_reaccion_espera

                            poner_reaccion_espera(telefono_limpio, msg_sid)
                            puntaje_final, feedback_final = evaluar_reto_facilitador(
                                modulos_eval,
                                msg_body,
                                pregunta.pregunta,
                                estudiante_nombre=estudiante.nombre or "Estudiante",
                                curso_nombre=(getattr(curso_obj, 'nombre', None) if curso_obj else None),
                                modo_gamificacion=modo_gami,
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ No se pudo evaluar pregunta abierta final con IA: {e}")

                        respuesta_final.estado = 'calificada'
                        if modo_usa_calificacion(getattr(estudiante, 'cliente', None)):
                            nota = float(puntaje_final)
                            respuesta_final.calificacion = int(round(nota * 10))
                        else:
                            respuesta_final.calificacion = int(
                                max(1, min(10, int(puntaje_final))) * 10,
                            )
                        respuesta_final.retroalimentacion = feedback_final
                        respuesta_final.fecha_calificacion = timezone.now()
                        respuesta_final.save(update_fields=['estado', 'calificacion', 'retroalimentacion', 'fecha_calificacion'])

                        puntos_msg = ""
                        try:
                            if modo_usa_calificacion(getattr(estudiante, 'cliente', None)):
                                nota_f = float(puntaje_final)
                                registrar_nota_gamificacion(
                                    estudiante,
                                    nota_f,
                                    'pregunta_abierta',
                                    curso=curso_obj,
                                    detalle='Pregunta abierta final',
                                )
                                res_n = resumen_calificaciones_estudiante(
                                    estudiante,
                                    curso_obj.id if curso_obj else None,
                                )
                                prom = res_n.get('promedio')
                                extra_prom = (
                                    f"\n📊 *Promedio acumulado:* {formatear_nota(prom)}/5"
                                    if prom is not None else ''
                                )
                                puntos_msg = (
                                    f"\n\n*Nota:* {formatear_nota(nota_f)}/5{extra_prom}"
                                )
                            elif gamificacion_otorga_puntos(
                                getattr(estudiante, 'cliente', None), curso_obj,
                            ):
                                from ..gamificacion import PerfilGamificacion
                                from ..response_templates import _barra_progreso

                                perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                                puntaje_10 = int(puntaje_final)
                                puntos_abierta = int(max(1, min(10, puntaje_10)) * 5)
                                perfil.agregar_puntos(
                                    puntos_abierta,
                                    f"Pregunta abierta final: {puntaje_10}/10",
                                )
                                perfil.refresh_from_db()

                                porcentaje = progreso.porcentaje_avance() if progreso else 100
                                barra = _barra_progreso(porcentaje)
                                puntos_msg = (
                                    f"\n\n💰 *+{puntos_abierta} puntos* → Total: *{perfil.puntos_totales} pts*\n"
                                    f"{barra} {porcentaje}%"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ No se pudieron aplicar puntos por pregunta abierta final: {e}")

                        # Si hay más preguntas abiertas pendientes (máximo 3),
                        # continuar en secuencia antes de emitir certificado.
                        siguiente_pregunta = _pregunta_abierta_final_pendiente(estudiante, progreso) if progreso else None
                        if siguiente_pregunta:
                            logger.info(
                                "🔁 Siguiente pregunta abierta final | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                                estudiante.id,
                                progreso.curso.id,
                                siguiente_pregunta.id,
                                getattr(siguiente_pregunta, 'orden', None),
                                (siguiente_pregunta.pregunta or '')[:180],
                            )
                            estudiante.contexto_temporal = {
                                'tipo': 'pregunta_abierta_final',
                                'curso_id': progreso.curso.id,
                                'progreso_id': progreso.id,
                                'pregunta_abierta_final_id': siguiente_pregunta.id,
                            }
                            estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
                            estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

                            texto_respuesta = (
                                "[MULTI_MSG]"
                                f"*Facilitadora*\n\n{feedback_final}{puntos_msg}"
                                "[SEP]"
                                "📝 *Siguiente pregunta abierta final*\n\n"
                                f"{siguiente_pregunta.pregunta}\n\n"
                                "✍️ Responde con tus propias palabras (texto o audio)."
                            )
                        else:
                            # Mantener el flujo general: después de la última pregunta final,
                            # se entrega certificado y se cierra el curso.
                            msg_cert_img = ""
                            if curso_obj:
                                try:
                                    from ..certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
                                    cert = crear_certificado_automatico(estudiante, curso_obj)
                                    if cert and cert.archivo_imagen:
                                        cert_url = obtener_url_certificado_twilio(cert)
                                        if cert_url:
                                            msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                        else:
                                            s3_key = str(cert.archivo_imagen.name)
                                            cert_url = f"https://eki-produccion.s3.us-east-2.amazonaws.com/{s3_key}"
                                            msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                    elif cert and cert.archivo_pdf:
                                        msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert.archivo_pdf.url}"
                                    else:
                                        msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                                except Exception as e:
                                    logger.error(f"❌ Error certificado tras pregunta abierta final: {e}", exc_info=True)
                                    msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."

                            # Radar/empleabilidad pausado: no envía Subachoque.
                            radar_msg = _radar_msg_si_aplica(estudiante)

                            estudiante.estado_onboarding = 'curso_finalizado'
                            estudiante.contexto_temporal = None
                            estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])

                            partes_finales = [f"*Facilitadora*\n\n{feedback_final}{puntos_msg}"]
                            if radar_msg:
                                partes_finales.append(radar_msg)
                            if msg_cert_img:
                                partes_finales.append(msg_cert_img)
                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes_finales)
                    else:
                        texto_respuesta = (
                            "No encuentro una pregunta abierta final activa para tu curso en este momento. "
                            "Escribe *ayuda* para soporte."
                        )

            # v1.9.8g: Post-certificate cutoff — no more interaction
            elif estudiante.estado_onboarding == 'curso_finalizado':
                print(f"🚫 Curso finalizado — sin interacción post-certificado")
                # Check if student has a new active course
                from ..models import ProgresoEstudiante
                nuevo_progreso = ProgresoEstudiante.objects.filter(
                    estudiante=estudiante, completado=False
                ).first()
                if nuevo_progreso:
                    # New course assigned — reset state
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    texto_respuesta = (
                        f"🎉 *¡Tienes un nuevo curso asignado!*\n\n"
                        f"📚 *{nuevo_progreso.curso.nombre}*\n\n"
                        f"Escribe *listo* para comenzar."
                    )
                else:
                    texto_respuesta = (
                        "✅ *Tu proceso del curso ya finalizó y tu certificado fue enviado.*\n\n"
                        "Cuando tu organización te inscriba en un nuevo curso, te notificaremos. "
                        "¡Gracias por tu participación! 🎓"
                    )
            
            # v1.9.8g: Asistente (compañero) — hasta 2 preguntas antes del reto
            elif estudiante.estado_onboarding == 'esperando_respuesta_asistente':
                ctx = estudiante.contexto_temporal or {}
                preguntas_hechas = ctx.get('preguntas_hechas', 0)
                modulos_reto_ids = ctx.get('modulos_reto_ids', [])
                progreso_id = ctx.get('progreso_id')
                _cli = estudiante.cliente if getattr(estudiante, 'cliente_id', None) else None
                _na_cli = (
                    (_cli.nombre_agente_asistente if _cli and getattr(_cli, 'nombre_agente_asistente', None) else '')
                    or ''
                )
                _na_curso = ''
                if progreso_id:
                    try:
                        from ..models import ProgresoEstudiante
                        _pp = ProgresoEstudiante.objects.select_related('curso').get(id=progreso_id)
                        _na_curso = (_pp.curso.nombre_agente_asistente if _pp.curso else '') or ''
                    except ProgresoEstudiante.DoesNotExist:
                        pass
                nombre_asistente = (_na_cli or _na_curso or 'Darío').strip() or 'Darío'
                print(f"💬 Asistente ({nombre_asistente}): Esperando respuesta del compañero IA")
                
                msg_lower = msg_body.strip().lower()
                if msg_lower in ['ayuda', 'soporte', 'ticket']:
                    from ..security_handler import procesar_solicitud_soporte
                    texto_respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'asistente_ayuda')
                elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    # Audio no pudo ser transcrito — NO contar como pregunta
                    print(f"🎤 Audio no transcrito en asistente — pidiendo reintento")
                    from core.agentes_whatsapp import mensaje_con_titular_agente

                    preguntas_restantes = 2 - preguntas_hechas
                    texto_respuesta = mensaje_con_titular_agente(
                        nombre_asistente,
                        (
                            f"No pude escuchar su audio. Por favor intente de nuevo "
                            f"o escríbame su pregunta.\n\n"
                            f"Le quedan {preguntas_restantes} pregunta(s). "
                            f"Si no tiene preguntas, escriba *listo*."
                        ),
                    )
                elif _mensaje_indica_listo(msg_body) or preguntas_hechas >= 2:
                    # Flujo exigido: Darío -> Facilitadora (reto) al escribir listo
                    print("🎯 Asistente terminó → Activando Facilitadora con reto")
                    from ..models import ProgresoEstudiante
                    from ..tutor_ia_modulo import (
                        cargar_modulos_reto,
                        generar_reto_facilitador,
                        listar_modulos_cobertura_reto,
                    )
                    from ..models import Modulo as ModuloRetoCtx
                    try:
                        progreso = ProgresoEstudiante.objects.get(id=progreso_id)
                    except ProgresoEstudiante.DoesNotExist:
                        progreso = None
                    modulos_reto = cargar_modulos_reto(
                        modulos_reto_ids, progreso.curso_id if progreso else None
                    )
                    if not modulos_reto and progreso and ctx.get('modulo_id'):
                        _mchk = ModuloRetoCtx.objects.filter(
                            id=ctx['modulo_id'], curso_id=progreso.curso_id
                        ).first()
                        if _mchk:
                            modulos_reto = listar_modulos_cobertura_reto(_mchk, progreso.curso)
                            modulos_reto_ids = [m.id for m in modulos_reto]

                    if modulos_reto and progreso:
                        _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                        from core.facilitador_perfil import nombre_display_facilitador

                        nombre_tutor = (
                            (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                            progreso.curso.nombre_agente_tutor or
                            nombre_display_facilitador(progreso.curso)
                        )
                        reto = generar_reto_facilitador(
                            modulos_reto,
                            progreso.curso.nombre,
                            estudiante_nombre=estudiante.nombre or "Estudiante",
                            curso=progreso.curso,
                            modulo_checkpoint=modulos_reto[-1] if modulos_reto else None,
                        )
                        _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                        estudiante.contexto_temporal = {
                            'tipo': 'reto_facilitador',
                            'modulos_reto_ids': modulos_reto_ids,
                            'reto_texto': reto,
                            'progreso_id': progreso_id,
                            'es_final': ctx.get('es_reto_final', False),
                            '_ts_leccion': _prev_ts,
                        }
                        estudiante.estado_onboarding = 'esperando_respuesta_reto'
                        estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                        try:
                            from core.facilitador_perfil import resolver_perfil_facilitador
                            from core.telemetria import registrar_reto_planteado

                            _curso_plan = progreso.curso if progreso else None
                            registrar_reto_planteado(
                                estudiante,
                                curso=_curso_plan,
                                modulo=(modulos_reto[-1] if modulos_reto else None),
                                reto_texto=reto,
                                modulos_cubiertos=modulos_reto_ids,
                                perfil_facilitador=resolver_perfil_facilitador(_curso_plan),
                            )
                        except Exception:
                            logger.debug('[reto] telemetría reto_planteado omitida', exc_info=True)
                        from core.tutor_ia_modulo import bloque_reto_whatsapp

                        texto_respuesta = bloque_reto_whatsapp(nombre_tutor, reto)
                    else:
                        logger.warning(
                            "reto asistente vacío | progreso_id=%s modulo_ctx=%s ids_ctx=%s",
                            progreso_id,
                            (ctx or {}).get('modulo_id'),
                            modulos_reto_ids,
                        )
                        estudiante.estado_onboarding = 'completado'
                        estudiante.contexto_temporal = None
                        estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
                        # Si el progreso ya está completado, no pedir *listo* como si hubiera más módulos
                        _prog_fin = None
                        try:
                            from ..models import ProgresoEstudiante
                            if progreso_id:
                                _prog_fin = ProgresoEstudiante.objects.filter(id=progreso_id).first()
                        except Exception:
                            _prog_fin = None
                        if _prog_fin and _prog_fin.completado:
                            texto_respuesta = (
                                "🎉 Ya completaste este curso.\n\n"
                                "Si el certificado aún no llega, escribe *ayuda*. "
                                "Si tienes otro curso asignado, también puedes escribir *listo*."
                            )
                        else:
                            texto_respuesta = (
                                "Seguimos con tu curso. Escribí *listo* para continuar "
                                "o *ayuda* si necesitás soporte."
                            )
                else:
                    # Student asked a question to Darío — answer from RAG (max 2)
                    preguntas_hechas += 1
                    from ..models import ProgresoEstudiante
                    from ..tutor_ia_modulo import cargar_modulos_reto, generar_respuesta_asistente
                    try:
                        _pr_dario = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
                    except ProgresoEstudiante.DoesNotExist:
                        _pr_dario = None
                    modulos_reto = cargar_modulos_reto(
                        modulos_reto_ids, _pr_dario.curso_id if _pr_dario else None
                    )
                    
                    respuesta_dario = generar_respuesta_asistente(
                        modulos_reto,
                        msg_body,
                        estudiante_nombre=estudiante.nombre or "Estudiante",
                        nombre_asistente=nombre_asistente,
                    )
                    
                    ctx['preguntas_hechas'] = preguntas_hechas
                    estudiante.contexto_temporal = ctx
                    estudiante.save()
                    
                    from core.agentes_whatsapp import mensaje_con_titular_agente

                    if preguntas_hechas >= 2:
                        texto_respuesta = mensaje_con_titular_agente(
                            nombre_asistente,
                            (
                                f"{respuesta_dario}\n\n"
                                f"Ya respondí sus 2 preguntas. Ahora la facilitadora le tiene un reto. "
                                f"Escriba *listo* cuando esté preparado."
                            ),
                        )
                    else:
                        texto_respuesta = mensaje_con_titular_agente(
                            nombre_asistente,
                            (
                                f"{respuesta_dario}\n\n"
                                f"¿Tiene otra pregunta? Le queda {2 - preguntas_hechas} pregunta más. "
                                f"Puede preguntar sobre el tema del curso. Si no, escriba *listo*."
                            ),
                        )
            
            # v1.9.8g: Facilitadora — evaluando respuesta al reto
            elif estudiante.estado_onboarding == 'esperando_respuesta_reto':
                print(f"📋 Facilitadora: Evaluando respuesta al reto")
                ctx = estudiante.contexto_temporal or {}
                modulos_reto_ids = ctx.get('modulos_reto_ids', [])
                reto_texto = ctx.get('reto_texto', '')
                progreso_id = ctx.get('progreso_id')
                
                # 📸 Foto como evidencia del reto: guardar y calificar con visión.
                evidencia_bytes = None
                evidencia_type = ''
                evidencia_url_guardada = ''
                resultado_foto = None
                if evidencia_imagen_url:
                    from core.gamificacion_modo import get_modo_gamificacion
                    from core.models import ProgresoEstudiante
                    from core.reto_evidencia import (
                        descargar_media_twilio,
                        evaluar_evidencia_foto,
                        guardar_evidencia,
                    )
                    from core.tutor_ia_modulo import cargar_modulos_reto

                    progreso_foto = ProgresoEstudiante.objects.filter(id=progreso_id).first()
                    evidencia_bytes, evidencia_type = descargar_media_twilio(evidencia_imagen_url)
                    evidencia_type = evidencia_type or evidencia_imagen_type
                    if evidencia_bytes:
                        evidencia_url_guardada = guardar_evidencia(
                            evidencia_bytes,
                            evidencia_type,
                            estudiante_id=estudiante.id,
                            curso_id=(progreso_foto.curso_id if progreso_foto else None),
                        )
                        if _mensaje_indica_listo(msg_body):
                            # El webhook convierte media sin texto en "listo"; aquí es una foto.
                            msg_body = ''
                        resultado_foto = evaluar_evidencia_foto(
                            evidencia_bytes,
                            evidencia_type,
                            reto_original=reto_texto,
                            modulos_cubiertos=cargar_modulos_reto(
                                modulos_reto_ids,
                                progreso_foto.curso_id if progreso_foto else None,
                            ),
                            curso=(progreso_foto.curso if progreso_foto else None),
                            estudiante_nombre=estudiante.nombre or 'Estudiante',
                            texto_acompanante=msg_body,
                            modo_gamificacion=get_modo_gamificacion(
                                getattr(estudiante, 'cliente', None)
                            ),
                        )
                    logger.info(
                        "[reto] evidencia foto estudiante=%s bytes=%s guardada=%s evaluada=%s",
                        estudiante.id,
                        len(evidencia_bytes or b''),
                        bool(evidencia_url_guardada),
                        resultado_foto is not None,
                    )

                msg_lower = msg_body.strip().lower()
                if msg_lower in ['ayuda', 'soporte', 'ticket']:
                    from ..security_handler import procesar_solicitud_soporte
                    texto_respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'reto_ayuda')
                elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    # Audio no pudo ser transcrito — pedir reintento sin evaluar
                    print(f"🎤 Audio no transcrito en reto — pidiendo reintento")
                    texto_respuesta = (
                        "No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta al reto.\n\n"
                        "_Escriba, envíe un audio o mande la foto de su evidencia._"
                    )
                elif evidencia_bytes and resultado_foto is None:
                    # Foto recibida pero sin visión disponible: no castigar con 1/10.
                    from core.reto_evidencia import mensaje_evidencia_no_evaluable

                    texto_respuesta = mensaje_evidencia_no_evaluable()
                elif _mensaje_indica_listo(msg_body):
                    # *listo* no es respuesta al reto (antes se "evaluaba" o se saltaba el avance).
                    texto_respuesta = (
                        "Para el reto necesito su respuesta en texto, audio o la foto "
                        "de su evidencia. Cuando la envíe, la facilitadora la revisa.\n\n"
                        "_Escriba, envíe un audio o mande la foto de su evidencia._"
                    )
                else:
                    from ..models import ProgresoEstudiante
                    from ..tutor_ia_modulo import cargar_modulos_reto, evaluar_reto_facilitador
                    progreso = (
                        ProgresoEstudiante.objects.filter(id=progreso_id).first()
                        if progreso_id
                        else None
                    )
                    modulos_reto = cargar_modulos_reto(
                        modulos_reto_ids, progreso.curso_id if progreso else None
                    )
                    
                    from core.gamificacion_modo import get_modo_gamificacion, construir_mensaje_evaluacion_reto

                    _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                    modo_gami = get_modo_gamificacion(_cliente)
                    if resultado_foto is not None:
                        puntaje, feedback = resultado_foto
                    else:
                        from core.sandbox_canal import poner_reaccion_espera

                        poner_reaccion_espera(telefono_limpio, msg_sid)
                        puntaje, feedback = evaluar_reto_facilitador(
                            modulos_reto, msg_body, reto_texto,
                            estudiante_nombre=estudiante.nombre or "Estudiante",
                            curso_nombre=(progreso.curso.nombre if progreso else None),
                            modo_gamificacion=modo_gami,
                        )

                    _curso_reto = progreso.curso if progreso else None
                    try:
                        from core.facilitador_perfil import resolver_perfil_facilitador
                        from core.telemetria import registrar_reto_respondido

                        registrar_reto_respondido(
                            estudiante,
                            curso=_curso_reto,
                            modulo=(modulos_reto[-1] if modulos_reto else None),
                            puntaje=puntaje,
                            feedback=feedback,
                            tipo_respuesta=('foto' if resultado_foto is not None else 'texto'),
                            evidencia_url=evidencia_url_guardada,
                            reto_texto=reto_texto,
                            respuesta_texto=msg_body,
                            perfil_facilitador=resolver_perfil_facilitador(_curso_reto),
                        )
                    except Exception:
                        logger.debug('[reto] telemetría reto_respondido omitida', exc_info=True)

                    from core.facilitador_perfil import nombre_display_facilitador

                    nombre_tutor = (
                        (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                        nombre_display_facilitador(_curso_reto)
                    )
                    if progreso is not None:
                        nombre_tutor = (
                            progreso.curso.nombre_agente_tutor
                            or nombre_display_facilitador(progreso.curso)
                        )

                    msg_eval = construir_mensaje_evaluacion_reto(
                        estudiante, progreso, puntaje, feedback, nombre_tutor,
                    )
                    
                    es_final = ctx.get('es_final', False)
                    
                    if es_final and progreso:
                        pregunta_abierta = None
                        pregunta_abierta_ctx_id = ctx.get('pregunta_abierta_final_id')
                        if pregunta_abierta_ctx_id:
                            from ..models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal
                            pregunta_ctx = PreguntaAbiertaFinalCurso.objects.filter(
                                id=pregunta_abierta_ctx_id,
                                curso=progreso.curso,
                                activa=True,
                            ).first()
                            if pregunta_ctx:
                                ya_respondio_ctx = RespuestaAbiertaFinal.objects.filter(
                                    pregunta=pregunta_ctx,
                                    estudiante=estudiante,
                                ).exists()
                                if not ya_respondio_ctx:
                                    pregunta_abierta = pregunta_ctx

                        if not pregunta_abierta:
                            pregunta_abierta = _pregunta_abierta_final_pendiente(estudiante, progreso)

                        if pregunta_abierta:
                            logger.info(
                                "🧭 Pregunta abierta final seleccionada post-reto | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                                estudiante.id,
                                progreso.curso.id,
                                pregunta_abierta.id,
                                getattr(pregunta_abierta, 'orden', None),
                                (pregunta_abierta.pregunta or '')[:180],
                            )
                            estudiante.contexto_temporal = {
                                'tipo': 'pregunta_abierta_final',
                                'curso_id': progreso.curso.id,
                                'progreso_id': progreso.id,
                                'pregunta_abierta_final_id': pregunta_abierta.id,
                            }
                            estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
                            estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                            texto_respuesta = (
                                f"{msg_eval}\n\n"
                                "📝 *Antes del cierre final*, responde esta pregunta abierta:\n\n"
                                f"{pregunta_abierta.pregunta}\n\n"
                                "✍️ Tu facilitadora revisará y calificará tu respuesta."
                            )
                        else:
                            logger.info(
                                "⚠️ Post-reto final sin pregunta abierta final | estudiante_id=%s | curso_id=%s | ctx_pregunta_id=%s",
                                estudiante.id,
                                progreso.curso.id,
                                pregunta_abierta_ctx_id,
                            )
                            # v1.9.8h: Final reto — issue certificate
                            estudiante.estado_onboarding = 'curso_finalizado'
                            estudiante.contexto_temporal = None
                            estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
                            
                            msg_cert_img = ""
                            try:
                                from ..certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
                                cert = crear_certificado_automatico(estudiante, progreso.curso)
                                if cert and cert.archivo_imagen:
                                    cert_url = obtener_url_certificado_twilio(cert)
                                    if cert_url:
                                        msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                    else:
                                        s3_key = str(cert.archivo_imagen.name)
                                        cert_url = f"https://eki-produccion.s3.us-east-2.amazonaws.com/{s3_key}"
                                        msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                elif cert and cert.archivo_pdf:
                                    msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert.archivo_pdf.url}"
                                else:
                                    msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                            except Exception as e:
                                logger.error(f"❌ Error certificado post-reto final: {e}", exc_info=True)
                                msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."

                            # Radar/empleabilidad pausado: no envía Subachoque.
                            radar_msg = _radar_msg_si_aplica(estudiante)
                            
                            msg_final = (
                                f"{msg_eval}\n\n"
                                f"🎓 *¡FELICITACIONES!*\n\n"
                                f"Ha completado el curso: *{progreso.curso.nombre}*"
                            )
                            partes_finales = [msg_final]
                            if radar_msg:
                                partes_finales.append(radar_msg)
                            partes_finales.append(msg_cert_img)
                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes_finales)
                    else:
                        _prev_ctx = estudiante.contexto_temporal or {}
                        from ..helpers_examenes import contexto_temporal_tras_cerrar_agente
                        from ..drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

                        _base_ctx = contexto_temporal_tras_cerrar_agente(progreso, _prev_ctx) or {}
                        estudiante.estado_onboarding = 'completado'
                        # Tras Darío + facilitadora: el drip/calendario aplica igual que sin agentes.
                        # No adelantar modulo_actual hasta que desbloquee el siguiente módulo.
                        if progreso:
                            modulo_cerrado = progreso.modulo_actual
                            from ..modulo_publicacion import (
                                mensaje_bloqueo_sin_siguiente_publicado,
                                siguiente_modulo_publicado_wa,
                            )

                            _blk_pub_reto = mensaje_bloqueo_sin_siguiente_publicado(
                                estudiante, progreso, modulo_cerrado
                            )
                            _blk_tras_reto = mensaje_bloqueo_avance_siguiente_modulo(
                                estudiante, progreso, modulo_cerrado
                            )
                            if _blk_pub_reto:
                                estudiante.contexto_temporal = _base_ctx
                                estudiante.save(
                                    update_fields=['contexto_temporal', 'estado_onboarding']
                                )
                                texto_respuesta = f"{msg_eval}\n\n{_blk_pub_reto}"
                            elif _blk_tras_reto:
                                estudiante.contexto_temporal = _base_ctx
                                estudiante.save(
                                    update_fields=['contexto_temporal', 'estado_onboarding']
                                )
                                texto_respuesta = f"{msg_eval}\n\n{_blk_tras_reto}"
                            else:
                                siguiente = siguiente_modulo_publicado_wa(
                                    progreso.curso, progreso.modulo_actual
                                )
                                if siguiente:
                                    progreso.modulo_actual = siguiente
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
                                    _base_ctx['post_reto_entregar_modulo_id'] = siguiente.id
                                estudiante.contexto_temporal = _base_ctx
                                estudiante.save(
                                    update_fields=['contexto_temporal', 'estado_onboarding']
                                )
                                texto_respuesta = (
                                    f"{msg_eval}\n\n"
                                    "✅ Escribe *continuar* para recibir el contenido del siguiente módulo.\n"
                                    "Cuando lo hayas revisado, responde *listo* para seguir."
                                )
                        else:
                            estudiante.contexto_temporal = _base_ctx
                            estudiante.save(
                                update_fields=['contexto_temporal', 'estado_onboarding']
                            )
                            texto_respuesta = (
                                f"{msg_eval}\n\n"
                                "✅ Escribe *continuar* para recibir el contenido del siguiente módulo.\n"
                                "Cuando lo hayas revisado, responde *listo* para seguir."
                            )
                    print(f"✅ Facilitadora reto evaluado | modo={modo_gami} | valor={puntaje}", flush=True)
            
            # 3.5a PRIORIDAD: Si está respondiendo al TUTOR IA (legacy)
            elif estudiante.estado_onboarding == 'esperando_respuesta_tutor_ia':
                from ..gamificacion import PerfilGamificacion
                print(f"🎓 Evaluando respuesta del Facilitador (legacy tutor IA)")
                ctx = estudiante.contexto_temporal or {}
                modulo_id = ctx.get('modulo_id')
                pregunta_tutor = ctx.get('pregunta_tutor', '')
                intentos = ctx.get('intentos_tutor', 0)
                
                # Detectar si el usuario quiere omitir el tutor
                msg_lower = msg_body.strip().lower()
                palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']
                
                if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    # Audio no pudo ser transcrito — pedir reintento
                    texto_respuesta = (
                        "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta.\n\n"
                        "Si prefieres continuar sin responder, escribe *listo*."
                    )
                elif any(p in msg_lower for p in palabras_skip):
                    # Usuario quiere seguir sin responder al tutor
                    estudiante.contexto_temporal = None
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    print(f"⏭️ Profesor Gerónimo omitido por usuario")
                    
                    # Si dijo "menu", retomar curso (B2B) o menú sandbox
                    if msg_lower in ['menu', 'menú']:
                        from ..flujo_whatsapp_b2b import respuesta_tras_keyword_menu
                        texto_respuesta = respuesta_tras_keyword_menu(
                            estudiante, estudiante.nombre, msg_body
                        )
                    else:
                        # v1.9.6: NO llamar continuar_leccion — el skip solo cierra el tutor.
                        # El estudiante ya tiene el contenido del módulo. Cuando lo estudie
                        # y escriba "listo" de nuevo, avanzará por el flujo normal (estado=completado).
                        texto_respuesta = "👍 Sin problema.\n\nContinúa revisando el contenido del módulo 👆\n\nCuando termines, escribe *listo* para avanzar al siguiente."
                        print(f"✅ v1.9.6: Skip Gerónimo sin avance automático", flush=True)
                else:
                    from ..tutor_ia_modulo import evaluar_respuesta_modulo
                    from ..models import Modulo
                    
                    try:
                        modulo = Modulo.objects.get(id=modulo_id) if modulo_id else None
                    except Modulo.DoesNotExist:
                        modulo = None
                    
                    if modulo:
                        aprobado, feedback = evaluar_respuesta_modulo(
                            modulo, msg_body, pregunta_tutor,
                            estudiante_nombre=estudiante.nombre or "Estudiante"
                        )
                        
                        # v1.9.8: Siempre 1 sola interacción — feedback y continúa
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save()
                        if aprobado:
                            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                            perfil.agregar_puntos(5, "Respuesta correcta - Profesor Gerónimo")
                            texto_respuesta = f"{feedback}\n\n💰 *+5 puntos bonus* por tu respuesta 💪\n\nContinúa revisando el módulo 👆\nCuando termines, escribe *listo* para avanzar."
                            print(f"✅ v1.9.8: Gerónimo aprobado — 1 interacción", flush=True)
                        else:
                            texto_respuesta = f"{feedback}\n\n✅ *¡Buen esfuerzo!* Sigue estudiando el módulo 👆\n\nCuando termines, escribe *listo* para avanzar."
                            print(f"✅ v1.9.8: Gerónimo incorrecto — feedback y continúa", flush=True)
                    else:
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save()
                        # v1.9.6: Solo enviar feedback, NO auto-avanzar
                        texto_respuesta = "✅ Gracias por tu respuesta!\n\nContinúa revisando el módulo 👆\nCuando termines, escribe *listo* para avanzar."
                        print(f"✅ v1.9.6: Gerónimo sin módulo — feedback sin auto-avance", flush=True)
            
            # 3.5a2 PRIORIDAD: Si está respondiendo a la REVISIÓN DE PROGRESO
            elif estudiante.estado_onboarding == 'esperando_respuesta_progreso':
                from ..gamificacion import PerfilGamificacion
                print(f"�‍🏫 Evaluando respuesta de María (Revisión de Progreso)")
                ctx = estudiante.contexto_temporal or {}
                pregunta_tutor = ctx.get('pregunta_tutor', '')
                modulos_info = ctx.get('modulos_info', '')
                intentos = ctx.get('intentos_tutor', 0)
                modulos_reto_ids = ctx.get('modulos_reto_ids', [])
                progreso_id = ctx.get('progreso_id')
                es_reto_final = ctx.get('es_reto_final', False)

                def _activar_reto_despues_de_maria(prefijo=""):
                    from ..models import ProgresoEstudiante, Modulo
                    from ..tutor_ia_modulo import (
                        cargar_modulos_reto,
                        generar_reto_facilitador,
                        listar_modulos_cobertura_reto,
                    )
                    progreso_r = (
                        ProgresoEstudiante.objects.filter(id=progreso_id)
                        .select_related('curso', 'modulo_actual')
                        .first()
                        if progreso_id
                        else None
                    )
                    _mids = list(modulos_reto_ids) if modulos_reto_ids else []
                    modulos_reto = (
                        cargar_modulos_reto(_mids, progreso_r.curso_id if progreso_r else None)
                        if _mids
                        else []
                    )
                    if not modulos_reto and progreso_r:
                        _mchk = None
                        _outer = estudiante.contexto_temporal or {}
                        mid = _outer.get('modulo_id')
                        if mid:
                            _mchk = Modulo.objects.filter(
                                id=mid, curso_id=progreso_r.curso_id
                            ).first()
                        if not _mchk and getattr(progreso_r, 'modulo_actual_id', None):
                            _mchk = progreso_r.modulo_actual
                        if _mchk:
                            modulos_reto = listar_modulos_cobertura_reto(_mchk, progreso_r.curso)
                            _mids = [m.id for m in modulos_reto]
                    if not (progreso_r and modulos_reto):
                        logger.warning(
                            "reto post-María vacío | progreso_id=%s modulo_ctx=%s ids_ctx=%s",
                            progreso_id,
                            (estudiante.contexto_temporal or {}).get('modulo_id'),
                            modulos_reto_ids,
                        )
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                        if progreso_r and progreso_r.completado:
                            return (
                                f"{prefijo}\n\n"
                                "🎉 Ya completaste este curso.\n\n"
                                "Si el certificado aún no llega, escribe *ayuda*. "
                                "Si tienes otro curso asignado, también puedes escribir *listo*."
                            ).strip()
                        return (
                            f"{prefijo}\n\n"
                            "Seguimos con tu curso. Escribí *listo* para continuar "
                            "o *ayuda* si necesitás soporte."
                        ).strip()
                    _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                    nombre_tutor = (
                        (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                        progreso_r.curso.nombre_agente_tutor or 'Claudia'
                    )
                    reto = generar_reto_facilitador(
                        modulos_reto,
                        progreso_r.curso.nombre,
                        estudiante_nombre=estudiante.nombre or "Estudiante",
                        curso=progreso_r.curso,
                        modulo_checkpoint=modulos_reto[-1] if modulos_reto else None,
                    )
                    _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                    estudiante.contexto_temporal = {
                        'tipo': 'reto_facilitador',
                        'modulos_reto_ids': _mids,
                        'reto_texto': reto,
                        'progreso_id': progreso_id,
                        'es_final': es_reto_final,
                        '_ts_leccion': _prev_ts,
                    }
                    estudiante.estado_onboarding = 'esperando_respuesta_reto'
                    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                    from core.tutor_ia_modulo import bloque_reto_whatsapp

                    bloque_reto = bloque_reto_whatsapp(nombre_tutor, reto)
                    return f"{prefijo}\n\n{bloque_reto}".strip()
                
                # Detectar si el usuario quiere omitir
                msg_lower = msg_body.strip().lower()
                palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']
                
                if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    texto_respuesta = (
                        "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta.\n\n"
                        "Si prefieres continuar sin responder, escribe *listo*."
                    )
                elif any(p in msg_lower for p in palabras_skip):
                    print(f"⏭️ María omitida por usuario → activando reto")
                    
                    if msg_lower in ['menu', 'menú']:
                        from ..flujo_whatsapp_b2b import respuesta_tras_keyword_menu
                        texto_respuesta = respuesta_tras_keyword_menu(
                            estudiante, estudiante.nombre, msg_body
                        )
                    else:
                        texto_respuesta = _activar_reto_despues_de_maria("👍 Perfecto, pasemos al reto de la facilitadora.")
                else:
                    from ..tutor_ia_modulo import evaluar_respuesta_progreso
                    
                    resuelta, feedback = evaluar_respuesta_progreso(
                        modulos_info, msg_body, pregunta_tutor,
                        estudiante_nombre=estudiante.nombre or "Estudiante"
                    )
                    
                    if resuelta:
                        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                        perfil.agregar_puntos(3, "Revisión de progreso - María")
                        texto_respuesta = _activar_reto_despues_de_maria(f"{feedback}\n\n💰 *+3 puntos* por tu reflexión 💪")
                        print(f"✅ María resuelta — activando reto", flush=True)
                    else:
                        texto_respuesta = _activar_reto_despues_de_maria(f"{feedback}\n\n✅ *Buena reflexión!*")
                        print(f"✅ María evaluada — activando reto", flush=True)

            # 3.5a2 PRIORIDAD: Si está respondiendo pregunta de RECUPERACIÓN (<70 pts)
            elif estudiante.estado_onboarding == 'esperando_respuesta_recuperacion':
                ctx = estudiante.contexto_temporal or {}
                pregunta_data = ctx.get('pregunta_data', {})
                correcta = pregunta_data.get('correcta', 'A')
                explicacion = pregunta_data.get('explicacion', '')
                
                from ..tutor_ia_modulo import evaluar_respuesta_recuperacion
                es_correcta, msg_evaluacion = evaluar_respuesta_recuperacion(msg_body, correcta, explicacion)
                
                # Si acertó, dar puntos bonus
                if es_correcta:
                    try:
                        from ..gamificacion import PerfilGamificacion
                        perfil_rec = PerfilGamificacion.objects.get(estudiante=estudiante)
                        perfil_rec.agregar_puntos(15, "🏆 Pregunta de recuperación correcta")
                    except Exception:
                        pass
                
                # Limpiar estado y continuar al certificado
                curso_id = ctx.get('curso_id')
                estudiante.estado_onboarding = 'completado'
                estudiante.contexto_temporal = None
                estudiante.save()
                
                # Generar certificado y resumen
                from ..response_templates import _generar_completado_final
                msg_final = _generar_completado_final(estudiante, curso_id)
                
                texto_respuesta = f"[MULTI_MSG]{msg_evaluacion}[SEP]{msg_final}"

            # 3.5b PRIORIDAD: Si está respondiendo pregunta de módulo (examen clásico)
            elif estudiante.estado_onboarding == 'esperando_respuesta_modulo':
                from ..pregunta_handler import (
                    examen_modulo_sin_pregunta_pendiente,
                    recuperar_examen_modulo_vacio,
                )

                # Mini-examen fantasma (rollback/recuperación sin pregunta):
                # *listo* debe entregar la lección, no el default «No entendí».
                if examen_modulo_sin_pregunta_pendiente(estudiante):
                    logger.warning(
                        'examen modulo vacio | estudiante_id=%s ctx_keys=%s',
                        estudiante.id,
                        sorted((estudiante.contexto_temporal or {}).keys()),
                    )
                    recuperar_examen_modulo_vacio(estudiante)
                    estudiante.refresh_from_db()
                    if _mensaje_indica_listo(msg_body):
                        from ..response_templates import get_response_for_intent

                        texto_respuesta = get_response_for_intent(
                            'continuar_leccion',
                            estudiante.nombre,
                            estudiante_id=estudiante.id,
                            mensaje_original=msg_body,
                        )
                    else:
                        texto_respuesta = (
                            "No hay una pregunta pendiente. "
                            "Si quiere avanzar, escriba *listo*."
                        )
                elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    texto_respuesta = (
                        "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta."
                    )
                elif msg_body.strip().lower() in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    from ..flujo_whatsapp_b2b import respuesta_tras_keyword_menu
                    texto_respuesta = respuesta_tras_keyword_menu(
                        estudiante, estudiante.nombre, msg_body
                    )
                else:
                    # Validar respuesta a pregunta de módulo
                    from ..pregunta_handler import validar_respuesta, procesar_respuesta_abierta_ia
                    print(f"📝 Validando respuesta a pregunta de módulo")
                    
                    # Verificar si la pregunta es abierta (IA) o de opciones
                    ctx = estudiante.contexto_temporal or {}
                    es_pregunta_ia = ctx.get('tipo') == 'pregunta_tutor_ia'
                    
                    # Fallback: verificar ultima_pregunta_data si contexto no tiene tipo IA
                    if not es_pregunta_ia:
                        pregunta_data = None
                        if hasattr(estudiante, 'ultima_pregunta_data') and estudiante.ultima_pregunta_data:
                            import ast
                            try:
                                pregunta_data = ast.literal_eval(estudiante.ultima_pregunta_data)
                            except Exception:
                                pregunta_data = None
                        if pregunta_data and (not pregunta_data.get('opciones')):
                            es_pregunta_ia = True
                    
                    if es_pregunta_ia:
                        # Pregunta IA abierta — evaluar con IA
                        es_correcta, mensaje_respuesta = procesar_respuesta_abierta_ia(estudiante, msg_body)
                        modulo_completado = None
                    else:
                        es_correcta, mensaje_respuesta, modulo_completado = validar_respuesta(estudiante, msg_body)

                    # Obtener progreso para avanzar al siguiente módulo
                    if modulo_completado or es_pregunta_ia:
                        from ..helpers_examenes import puede_avanzar_modulo, es_modulo_checkpoint_reto_ia
                        
                        if modulo_completado:
                            progreso = modulo_completado.progreso
                            modulo_actual = modulo_completado.modulo
                        else:
                            # Para preguntas IA abierta, obtener progreso desde contexto
                            from ..models import ProgresoEstudiante, Modulo
                            modulo_id = ctx.get('modulo_id')
                            progreso_id = ctx.get('progreso_id')
                            try:
                                modulo_actual = Modulo.objects.get(id=modulo_id) if modulo_id else None
                                progreso = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
                            except Exception:
                                modulo_actual = None
                                progreso = None
                            
                            if progreso and modulo_actual:
                                # Crear ModuloCompletado para la pregunta IA abierta
                                modulo_abierto, created_abierto = ModuloCompletado.objects.get_or_create(
                                    progreso=progreso,
                                    modulo=modulo_actual
                                )
                                if created_abierto:
                                    progreso.fecha_ultimo_avance = timezone.now()
                                    progreso.save(update_fields=['fecha_ultimo_avance'])
                        
                        _skip_avance = False
                        if not (progreso and modulo_actual):
                            texto_respuesta = mensaje_respuesta
                            _skip_avance = True
                        
                        if not _skip_avance:
                            # VERIFICAR EXAMEN OBLIGATORIO ANTES DE AVANZAR
                            puede_avanzar, mensaje_examen, detalles = puede_avanzar_modulo(estudiante, modulo_actual)
                        
                            if not puede_avanzar:
                                # NO puede avanzar - examen obligatorio no aprobado
                                mensaje_respuesta += f"""


🔒 *Examen Obligatorio*

{mensaje_examen}

Para continuar al siguiente módulo debes aprobar el examen de este módulo.

Escribe *"examen"* cuando estés listo para intentarlo."""
                            
                                texto_respuesta = mensaje_respuesta
                                # Fall through to Twilio API send
                        
                            else:
                                from ..modulo_publicacion import (
                                    mensaje_bloqueo_sin_siguiente_publicado,
                                    siguiente_modulo_publicado_wa,
                                    total_modulos_publicados_wa,
                                )

                                from ..helpers_examenes import evaluar_checkpoint_reto_ia
                                from ..response_templates import (
                                    activar_checkpoint_facilitador,
                                )

                                total_modulos = total_modulos_publicados_wa(progreso.curso)
                                usar_agentes_ia_curso = bool(
                                    getattr(progreso.curso, 'usar_agentes_ia', True)
                                )
                                decision_cp = evaluar_checkpoint_reto_ia(
                                    modulo_actual,
                                    total_modulos,
                                    usar_agentes_ia_curso,
                                )
                                es_modulo_reto = decision_cp.es_reto
                                try:
                                    from core.eventos_ia import emit_checkpoint_evaluado

                                    emit_checkpoint_evaluado(
                                        decision_cp,
                                        estudiante=estudiante,
                                        curso=progreso.curso,
                                        modulo=modulo_actual,
                                        origen='pregunta_modulo',
                                    )
                                except Exception:
                                    pass

                                drip_bloqueado = False
                                _blk_pub_v = mensaje_bloqueo_sin_siguiente_publicado(
                                    estudiante, progreso, modulo_actual
                                )
                                if _blk_pub_v:
                                    # El siguiente módulo en borrador no tapa el checkpoint:
                                    # primero el reto, el bloqueo llega al cerrarlo.
                                    if es_modulo_reto:
                                        _dario_blk = activar_checkpoint_facilitador(
                                            estudiante, progreso, modulo_actual
                                        )
                                        texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(
                                            [mensaje_respuesta, _dario_blk]
                                        )
                                    else:
                                        texto_respuesta = f"{mensaje_respuesta}\n\n{_blk_pub_v}"
                                    drip_bloqueado = True
                                    siguiente_modulo = None
                                else:
                                    siguiente_modulo = siguiente_modulo_publicado_wa(
                                        progreso.curso, modulo_actual
                                    )

                                if siguiente_modulo:
                                    from ..drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

                                    _blk_v = mensaje_bloqueo_avance_siguiente_modulo(
                                        estudiante, progreso, modulo_actual
                                    )
                                    # Igual que en continuar_leccion: el drip no debe tapar el checkpoint IA.
                                    if _blk_v and not es_modulo_reto:
                                        texto_respuesta = f"{mensaje_respuesta}\n\n{_blk_v}"
                                        drip_bloqueado = True
                                        siguiente_modulo = None

                                if siguiente_modulo:
                                    _fcp = getattr(modulo_actual, 'facilitador_checkpoint', None)
                                    logger.info(
                                        '🎯 [checkpoint-pregunta-modulo] curso=%s mod_num=%s total_mod=%s '
                                        'usar_ia=%s facilitador_checkpoint=%s regla=%s -> es_reto=%s | est=%s',
                                        progreso.curso_id,
                                        getattr(modulo_actual, 'numero', None),
                                        total_modulos,
                                        usar_agentes_ia_curso,
                                        _fcp,
                                        decision_cp.regla_aplicada,
                                        es_modulo_reto,
                                        estudiante.id,
                                    )
                                    
                                    if not es_modulo_reto:
                                        # Normal: advance pointer
                                        progreso.modulo_actual = siguiente_modulo
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
                                    # else: pointer stays — will advance after reto
                                
                                    estudiante.preguntas_ia_restantes = 3
                                    estudiante.save()
                                
                                    porcentaje = progreso.porcentaje_avance()
                                    from ..response_templates import obtener_video_url
                                    video_url = obtener_video_url(siguiente_modulo)
                                
                                    archivos_multimedia = siguiente_modulo.archivos_multimedia.filter(activo=True)
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
                                
                                    msg_completado = mensaje_respuesta

                                    if es_modulo_reto:
                                        dario_msg = activar_checkpoint_facilitador(
                                            estudiante, progreso, modulo_actual
                                        )
                                        texto_respuesta = "[MULTI_MSG]" + "[SEP]".join([msg_completado, dario_msg])
                                    else:
                                        # v1.9.8i: Normal module — exam result + next module (no completado msg)
                                        estudiante.estado_onboarding = 'completado'
                                        estudiante.save()

                                        from ..module_steps import (
                                            entregar_bloque_secciones_desde_paso,
                                            modulo_usa_pasos,
                                            pasos_activos_qs,
                                            texto_legacy_whatsapp,
                                        )
                                        from ..avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo

                                        if modulo_usa_pasos(siguiente_modulo) and pasos_activos_qs(siguiente_modulo).exists():
                                            msg_pasos_n = entregar_bloque_secciones_desde_paso(
                                                progreso, siguiente_modulo, 1
                                            )
                                            inner_n = (
                                                msg_pasos_n[len('[MULTI_MSG]'):]
                                                if (msg_pasos_n or '').startswith('[MULTI_MSG]')
                                                else (msg_pasos_n or '')
                                            )
                                            partes = [msg_completado] + [p for p in inner_n.split('[SEP]') if p]
                                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)
                                        else:
                                            _leg = texto_legacy_whatsapp(siguiente_modulo)
                                            msg_modulo = (
                                                f"📖 *Módulo {siguiente_modulo.numero}: {siguiente_modulo.titulo}*\n\n"
                                                f"{siguiente_modulo.descripcion}\n\n{_leg}"
                                            )
                                            if siguiente_modulo.examen_obligatorio:
                                                msg_modulo += (
                                                    f"\n\n⚠️ *Este módulo tiene examen obligatorio "
                                                    f"({siguiente_modulo.puntaje_minimo_aprobacion}% para aprobar)*"
                                                )
                                            partes = [msg_completado, msg_modulo]
                                            hay_media_exam = False
                                            if primera_media_url:
                                                partes.append(parte_mensaje_con_media(primera_media_url))
                                                hay_media_exam = True
                                            for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
                                                partes.append(parte_mensaje_con_media(extra_url))
                                                hay_media_exam = True
                                            if hay_media_exam:
                                                partes.append("[DELAY:5]")
                                            partes.append(
                                                resolver_cta_listo(
                                                    estudiante, progreso.curso, CTX_FIN_ENTREGA_MODULO
                                                )
                                            )
                                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)

                                elif not drip_bloqueado:
                                    # Completó todos los módulos
                                    progreso.completado = True
                                    progreso.fecha_completado = timezone.now()
                                    progreso.save()
                                
                                    # === v1.9.8h: RETO FINAL en lugar de pregunta de recuperación ===
                                    _skip_cert = False
                                    pregunta_abierta = _pregunta_abierta_final_pendiente(estudiante, progreso)
                                    usar_gamificacion_final = bool(
                                        progreso.curso.usar_gamificacion or
                                        (estudiante.cliente.usar_gamificacion if getattr(estudiante, 'cliente', None) else False)
                                    )
                                    usar_agentes_ia_final = bool(getattr(progreso.curso, 'usar_agentes_ia', True))
                                    # Reto final solo si el curso usa gamificación Y agentes IA.
                                    activar_reto_final = usar_gamificacion_final and usar_agentes_ia_final

                                    if activar_reto_final:
                                        try:
                                            nombre_tutor_final = progreso.curso.nombre_agente_tutor or 'Claudia'
                                            nombre_asist_final = progreso.curso.nombre_agente_asistente or 'Darío'
                                            modulos_all = list(progreso.curso.modulos.filter(numero__gte=4).order_by('numero'))
                                            if not modulos_all:
                                                modulos_all = list(progreso.curso.modulos.all().order_by('numero'))
                                            modulos_final_range = "los módulos finales del curso"
                                            if len(modulos_all) >= 2:
                                                modulos_final_range = f"los módulos {modulos_all[0].numero} a {modulos_all[-1].numero}"

                                            _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                                            estudiante.contexto_temporal = {
                                                'tipo': 'asistente_dario',
                                                'curso_activo_id': progreso.curso_id,
                                                'curso_id': progreso.curso.id,
                                                'modulo_id': modulo_actual.id,
                                                'progreso_id': progreso.id,
                                                'modulos_reto_ids': [m.id for m in modulos_all],
                                                'preguntas_hechas': 0,
                                                'es_reto_final': True,
                                                '_ts_leccion': _prev_ts,
                                            }
                                            if pregunta_abierta:
                                                estudiante.contexto_temporal['pregunta_abierta_final_id'] = pregunta_abierta.id
                                            estudiante.estado_onboarding = 'esperando_respuesta_asistente'
                                            estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

                                            from core.agentes_whatsapp import mensaje_con_titular_agente

                                            texto_respuesta = (
                                                f"{mensaje_respuesta}\n\n"
                                                f"🎉 *¡Completaste todos los módulos del curso!*\n\n"
                                                + mensaje_con_titular_agente(
                                                    nombre_asist_final,
                                                    (
                                                        f"Antes de tu certificado, {nombre_tutor_final} te planteará un reto final sobre {modulos_final_range}.\n\n"
                                                        "¿Tienes dudas antes del reto?\n"
                                                        "Ejemplos:\n"
                                                        "• ¿Cómo diferencio un daño leve de uno económico?\n"
                                                        "• ¿Qué paso práctico recomienda para validar en campo?\n"
                                                        "• ¿Qué indicador debo monitorear cada semana?\n\n"
                                                        "Envíame tu pregunta (texto o audio).\n"
                                                        "Si no tienes dudas, escribe *listo* para pasar con la facilitadora."
                                                    ),
                                                )
                                            )
                                            logger.info(
                                                f"🎯 Reto final activado | estudiante_id={estudiante.id} | curso_id={progreso.curso.id} | "
                                                f"curso_usar_gamificacion={bool(progreso.curso.usar_gamificacion)} | "
                                                f"cliente_usar_gamificacion={bool(estudiante.cliente.usar_gamificacion) if getattr(estudiante, 'cliente', None) else False} | "
                                                f"pregunta_abierta_id={getattr(pregunta_abierta, 'id', None)}"
                                            )
                                            _skip_cert = True
                                        except Exception as e:
                                            logger.warning(f"⚠️ Reto final exam: {e}")
                                    
                                    if not _skip_cert:
                                        if pregunta_abierta:
                                            estudiante.contexto_temporal = {
                                                'tipo': 'pregunta_abierta_final',
                                                'curso_id': progreso.curso.id,
                                                'progreso_id': progreso.id,
                                                'pregunta_abierta_final_id': pregunta_abierta.id,
                                            }
                                            estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
                                            estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                                            texto_respuesta = (
                                                f"{mensaje_respuesta}\n\n"
                                                "📝 *Antes del cierre final*, responde esta pregunta abierta:\n\n"
                                                f"{pregunta_abierta.pregunta}\n\n"
                                                "✍️ Tu facilitadora revisará y calificará tu respuesta."
                                            )
                                        else:
                                            estudiante.estado_onboarding = 'curso_finalizado'
                                            estudiante.save(update_fields=['estado_onboarding'])

                                            msg_final = (
                                                f"{mensaje_respuesta}\n\n"
                                                f"🎓 *¡FELICITACIONES!*\n\n"
                                                f"Ha completado el curso: *{progreso.curso.nombre}*\n\n"
                                                f"🏆 Su certificado se está generando..."
                                            )

                                            msg_cert_img = ""
                                            try:
                                                from ..certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
                                                logger.info(f"🎓 Iniciando generación de certificado para {estudiante.nombre} - {progreso.curso.nombre}")
                                                cert = crear_certificado_automatico(estudiante, progreso.curso)
                                                logger.info(f"🎓 Certificado resultado: cert={cert}, imagen={cert.archivo_imagen if cert else 'N/A'}, pdf={cert.archivo_pdf if cert else 'N/A'}")
                                            
                                                if cert and cert.archivo_imagen:
                                                    cert_url = obtener_url_certificado_twilio(cert)
                                                    if cert_url:
                                                        msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                                        logger.info(f"✅ Certificado URL para Twilio: {cert_url}")
                                                    else:
                                                        s3_key = str(cert.archivo_imagen.name)
                                                        cert_url = f"https://eki-produccion.s3.us-east-2.amazonaws.com/{s3_key}"
                                                        msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                                        logger.info(f"✅ Certificado URL fallback: {cert_url}")
                                                elif cert and cert.archivo_pdf:
                                                    cert_url = cert.archivo_pdf.url
                                                    msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert_url}"
                                                    logger.info(f"📄 Certificado PDF URL: {cert_url}")
                                                elif cert:
                                                    logger.warning(f"⚠️ Cert creado sin archivo, forzando regeneración...")
                                                    from ..certificado_service import generar_y_guardar_certificado
                                                    generar_y_guardar_certificado(cert, force=True)
                                                    cert.refresh_from_db()
                                                    if cert.archivo_imagen:
                                                        cert_url = obtener_url_certificado_twilio(cert)
                                                        if cert_url:
                                                            msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                                            logger.info(f"✅ Certificado PRESIGNED URL (retry): {cert_url[:100]}...")
                                                        else:
                                                            msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                                                    else:
                                                        msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                                                else:
                                                    msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                                                    logger.warning(f"❌ crear_certificado_automatico retornó None para {estudiante.nombre}")
                                            except Exception as e:
                                                logger.error(f"❌ Error generando certificado: {e}", exc_info=True)
                                                import traceback; traceback.print_exc()
                                                msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."

                                            # Radar/empleabilidad pausado: no envía Subachoque.
                                            radar_msg = _radar_msg_si_aplica(estudiante)

                                            partes = [msg_final]
                                            if radar_msg:
                                                partes.append(radar_msg)
                                            partes.append(msg_cert_img)
                                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)
                    
                    # El default «No entendí» se asigna antes de esta rama.
                    # Opción inválida / error de contexto deben ganar.
                    if (
                        not texto_respuesta
                        or texto_respuesta.startswith('No entendí. Si quieres avanzar')
                    ):
                        texto_respuesta = mensaje_respuesta
                    print(f"✅ Respuesta validada: {'Correcta' if es_correcta else 'Incorrecta'}")
            
            # 3.5c PRIORIDAD: Si está seleccionando un curso de la lista
            # (B2B con 2+ cursos también elige por número aquí)
            elif estudiante.estado_onboarding == 'esperando_seleccion_curso':
                msg_sel = msg_body.strip().lower()
                if msg_sel in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    from ..response_templates import get_response_for_intent
                    texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                else:
                    import re as re_curso_sel
                    indice_sel = None
                    match_tomar_sel = re_curso_sel.match(r'^tomar\s*(\d+)$', msg_sel)
                    if match_tomar_sel:
                        indice_sel = int(match_tomar_sel.group(1))
                    elif msg_body.strip().isdigit():
                        indice_sel = int(msg_body.strip())
                    if indice_sel is not None:
                        from ..selector_curso import continuar_curso_seleccionado
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save(update_fields=['estado_onboarding'])
                        texto_respuesta = continuar_curso_seleccionado(estudiante.id, indice_sel, msg_body)
                        print(f"✅ Curso seleccionado: {indice_sel}")
                    else:
                        # Si no es número/tomar ni menú, resetear estado y procesar normalmente
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
                            texto_respuesta = "No entendí tu selección. Escribe *menú* para ver las opciones."
            
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


def _procesar_meta_webhook(payload):
    """Procesa webhooks de Meta WhatsApp (mantiene compatibilidad)"""
    try:
        print("🔵 META: Procesando...")
        entries = payload.get('entry', [])
        
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                meta_to = (
                    (value.get('metadata') or {}).get('display_phone_number')
                    or (value.get('metadata') or {}).get('phone_number_id')
                    or ''
                )
                
                # Mensajes entrantes
                messages = value.get('messages', [])
                for m in messages:
                    phone = m.get('from')
                    msg_id = m.get('id')
                    text = ''
                    if 'text' in m and isinstance(m['text'], dict):
                        text = m['text'].get('body', '')
                    
                    # Guardar mensaje
                    WhatsappLog.objects.create(
                        telefono=phone,
                        mensaje=text,
                        mensaje_id=msg_id,
                        tipo='INCOMING'
                    )
                    
                    # Obtener o crear estudiante
                    estudiante, _ = Estudiante.objects.get_or_create(
                        telefono=phone,
                        defaults={'nombre': 'Usuario', 'activo': True, 'cedula': f'META_{phone[-10:]}'}
                    )
                    
                    # Verificar seguridad primero
                    from ..security_handler import verificar_seguridad_completa
                    bloqueado, respuesta_seguridad, estudiante = verificar_seguridad_completa(
                        estudiante,
                        text,
                        telefono=phone,
                        numero_destino=meta_to,
                    )
                    
                    if bloqueado:
                        texto_respuesta = respuesta_seguridad
                    else:
                        # Detectar intent
                        intent = detect_intent(text)
                        
                        if intent != 'desconocido':
                            # Usar template
                            texto_respuesta = get_response_for_intent(
                                intent, 
                                estudiante.nombre,
                                estudiante_id=estudiante.id,
                                mensaje_original=text
                            )
                        else:
                            # Usar IA solo para preguntas
                            try:
                                from ..ai_assistant import responder_con_ia
                                texto_respuesta = responder_con_ia(text, phone)
                            except Exception as e:
                                print(f"Error IA: {e}")
                                texto_respuesta = "Disculpa, tengo problemas técnicos. Vuelve a escribir tu mensaje para continuar."
                    
                    # Enviar respuesta
                    resultado_envio = enviar_whatsapp(phone, texto_respuesta)
                    
                    if resultado_envio.get('success'):
                        WhatsappLog.objects.create(
                            telefono=phone,
                            mensaje=texto_respuesta,
                            mensaje_id=resultado_envio.get('mensaje_id'),
                            tipo='SENT'
                        )
    
    except Exception as e:
        print(f"❌ Error en _procesar_meta_webhook: {str(e)}")
        import traceback
        traceback.print_exc()






