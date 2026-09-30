"""Enlaces cortos de video para WhatsApp y agregados de Learning Analytics.

Apertura = clic en /v/<token> (no es reproducción ni lectura de WhatsApp).
Progreso 25/50/75/100 = hito del reproductor propio. YouTube/Vimeo solo tienen apertura.
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import date
from urllib.parse import urlparse

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q

logger = logging.getLogger(__name__)

_MEDIA_RE = re.compile(r'\[MEDIA:(.+?)\]', re.DOTALL)
_TOKEN_RE = re.compile(r'^[A-Za-z0-9]{16,40}$')
_VIDEO_EXT = ('.mp4', '.m4v', '.mov', '.webm', '.3gp')
_PREVIEW_BOTS = (
    'facebookexternalhit',
    'facebot',
    'twitterbot',
    'telegrambot',
    'slackbot',
    'discordbot',
    'linkedinbot',
)
_HOSTS_REDIRECT = (
    'youtube.com',
    'youtu.be',
    'youtube-nocookie.com',
    'vimeo.com',
)
HITOS = {
    25: 'progreso_25',
    50: 'progreso_50',
    75: 'progreso_75',
    100: 'progreso_100',
}


def shortlinks_activos() -> bool:
    return bool(getattr(settings, 'EKI_VIDEO_SHORTLINKS', False))


def base_publica() -> str:
    return (
        getattr(settings, 'VIDEO_PUBLIC_BASE_URL', '') or 'https://videos.eki.technology'
    ).rstrip('/')


def generar_token() -> str:
    return secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:22]


def token_valido(token: str) -> bool:
    return bool(_TOKEN_RE.fullmatch(token or ''))


def es_prefetch(user_agent: str) -> bool:
    ua = (user_agent or '').lower()
    return any(bot in ua for bot in _PREVIEW_BOTS)


def es_video_rastreable(url: str) -> bool:
    """True solo para video. Imagen, PDF y audio siguen como adjunto de WhatsApp."""
    raw = (url or '').strip()
    if not raw:
        return False
    path = raw.split('?', 1)[0].lower()
    if any(path.endswith(ext) for ext in _VIDEO_EXT):
        return True
    host = (urlparse(raw).hostname or '').lower()
    if host.endswith(_HOSTS_REDIRECT) or host in _HOSTS_REDIRECT:
        return True
    if '/videos/' in path:
        return True
    return False


def _es_youtube_o_vimeo(url: str) -> bool:
    host = (urlparse(url or '').hostname or '').lower()
    return host in _HOSTS_REDIRECT or host.endswith('.youtube.com') or host.endswith('.vimeo.com')


def clasificar_destino(url: str) -> tuple[str, str]:
    """(destino_tipo, destino_ref). destino_ref nunca es una URL firmada."""
    from core.models_video import VideoEnlace
    from core.twilio_media import _s3_key_desde_url

    limpia = (url or '').strip()
    if _es_youtube_o_vimeo(limpia):
        return VideoEnlace.DESTINO_EXTERNO, limpia
    key = _s3_key_desde_url(limpia)
    if key:
        return VideoEnlace.DESTINO_S3, key
    return VideoEnlace.DESTINO_ARCHIVO, limpia


def _etiqueta(modulo, url: str, video_id: str) -> str:
    if video_id.startswith('archivo:'):
        try:
            from core.models_extras import ArchivoModulo

            arch = ArchivoModulo.objects.filter(pk=int(video_id.split(':', 1)[1])).first()
            if arch and (arch.titulo or '').strip():
                return arch.titulo.strip()[:200]
        except (TypeError, ValueError):
            pass
    if modulo is not None:
        titulo = (getattr(modulo, 'titulo', '') or '').strip()
        numero = getattr(modulo, 'numero', None)
        if titulo:
            pref = f'M{numero}. ' if numero is not None else ''
            return f'{pref}{titulo}'[:200]
    return 'Video'


def identificar_video(modulo, url: str) -> tuple[str, str, str, str]:
    """video_id, destino_tipo, destino_ref, etiqueta."""
    limpia = (url or '').strip()
    base = limpia.split('?', 1)[0]
    tipo, ref = clasificar_destino(limpia)
    video_id = ''
    if modulo is not None:
        try:
            from core.models_extras import ArchivoModulo

            for arch in modulo.archivos_multimedia.filter(activo=True, tipo='video'):
                candidatos = [(arch.url_externa or '').strip()]
                try:
                    candidatos.append((arch.get_url_para_envio() or '').strip())
                except Exception:
                    pass
                if any(c and c.split('?', 1)[0] == base for c in candidatos):
                    video_id = f'archivo:{arch.pk}'
                    break
        except Exception:
            logger.warning('identificar_video archivos modulo_id=%s', getattr(modulo, 'id', None))
        if not video_id:
            for paso in modulo.pasos.filter(activo=True):
                media = (paso.media_url or '').strip()
                if media and media.split('?', 1)[0] == base:
                    video_id = f'paso:{paso.pk}'
                    break
        if not video_id:
            propio = (getattr(modulo, 'video_url', None) or '').strip()
            if propio and propio.split('?', 1)[0] == base:
                video_id = f'modulo:{modulo.pk}'
    if not video_id:
        digest = hashlib.sha256(base.encode('utf-8')).hexdigest()[:16]
        video_id = f'url:{digest}'
    return video_id, tipo, ref, _etiqueta(modulo, limpia, video_id)


def url_publica(enlace) -> str:
    return f'{base_publica()}/v/{enlace.token}'


def obtener_o_crear_enlace(*, estudiante, curso, modulo, url: str):
    from core.models_video import VideoEnlace

    video_id, tipo, ref, etiqueta = identificar_video(modulo, url)
    existente = (
        VideoEnlace.objects.filter(estudiante=estudiante, video_id=video_id)
        .order_by('id')
        .first()
    )
    if existente:
        cambios = []
        if existente.destino_tipo != tipo:
            existente.destino_tipo = tipo
            cambios.append('destino_tipo')
        if existente.destino_ref != ref:
            existente.destino_ref = ref
            cambios.append('destino_ref')
        if etiqueta and existente.etiqueta != etiqueta:
            existente.etiqueta = etiqueta
            cambios.append('etiqueta')
        if modulo is not None and existente.modulo_id != getattr(modulo, 'pk', None):
            existente.modulo = modulo
            cambios.append('modulo')
        if cambios:
            existente.save(update_fields=cambios)
        return existente
    for _ in range(5):
        try:
            with transaction.atomic():
                return VideoEnlace.objects.create(
                    token=generar_token(),
                    estudiante=estudiante,
                    curso=curso,
                    modulo=modulo,
                    video_id=video_id,
                    etiqueta=etiqueta,
                    destino_tipo=tipo,
                    destino_ref=ref,
                )
        except IntegrityError:
            otra = VideoEnlace.objects.filter(estudiante=estudiante, video_id=video_id).first()
            if otra:
                return otra
    raise IntegrityError('No se pudo crear el enlace de video')


def video_usa_enlace(modulo, url: str) -> bool:
    """La elección del micro gana. Sin micro de video, manda el flag global."""
    base = (url or '').strip().split('?', 1)[0]
    if modulo is not None and base:
        for paso in modulo.pasos.all():
            media = (getattr(paso, 'media_url', None) or '').strip()
            if media and media.split('?', 1)[0] == base:
                return getattr(paso, 'video_entrega', 'whatsapp') == 'enlace'
    return shortlinks_activos()


def reescribir_videos_en_mensaje(mensaje: str, *, estudiante, curso, modulo) -> str:
    """Sustituye [MEDIA:video] por el enlace corto. El resto de adjuntos no cambia."""
    if not mensaje or '[MEDIA:' not in mensaje or estudiante is None or curso is None:
        return mensaje

    def _reemplazo(match: re.Match) -> str:
        url = (match.group(1) or '').strip()
        if not es_video_rastreable(url) or not video_usa_enlace(modulo, url):
            return match.group(0)
        try:
            enlace = obtener_o_crear_enlace(
                estudiante=estudiante,
                curso=curso,
                modulo=modulo,
                url=url,
            )
        except Exception:
            logger.exception('shortlink video no creado')
            return match.group(0)
        return f'🎥 Para ver el video:\n{url_publica(enlace)}'

    return _MEDIA_RE.sub(_reemplazo, mensaje)


def registrar_apertura(enlace, user_agent: str):
    from core.models_video import VideoView

    return VideoView.objects.create(
        enlace=enlace,
        estudiante_id=enlace.estudiante_id,
        curso_id=enlace.curso_id,
        modulo_id=enlace.modulo_id,
        video_id=enlace.video_id,
        evento=VideoView.EVENTO_APERTURA,
        user_agent=(user_agent or '')[:400],
    )


def registrar_progreso(enlace, hito: int, user_agent: str):
    """Primer cruce de cada umbral por enlace. Reintentos no suman otra fila."""
    from core.models_video import VideoView

    evento = HITOS[int(hito)]
    previo = VideoView.objects.filter(enlace=enlace, evento=evento).order_by('id').first()
    if previo:
        return previo, False
    fila = VideoView.objects.create(
        enlace=enlace,
        estudiante_id=enlace.estudiante_id,
        curso_id=enlace.curso_id,
        modulo_id=enlace.modulo_id,
        video_id=enlace.video_id,
        evento=evento,
        user_agent=(user_agent or '')[:400],
    )
    return fila, True


def redirect_externo_seguro(url: str) -> bool:
    parsed = urlparse(url or '')
    if parsed.scheme not in ('https', 'http'):
        return False
    host = (parsed.hostname or '').lower()
    if host in _HOSTS_REDIRECT:
        return True
    return host.endswith('.youtube.com') or host.endswith('.vimeo.com') or host.endswith('.youtube-nocookie.com')


def src_reproductor_seguro(url: str) -> bool:
    parsed = urlparse(url or '')
    return parsed.scheme == 'https' and bool(parsed.hostname)


def url_firmada_s3(key: str, expires_in: int = 3600) -> str:
    """Presigned GET. No reescribe el host: la firma dejaría de valer."""
    import boto3
    from botocore.config import Config

    limpia = (key or '').lstrip('/')
    if not limpia or '..' in limpia.split('/'):
        raise ValueError('key S3 inválida')
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None) or 'eki-produccion'
    region = getattr(settings, 'AWS_S3_REGION_NAME', None) or 'us-east-2'
    client = boto3.client(
        's3',
        config=Config(signature_version='s3v4', region_name=region),
    )
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': limpia},
        ExpiresIn=expires_in,
    )


def url_de_reproduccion(enlace) -> str:
    from core.models_video import VideoEnlace

    if enlace.destino_tipo == VideoEnlace.DESTINO_S3:
        return url_firmada_s3(enlace.destino_ref)
    if enlace.destino_tipo == VideoEnlace.DESTINO_EXTERNO:
        if not redirect_externo_seguro(enlace.destino_ref):
            raise ValueError('destino externo no permitido')
        return enlace.destino_ref
    if not src_reproductor_seguro(enlace.destino_ref):
        raise ValueError('URL de archivo no reproducible')
    return enlace.destino_ref


def _max_hito(row: dict) -> int | None:
    for hito, clave in ((100, 'p100'), (75, 'p75'), (50, 'p50'), (25, 'p25')):
        if row.get(clave):
            return hito
    return None


def reporte_aperturas_video(
    *,
    curso_id: int | None = None,
    cliente_id: int | None = None,
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
) -> dict:
    """Agregados para Analítica. Apertura ≠ reproducción. Progreso solo en reproductor propio."""
    from core.models_video import VideoView

    qs = VideoView.objects.all()
    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    if cliente_id:
        qs = qs.filter(estudiante__cliente_id=cliente_id)
    if fecha_inicio:
        qs = qs.filter(creado_en__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(creado_en__date__lte=fecha_fin)

    totales = qs.aggregate(
        aperturas=Count('id', filter=Q(evento=VideoView.EVENTO_APERTURA)),
        estudiantes=Count('estudiante_id', filter=Q(evento=VideoView.EVENTO_APERTURA), distinct=True),
        llegaron_100=Count(
            'estudiante_id',
            filter=Q(evento=VideoView.EVENTO_P100),
            distinct=True,
        ),
    )
    por_curso = list(
        qs.values(
            'curso_id',
            'curso__nombre',
            'video_id',
            'modulo__numero',
            'modulo__titulo',
            'enlace__etiqueta',
        )
        .annotate(
            aperturas=Count('id', filter=Q(evento=VideoView.EVENTO_APERTURA)),
            estudiantes=Count(
                'estudiante_id',
                filter=Q(evento=VideoView.EVENTO_APERTURA),
                distinct=True,
            ),
            llegaron_100=Count(
                'estudiante_id',
                filter=Q(evento=VideoView.EVENTO_P100),
                distinct=True,
            ),
        )
        .order_by('curso__nombre', 'modulo__numero', 'video_id')
    )
    filas_est = list(
        qs.values(
            'estudiante_id',
            'estudiante__nombre',
            'curso__nombre',
            'video_id',
            'modulo__numero',
            'modulo__titulo',
            'enlace__etiqueta',
        )
        .annotate(
            aperturas=Count('id', filter=Q(evento=VideoView.EVENTO_APERTURA)),
            p25=Count('id', filter=Q(evento=VideoView.EVENTO_P25)),
            p50=Count('id', filter=Q(evento=VideoView.EVENTO_P50)),
            p75=Count('id', filter=Q(evento=VideoView.EVENTO_P75)),
            p100=Count('id', filter=Q(evento=VideoView.EVENTO_P100)),
        )
        .order_by('estudiante__nombre', 'curso__nombre', 'video_id')[:200]
    )
    por_estudiante = []
    for row in filas_est:
        row['max_hito'] = _max_hito(row)
        por_estudiante.append(row)
    return {
        'totales': totales,
        'por_curso': por_curso,
        'por_estudiante': por_estudiante,
    }
