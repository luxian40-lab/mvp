"""
Entrega de media WhatsApp: reintento automático ante 63019/63021/63005,
estado de paquete y métricas ops.

No cambia el formato de envío del curso: reintenta el mismo MediaUrl
(preparado de nuevo) sin meter links S3 en el cuerpo.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

_RETRY_RE = re.compile(r'RETRY:(\d+)', re.I)

MAX_VIDEO_MB_3G = 25.0
MAX_AUDIO_MB_3G = 10.0
MAX_IMAGE_MB_3G = 5.0
MAX_VIDEO_SEGUNDOS_3G = 180


def _max_reintentos() -> int:
    try:
        return max(0, min(int(getattr(settings, 'MEDIA_REINTENTOS_AUTO', 2) or 2), 5))
    except (TypeError, ValueError):
        return 2


def _max_video_mb() -> float:
    try:
        return float(getattr(settings, 'MEDIA_MAX_VIDEO_MB_3G', MAX_VIDEO_MB_3G) or MAX_VIDEO_MB_3G)
    except (TypeError, ValueError):
        return MAX_VIDEO_MB_3G


def contar_reintentos_en_log(log) -> int:
    detalle = getattr(log, 'error_detalle', None) or ''
    nums = [int(m) for m in _RETRY_RE.findall(detalle)]
    return max(nums) if nums else 0


def marcar_reintento_en_log(log, n: int, error_code: str = '') -> None:
    prev = (log.error_detalle or '').strip()
    limpio = _RETRY_RE.sub('', prev).strip(' |')
    parts = [p for p in (limpio, f'RETRY:{n}', error_code or '') if p]
    log.error_detalle = ' | '.join(parts)[:2000]
    log.save(update_fields=['error_detalle'])


def _ya_notificado_ops(log) -> bool:
    return 'NOTIFIED_OPS' in (getattr(log, 'error_detalle', None) or '')


def _marcar_notificado_ops(log) -> None:
    prev = (log.error_detalle or '').strip()
    if 'NOTIFIED_OPS' in prev:
        return
    log.error_detalle = (f'{prev} | NOTIFIED_OPS'.strip(' |'))[:2000]
    log.save(update_fields=['error_detalle'])


def notificar_fallo_media_ops(log, error_code: str = '', intentos: int = 0) -> None:
    """
    Alerta ops (Slack + email) cuando media WhatsApp queda fallida tras reintentos.
    Idempotente por WhatsappLog (marcador NOTIFIED_OPS).
    """
    if _ya_notificado_ops(log):
        return

    from core.twilio_media import extraer_media_url_de_mensaje

    tel = (getattr(log, 'telefono', None) or '').strip()
    sid = (getattr(log, 'mensaje_id', None) or '').strip()
    code = str(error_code or '').strip()
    media_url = extraer_media_url_de_mensaje(getattr(log, 'mensaje', '') or '') or ''
    media_corta = (media_url[:120] + '…') if len(media_url) > 120 else media_url

    titulo = f'Media WA fallida {code or "?"} · {tel or "sin tel"}'
    cuerpo = (
        f'Teléfono: {tel}\n'
        f'Código Twilio: {code}\n'
        f'Intentos auto: {intentos}\n'
        f'MessageSid: {sid}\n'
        f'Media: {media_corta or "(sin URL en log)"}\n'
        f'Admin triage: /admin/core/whatsapplog/?codigo_twilio={code or "fallos"}\n'
        f'Paquetes: /admin/core/mediapaqueteentrega/?estado__exact=fallido\n'
        f'63021 = codec/formato video (H.264+AAC). 63019 = URL/MIME/download.'
    )

    try:
        from core.ops_slack import notify_slack_ops

        notify_slack_ops(cuerpo, title=titulo)
    except Exception as exc:
        logger.warning('Slack media-fail notify: %s', exc)

    try:
        from django.conf import settings
        from django.core.mail import send_mail

        destino = (
            getattr(settings, 'EMAIL_SOPORTE', None)
            or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
            or ''
        )
        if destino and getattr(settings, 'EKI_MEDIA_FAIL_EMAIL', True):
            send_mail(
                subject=f'[eki ops] {titulo}',
                message=cuerpo,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=[destino] if isinstance(destino, str) else list(destino),
                fail_silently=True,
            )
    except Exception as exc:
        logger.warning('Email media-fail notify: %s', exc)

    try:
        _marcar_notificado_ops(log)
    except Exception:
        pass


def reintentar_media_desde_log(log, error_code: str = '') -> bool:
    """
    Reenvía el mismo adjunto 1–MAX veces tras fallo async de Twilio.
    Returns True si Twilio aceptó el reintento.
    """
    from core.twilio_media import (
        es_error_media_twilio,
        extraer_media_url_de_mensaje,
        mensaje_log_con_media,
        normalizar_media_url_s3,
        preparar_url_media_whatsapp,
    )

    if not es_error_media_twilio(error_code):
        return False

    ya = contar_reintentos_en_log(log)
    max_r = _max_reintentos()
    if ya >= max_r:
        logger.info(
            '📎 Media: sin más reintentos auto | sid=%s intentos=%s',
            getattr(log, 'mensaje_id', ''),
            ya,
        )
        _upsert_paquete_desde_log(log, estado='fallido', error_code=error_code, intentos=ya)
        notificar_fallo_media_ops(log, error_code=error_code, intentos=ya)
        return False

    media_url = extraer_media_url_de_mensaje(getattr(log, 'mensaje', '') or '')
    if not media_url:
        logger.warning('📎 Media fallida sin [MEDIA:] en log sid=%s', getattr(log, 'mensaje_id', ''))
        _upsert_paquete_desde_log(log, estado='fallido', error_code=error_code, intentos=ya)
        notificar_fallo_media_ops(log, error_code=error_code, intentos=ya)
        return False

    n = ya + 1
    marcar_reintento_en_log(log, n, error_code)

    try:
        from core.utils import enviar_whatsapp_twilio

        url = normalizar_media_url_s3(media_url) or media_url
        try:
            url = preparar_url_media_whatsapp(url) or url
        except Exception as prep_err:
            logger.warning('📎 preparar_url_media_whatsapp: %s', prep_err)

        cuerpo = (
            '📡 Reenviamos el material del módulo (hubo un fallo de red). '
            'Si no lo ve, escriba *reenvía video*.'
        )
        res = enviar_whatsapp_twilio(
            telefono=log.telefono,
            texto=cuerpo,
            media_url=url,
            texto_log=mensaje_log_con_media(cuerpo, url),
        )
        ok = bool(res.get('success'))
        if ok:
            logger.info(
                '📎 Media reintento %s/%s OK | tel=%s sid_orig=%s',
                n,
                max_r,
                log.telefono,
                getattr(log, 'mensaje_id', ''),
            )
            _upsert_paquete_desde_log(
                log, estado='enviado', error_code=error_code, intentos=n,
            )
        else:
            logger.warning('📎 Media reintento %s falló | %s', n, res.get('response'))
            _upsert_paquete_desde_log(
                log, estado='fallido', error_code=error_code, intentos=n,
            )
            if n >= max_r:
                notificar_fallo_media_ops(log, error_code=error_code, intentos=n)
        return ok
    except Exception as e:
        logger.error('📎 Error reintento media: %s', e, exc_info=True)
        _upsert_paquete_desde_log(log, estado='fallido', error_code=error_code, intentos=n)
        notificar_fallo_media_ops(log, error_code=error_code, intentos=n)
        return False


def marcar_paquete_recuperado_por_telefono(telefono: str) -> int:
    from core.models_media_entrega import MediaPaqueteEntrega

    qs = list(
        MediaPaqueteEntrega.objects.filter(
            telefono=telefono,
            estado='fallido',
        ).order_by('-actualizado_en')[:5]
    )
    n = 0
    for p in qs:
        p.estado = 'recuperado'
        p.save(update_fields=['estado', 'actualizado_en'])
        n += 1
    return n


def _upsert_paquete_desde_log(log, *, estado: str, error_code: str = '', intentos: int = 0):
    from core.models_media_entrega import MediaPaqueteEntrega
    from core.twilio_media import extraer_media_url_de_mensaje

    media_url = extraer_media_url_de_mensaje(getattr(log, 'mensaje', '') or '') or ''
    est = getattr(log, 'estudiante', None)
    tel = (getattr(log, 'telefono', None) or '').strip()
    if not tel:
        return

    obj = None
    if getattr(log, 'pk', None):
        obj = MediaPaqueteEntrega.objects.filter(whatsapp_log_id=log.pk).first()
    if obj is None and media_url:
        obj = (
            MediaPaqueteEntrega.objects.filter(telefono=tel, media_url=media_url)
            .order_by('-id')
            .first()
        )
    if obj is None:
        obj = MediaPaqueteEntrega(
            telefono=tel,
            estudiante=est,
            whatsapp_log=log if getattr(log, 'pk', None) else None,
            media_url=media_url[:2000],
        )
    obj.estado = estado
    obj.intentos = max(obj.intentos or 0, intentos)
    if error_code:
        obj.error_code = str(error_code)[:20]
    if est and not obj.estudiante_id:
        obj.estudiante = est
    if getattr(log, 'pk', None):
        obj.whatsapp_log = log
    obj.save()


def metricas_media_cliente(cliente, dias: int = 30) -> dict:
    from core.models import Estudiante, WhatsappLog

    dias = max(1, min(int(dias or 30), 180))
    desde = timezone.now() - timedelta(days=dias)
    tels = list(
        Estudiante.objects.filter(cliente=cliente)
        .exclude(telefono='')
        .values_list('telefono', flat=True)[:5000]
    )
    if not tels:
        return {
            'dias': dias,
            'con_media': 0,
            'entregados': 0,
            'fallidos': 0,
            'pct_fallo': 0.0,
            'por_error': [],
        }

    base = WhatsappLog.objects.filter(
        tipo='SENT',
        fecha__gte=desde,
        telefono__in=tels,
        mensaje__contains='[MEDIA:',
    )
    con_media = base.count()
    entregados = base.filter(estado__in=('DELIVERED', 'READ', 'RECEIVED')).count()
    fallidos = base.filter(estado__in=('UNDELIVERED', 'FAILED')).count()
    denom = entregados + fallidos
    pct = round(100.0 * fallidos / denom, 1) if denom else 0.0

    por_error = list(
        base.filter(estado__in=('UNDELIVERED', 'FAILED'))
        .values('error_detalle')
        .annotate(n=Count('id'))
        .order_by('-n')[:8]
    )
    codes: dict[str, int] = {}
    for row in por_error:
        det = row.get('error_detalle') or ''
        code = 'otro'
        for c in ('63019', '63021', '63005'):
            if c in det:
                code = c
                break
        codes[code] = codes.get(code, 0) + row['n']

    return {
        'dias': dias,
        'con_media': con_media,
        'entregados': entregados,
        'fallidos': fallidos,
        'pct_fallo': pct,
        'por_error': [
            {'codigo': k, 'n': v}
            for k, v in sorted(codes.items(), key=lambda x: -x[1])
        ],
    }


def avisos_formato_3g(
    *,
    nombre_archivo: str = '',
    size_bytes: Optional[int] = None,
    content_type: str = '',
    duracion_segundos: Optional[float] = None,
) -> list[str]:
    """Avisos de política 3G (nunca bloquean)."""
    avisos: list[str] = []
    name = (nombre_archivo or '').lower()
    ctype = (content_type or '').lower()
    mb = (size_bytes or 0) / (1024 * 1024) if size_bytes else 0

    es_video = ctype.startswith('video/') or name.endswith(('.mp4', '.mov', '.3gp', '.webm'))
    es_audio = ctype.startswith('audio/') or name.endswith(('.mp3', '.ogg', '.m4a', '.aac', '.wav'))
    es_img = ctype.startswith('image/') or name.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))

    if es_video and mb > _max_video_mb():
        avisos.append(
            f'Video ~{mb:.1f} MB supera el recomendado para 3G ({_max_video_mb():.0f} MB). '
            'Puede fallar en campo (63019). Comprima o recorte.'
        )
    if es_audio and mb > MAX_AUDIO_MB_3G:
        avisos.append(
            f'Audio ~{mb:.1f} MB supera el recomendado ({MAX_AUDIO_MB_3G:.0f} MB) para 3G.'
        )
    if es_img and mb > MAX_IMAGE_MB_3G:
        avisos.append(
            f'Imagen ~{mb:.1f} MB supera el recomendado ({MAX_IMAGE_MB_3G:.0f} MB).'
        )
    if es_video and duracion_segundos and duracion_segundos > MAX_VIDEO_SEGUNDOS_3G:
        avisos.append(
            f'Video de {int(duracion_segundos)}s supera ~{MAX_VIDEO_SEGUNDOS_3G}s recomendados en 3G.'
        )
    if es_video and name.endswith('.mov'):
        avisos.append('Preferir MP4 (H.264) frente a MOV para WhatsApp/3G.')
    return avisos
