import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook

from core.webhook_evento import (
    CANAL_META,
    CANAL_TWILIO,
    firma_meta_invalida,
    liberar_eventos,
    preparar_payload_meta,
    reclamar_twilio,
)

from .twilio_transporte import _encolar_twilio_edu_si_async, _es_status_callback_twilio
from .webhook_comercial import _encolar_bot_comercial_si_async
from .webhook_meta import (
    _aplicar_sandbox_menu,
    _encolar_sandbox_si_async,
    _procesar_meta_webhook,
    _sandbox_inbound_repetido,
)
from .webhook_twilio import _procesar_twilio_webhook

logger = logging.getLogger(__name__)


def _sid_de(data) -> str:
    return str((data or {}).get('MessageSid') or '').strip()[:128]


def _error_sincronico(canal, external_id):
    """La lógica de negocio ya arrancó: el reclamo se queda."""
    logger.error(
        'webhook_proceso_sincrono canal=%s external_id=%s',
        canal,
        external_id,
    )
    return HttpResponse('Error', status=500)


def _error_encolado(canal, external_ids):
    """Redis no aceptó la tarea: se suelta el reclamo para que el proveedor reintente."""
    logger.exception(
        'webhook_encolar_fail canal=%s external_ids=%s',
        canal,
        list(external_ids or []),
    )
    liberar_eventos(canal, external_ids)
    return HttpResponse('Error', status=500)


def _payload_un_mensaje(payload, message_id: str) -> dict:
    import copy

    clon = copy.deepcopy(payload)
    for entry in clon.get('entry') or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get('changes') or []:
            if not isinstance(change, dict):
                continue
            value = change.get('value')
            if not isinstance(value, dict) or 'messages' not in value:
                continue
            value['messages'] = [
                mensaje
                for mensaje in (value.get('messages') or [])
                if isinstance(mensaje, dict)
                and str(mensaje.get('id') or '').strip()[:128] == message_id
            ]
    return clon


def _procesar_meta_por_mensaje(payload):
    """Cada mensaje se encola o se procesa solo. Un fallo no suelta los anteriores."""
    from core.sandbox_canal import iter_mensajes_inbound_meta, sandbox_via_meta
    from core.sandbox_menu import es_destino_sandbox

    inbounds = list(iter_mensajes_inbound_meta(payload))
    if not inbounds:
        _procesar_meta_webhook(payload)
        return None

    def _posteriores(desde: int) -> list[str]:
        return [_sid_de(inbounds[j]) for j in range(desde, len(inbounds)) if _sid_de(inbounds[j])]

    if sandbox_via_meta() and any(es_destino_sandbox(item) for item in inbounds):
        last_sb = None
        for indice, inbound in enumerate(inbounds):
            if not es_destino_sandbox(inbound):
                continue
            sid = _sid_de(inbound)
            if _sandbox_inbound_repetido(inbound):
                continue
            try:
                encolado = _encolar_sandbox_si_async(inbound)
            except Exception:
                return _error_encolado(CANAL_META, [sid, *_posteriores(indice + 1)])
            if encolado:
                continue
            try:
                last_sb = _aplicar_sandbox_menu(inbound)
            except Exception:
                liberar_eventos(CANAL_META, _posteriores(indice + 1))
                return _error_sincronico(CANAL_META, sid)
        if isinstance(last_sb, HttpResponse):
            return last_sb
        return HttpResponse('OK')

    for indice, inbound in enumerate(inbounds):
        sid = _sid_de(inbound)
        try:
            _procesar_meta_webhook(_payload_un_mensaje(payload, sid) if sid else payload)
        except Exception:
            liberar_eventos(CANAL_META, _posteriores(indice + 1))
            return _error_sincronico(CANAL_META, sid)
    return None


def _procesar_twilio_reclamado(data, ids, es_comercial):
    sid = ids[0] if ids else _sid_de(data)
    try:
        sb = _aplicar_sandbox_menu(data)
    except Exception:
        return _error_sincronico(CANAL_TWILIO, sid)
    if sb is not None:
        return sb
    try:
        if es_comercial(data):
            encolado = _encolar_bot_comercial_si_async(data)
        else:
            encolado = _encolar_twilio_edu_si_async(data)
    except Exception:
        return _error_encolado(CANAL_TWILIO, ids or ([sid] if sid else []))
    if encolado:
        return None
    try:
        if es_comercial(data):
            logger.info("🧭 Router webhook: Twilio destino comercial/agro detectado")
            _procesar_bot_comercial_twilio_webhook(data)
            return None
        logger.info("🧭 Router webhook: Twilio destino educativo detectado")
        return _procesar_twilio_webhook(data)
    except Exception:
        return _error_sincronico(CANAL_TWILIO, sid)


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
                if firma_meta_invalida(
                    raw_body,
                    request.META.get('HTTP_X_HUB_SIGNATURE_256', ''),
                ):
                    logger.warning('meta_webhook_firma_invalida')
                    return HttpResponse('Forbidden', status=403)
                payload, ids_meta, seguir = preparar_payload_meta(payload)
                if not seguir:
                    return HttpResponse('OK')

                try:
                    from core.meta_waba import aplicar_eventos_plantilla

                    aplicar_eventos_plantilla(
                        payload,
                        raw_body,
                        request.META.get('HTTP_X_HUB_SIGNATURE_256', ''),
                    )
                except Exception:
                    logger.exception('meta_template_status_update_fail')
                resultado_meta = _procesar_meta_por_mensaje(payload)
                if isinstance(resultado_meta, HttpResponse):
                    return resultado_meta
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
                    seguir_tw, ids_tw = reclamar_twilio(
                        payload,
                        es_status=_es_status_callback_twilio(payload),
                    )
                    if not seguir_tw:
                        return HttpResponse('OK')

                    resultado_tw = _procesar_twilio_reclamado(
                        payload, ids_tw, _es_destino_bot_comercial,
                    )
                    if isinstance(resultado_tw, HttpResponse):
                        return resultado_tw
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
            seguir_tw, ids_tw = reclamar_twilio(
                request.POST,
                es_status=_es_status_callback_twilio(request.POST),
            )
            if not seguir_tw:
                return HttpResponse('OK')

            twilio_result = _procesar_twilio_reclamado(
                request.POST, ids_tw, _es_destino_bot_comercial,
            )
            if isinstance(twilio_result, HttpResponse):
                return twilio_result
        
        except Exception as e:
            print(f"❌ Error en webhook: {str(e)}", flush=True)
            logger.error(f"❌ Error en webhook: {str(e)}")
            import traceback
            traceback.print_exc()
            return HttpResponse('Error', status=500)

        return HttpResponse('OK')
