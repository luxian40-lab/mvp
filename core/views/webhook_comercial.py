import json

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from core.bot_comercial.webhook import _procesar_bot_comercial_twilio_webhook

# legacy lo sustituye al cargar webhook_meta (la llamada vive en este módulo).
_aplicar_sandbox_menu = None

from .legacy import logger
from .twilio_transporte import (
    _es_status_callback_twilio,
    _twilio_post_plano,
)

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

@csrf_exempt
def bot_comercial_webhook(request):
    """Webhook dedicado para el número de WhatsApp del bot comercial."""
    if request.method != 'POST':
        return HttpResponse('Method Not Allowed', status=405)

    from core.twilio_webhook_security import validate_twilio_request

    denied = validate_twilio_request(request)
    if denied is not None:
        return denied

    from core.conversacion.bandeja_entrada import anotar_payload_twilio, aplicar_con_turno, omitir_turno
    from core.nati import normalizar_telefono_whatsapp
    from core.webhook_evento import CANAL_TWILIO

    def _sid(data):
        return str(data.get('MessageSid') or '').strip()[:128]

    def _tel(data):
        return normalizar_telefono_whatsapp(str(data.get('From') or '')) or 'sin-telefono'

    try:
        try:
            payload = json.loads(request.body.decode('utf-8'))
            anotar_payload_twilio(payload)
            sb = _aplicar_sandbox_menu(payload)
            if sb is not None:
                omitir_turno(CANAL_TWILIO, _sid(payload))
                return sb
            if not _encolar_bot_comercial_si_async(payload, forzar_canal=True):
                aplicar_con_turno(
                    CANAL_TWILIO,
                    _sid(payload),
                    _tel(payload),
                    lambda: _procesar_bot_comercial_twilio_webhook(payload, forzar_canal=True),
                )
        except json.JSONDecodeError:
            anotar_payload_twilio(request.POST)
            sb = _aplicar_sandbox_menu(request.POST)
            if sb is not None:
                omitir_turno(CANAL_TWILIO, _sid(request.POST))
                return sb
            if not _encolar_bot_comercial_si_async(request.POST, forzar_canal=True):
                aplicar_con_turno(
                    CANAL_TWILIO,
                    _sid(request.POST),
                    _tel(request.POST),
                    lambda: _procesar_bot_comercial_twilio_webhook(request.POST, forzar_canal=True),
                )
        return HttpResponse('OK')
    except Exception as e:
        logger.error(f"❌ Error webhook bot comercial: {e}")
        return HttpResponse('Error', status=500)
