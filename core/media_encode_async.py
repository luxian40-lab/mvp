"""Subida async de video admin: S3 incoming → Celery ffmpeg → PasoModulo."""
from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

CACHE_TTL = 7200


def media_encode_job_key(job_id: str) -> str:
    return f'media_encode_job:{job_id}'


def media_encode_paso_key(paso_id: int) -> str:
    return f'media_encode_paso:{paso_id}'


def es_extension_video(name: str) -> bool:
    low = (name or '').lower().split('?')[0]
    return low.endswith(('.mp4', '.m4v', '.mov'))


def use_async_media_encode() -> bool:
    return not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)


def validar_cabecera_mp4_rapida(raw: bytes, filename: str) -> None:
    if len(raw) < 12 or b'ftyp' not in raw[:64]:
        raise ValidationError(
            f'El video "{filename}" no es un MP4 válido (cabecera incorrecta). '
            'Exporte de nuevo como H.264 + AAC (.mp4) e intente otra vez.'
        )


def subir_video_incoming(
    raw: bytes,
    filename: str,
    *,
    carpeta: str,
    prefix: str,
) -> tuple[str, str]:
    """Guarda bytes crudos en S3 incoming/. Returns (storage_path, public_url)."""
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone
    from django.utils.text import get_valid_filename

    fn = get_valid_filename(filename)
    now = timezone.now()
    path = (
        f'{carpeta.rstrip("/")}/incoming/{now:%Y/%m}/'
        f'{prefix}_{now:%Y%m%d%H%M%S}_{fn}'
    )
    saved = default_storage.save(path, ContentFile(raw))
    return saved, default_storage.url(saved)


def _set_encode_state(*, job_id: str, paso_id: int, status: str, error: str = '') -> None:
    payload = {'status': status, 'paso_id': paso_id, 'job_id': job_id}
    if error:
        payload['error'] = error[:500]
    cache.set(media_encode_job_key(job_id), payload, CACHE_TTL)
    cache.set(media_encode_paso_key(paso_id), payload, CACHE_TTL)


def _clear_encode_state(*, job_id: str, paso_id: int) -> None:
    cache.delete(media_encode_job_key(job_id))
    cache.delete(media_encode_paso_key(paso_id))


def encolar_encode_paso_modulo(
    *,
    paso_id: int,
    job_id: str,
    temp_s3_path: str,
    filename: str,
    carpeta: str,
    prefix: str,
) -> None:
    _set_encode_state(job_id=job_id, paso_id=paso_id, status='pending')
    from core.tasks import encode_paso_modulo_media

    encode_paso_modulo_media.delay(
        job_id,
        paso_id,
        temp_s3_path,
        filename,
        carpeta,
        prefix,
    )


def aplicar_resultado_upload_async(
    resultado: dict,
    paso_id: int,
    *,
    carpeta: str,
    prefix: str,
) -> bool:
    if not resultado.get('async_encode'):
        return False
    encolar_encode_paso_modulo(
        paso_id=paso_id,
        job_id=resultado['job_id'],
        temp_s3_path=resultado['temp_s3_path'],
        filename=resultado['filename'],
        carpeta=carpeta,
        prefix=prefix,
    )
    return True


def es_url_media_incoming(url: str) -> bool:
    return '/incoming/' in (url or '').strip().lower()


def estado_encode_paso(paso_id: int, *, paso=None) -> dict | None:
    """
    Estado encode async. Reconcilia con PasoModulo cuando el cache LocMem
    del web no ve lo que escribió el worker Celery (prod EB).
    """
    if not paso_id:
        return None

    if paso is None:
        from core.models import PasoModulo

        paso = PasoModulo.objects.filter(pk=paso_id).only('media_url', 'media_wa_apto').first()

    enc = cache.get(media_encode_paso_key(paso_id))
    if paso is None:
        return enc

    url = (getattr(paso, 'media_url', None) or '').strip()
    incoming = es_url_media_incoming(url)
    apto = getattr(paso, 'media_wa_apto', None)

    if enc:
        st = enc.get('status')
        if st in ('pending', 'running'):
            if not incoming and apto is not None:
                limpiar_estado_encode_paso(paso_id)
                return None
            if incoming and apto is False:
                limpiar_estado_encode_paso(paso_id)
                err = (enc.get('error') or '').strip() or (
                    'Video no apto para WhatsApp. Exporte MP4 H.264+AAC ≤16 MB e intente de nuevo.'
                )
                return {'status': 'error', 'paso_id': paso_id, 'error': err[:500]}
        return enc

    if incoming and apto is False:
        return {
            'status': 'error',
            'paso_id': paso_id,
            'error': 'Video no apto para WhatsApp. Exporte MP4 H.264+AAC ≤16 MB e intente de nuevo.',
        }
    if incoming and apto is None:
        return {'status': 'pending', 'paso_id': paso_id}

    return None


def mensaje_upload_media(resultado: dict) -> str:
    if resultado.get('async_encode'):
        return (
            'Video recibido. Procesando en segundo plano (1–3 min): ffmpeg + optimización WhatsApp. '
            'Refrescá la página (F5) para ver el semáforo en verde o el error concreto.'
        )
    url = (resultado.get('url') or '')[:120]
    suffix = '…' if len(resultado.get('url') or '') > 120 else ''
    return f'Material listo. URL: {url}{suffix}'


def nuevo_job_id() -> str:
    return str(uuid.uuid4())


def limpiar_estado_encode_paso(paso_id: int) -> None:
    """Quita cache de encode async (p. ej. tras borrar media o subir de nuevo)."""
    if not paso_id:
        return
    enc = cache.get(media_encode_paso_key(paso_id)) or {}
    job_id = enc.get('job_id')
    cache.delete(media_encode_paso_key(paso_id))
    if job_id:
        cache.delete(media_encode_job_key(job_id))
