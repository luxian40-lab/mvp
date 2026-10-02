import logging

from django.conf import settings

from ..models import WhatsappLog
from ..response_templates import MENSAJE_CAPTION_SOLO_MEDIA as TWILIO_CAPTION_ADJUNTO

logger = logging.getLogger(__name__)

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
