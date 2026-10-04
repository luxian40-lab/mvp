import logging

from django.conf import settings
from django.http import HttpResponse

from ..intent_detector import detect_intent
from ..models import Estudiante, WhatsappLog
from ..response_templates import get_response_for_intent
from ..utils import enviar_whatsapp

logger = logging.getLogger(__name__)

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
    """Una tarea Celery por mensaje si SANDBOX_CELERY_ASYNC=true.

    Si Redis no acepta la tarea, la excepción sube. El webhook conserva
    los reclamos ya encolados, suelta el que falló y los que no alcanzó
    a encolarse, y responde 500. No hay fallback síncrono.
    """
    if not getattr(settings, 'SANDBOX_CELERY_ASYNC', False):
        return False
    from core.tasks import procesar_sandbox_meta_async

    procesar_sandbox_meta_async.delay(dict(inbound))
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

            try:
                if not _encolar_bot_comercial_si_async(data, forzar_canal=True):
                    _procesar_bot_comercial_twilio_webhook(data, forzar_canal=True)
            except Exception:
                logger.exception('sandbox_nat_proceso_fail')
                try:
                    from core.nati import normalizar_telefono_whatsapp
                    from core.sandbox_menu import enviar_texto_sandbox

                    tel = normalizar_telefono_whatsapp(str(data.get('From') or ''))
                    destino = str(data.get('To') or sandbox_number())
                    if tel:
                        enviar_texto_sandbox(
                            tel,
                            destino,
                            "Nat no pudo completar esa consulta. "
                            "Escriba de nuevo la pregunta, o *menu* para volver.\n\n"
                            "_*menu* para el menú principal._",
                            agente='sandbox_nat',
                        )
                except Exception:
                    logger.exception('sandbox_nat_fallback_fail')
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
                    
                    from core.linea_registrados import (
                        TEXTO_SOLO_REGISTRADOS,
                        debe_cortar,
                        permitir_numero_nuevo,
                    )

                    if not Estudiante.objects.filter(telefono=phone).exists() and (
                        debe_cortar(phone) or not permitir_numero_nuevo(phone)
                    ):
                        enviar_whatsapp(phone, TEXTO_SOLO_REGISTRADOS)
                        continue

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

from .twilio_transporte import _encolar_twilio_edu_si_async
from .webhook_comercial import _encolar_bot_comercial_si_async
from .webhook_twilio import _procesar_twilio_webhook
