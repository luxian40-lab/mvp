import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook

from .twilio_transporte import _encolar_twilio_edu_si_async
from .webhook_comercial import _encolar_bot_comercial_si_async
from .webhook_meta import (
    _aplicar_sandbox_menu,
    _encolar_sandbox_si_async,
    _procesar_meta_webhook,
    _sandbox_inbound_repetido,
)
from .webhook_twilio import _procesar_twilio_webhook

logger = logging.getLogger(__name__)

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
