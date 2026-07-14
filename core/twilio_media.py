"""Utilidades Twilio WhatsApp media: normalización, errores y fallback a enlace."""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Fallos de adjunto: sync (excepciona create) o async (status callback undelivered).
CODIGOS_FALLA_MEDIA_TWILIO = frozenset({'63019', '63021', '63005'})

_MEDIA_MARKER_RE = re.compile(r'\[MEDIA:(.+?)\]', re.DOTALL)


def es_error_media_twilio(err) -> bool:
    """True si el error/string/código indica rechazo o fallo de media WhatsApp."""
    if err is None:
        return False
    if isinstance(err, (int, float)):
        return str(int(err)) in CODIGOS_FALLA_MEDIA_TWILIO
    s = str(err)
    return any(code in s for code in CODIGOS_FALLA_MEDIA_TWILIO)


def normalizar_media_url_s3(url: Optional[str]) -> Optional[str]:
    """
    URL pública regional (us-east-2). Evita redirects .s3.amazonaws.com → región
    que suelen terminar en 63019/63021.
    """
    if not url:
        return None
    clean = str(url).strip()
    if not clean:
        return None
    if 'amazonaws.com' in clean and '.s3.amazonaws.com/' in clean and '.s3.us-east-2.amazonaws.com/' not in clean:
        clean = clean.replace('.s3.amazonaws.com/', '.s3.us-east-2.amazonaws.com/')
    return clean


def cuerpo_con_enlace_archivo(body: str, media_url: str) -> str:
    base = (body or '').strip()
    url = (media_url or '').strip()
    extra = f'📎 Archivo: {url}' if url else ''
    if not extra:
        return base
    if url and url in base:
        return base
    return f'{base}\n\n{extra}'.strip() if base else extra


def mensaje_log_con_media(texto: str, media_url: Optional[str], max_len: int = 1500) -> str:
    """Persiste el marcador [MEDIA:url] para poder reintentar por status callback."""
    body = (texto or '').strip()
    url = (media_url or '').strip()
    if not url:
        return body[:max_len]
    if f'[MEDIA:{url}]' in body or f'[MEDIA:{url[:80]}' in body:
        return body[:max_len]
    marker = f'[MEDIA:{url}]'
    if not body:
        return marker[:max_len]
    combined = f'{body}\n{marker}'
    return combined[:max_len]


def extraer_media_url_de_mensaje(mensaje: Optional[str]) -> Optional[str]:
    if not mensaje:
        return None
    m = _MEDIA_MARKER_RE.search(mensaje)
    if not m:
        return None
    return (m.group(1) or '').strip() or None


def url_no_es_media_directo(url: str) -> bool:
    """Páginas (YouTube/Drive/Vimeo) que Twilio no puede adjuntar como video."""
    u = (url or '').strip().lower()
    if not u:
        return False
    if u.endswith(('.mp4', '.mov', '.3gp', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.ogg', '.mp3')):
        return False
    if '/videoplayback' in u:
        return False
    host_hints = (
        'youtube.com/watch',
        'youtu.be/',
        'youtube.com/shorts/',
        'youtube.com/embed/',
        'vimeo.com/',
        'drive.google.com/',
        'docs.google.com/',
    )
    return any(h in u for h in host_hints)


def marcar_fallback_enlace(error_detalle: Optional[str]) -> str:
    base = (error_detalle or '').strip()
    tag = 'FALLBACK_ENLACE'
    if tag in base:
        return base
    return f'{base} | {tag}'.strip(' |') if base else tag


def ya_envio_fallback_enlace(log) -> bool:
    detalle = getattr(log, 'error_detalle', None) or ''
    mensaje = getattr(log, 'mensaje', None) or ''
    if 'FALLBACK_ENLACE' in detalle:
        return True
    if '📎 Archivo:' in mensaje and '[MEDIA:' not in mensaje:
        return True
    return False


def _parse_mp4_top_boxes(data: bytes) -> list[tuple[int, int, bytes]]:
    """[(offset, size, type4), ...] top-level boxes."""
    out: list[tuple[int, int, bytes]] = []
    i = 0
    n = len(data)
    while i + 8 <= n:
        size = int.from_bytes(data[i : i + 4], 'big')
        typ = data[i + 4 : i + 8]
        if size == 1 and i + 16 <= n:
            size = int.from_bytes(data[i + 8 : i + 16], 'big')
        if size < 8 or i + size > n:
            break
        out.append((i, size, typ))
        i += size
        if len(out) > 64:
            break
    return out


def mp4_necesita_faststart(data: bytes) -> bool:
    """True si moov está después de mdat (WhatsApp suele rechazar → 63021)."""
    boxes = _parse_mp4_top_boxes(data)
    moov = next((b for b in boxes if b[2] == b'moov'), None)
    mdat = next((b for b in boxes if b[2] == b'mdat'), None)
    if not moov or not mdat:
        return False
    return moov[0] > mdat[0]


def remux_mp4_faststart(data: bytes) -> bytes:
    """
    Reordena átomos: ftyp (+ free) + moov + resto.
    Pure Python (sin ffmpeg). No re-encode; copy bytes.
    """
    boxes = _parse_mp4_top_boxes(data)
    if not boxes:
        return data
    if not mp4_necesita_faststart(data):
        return data

    by_type = {b[2]: b for b in boxes}
    if b'ftyp' not in by_type or b'moov' not in by_type:
        return data

    pieces: list[bytes] = []
    o_f, s_f, _ = by_type[b'ftyp']
    pieces.append(data[o_f : o_f + s_f])
    free_after = None
    for o, s, t in boxes:
        if t == b'free' and o == o_f + s_f:
            free_after = (o, s)
            pieces.append(data[o : o + s])
            break
    o_m, s_m, _ = by_type[b'moov']
    pieces.append(data[o_m : o_m + s_m])
    for o, s, t in boxes:
        if t in (b'ftyp', b'moov'):
            continue
        if free_after and o == free_after[0]:
            continue
        pieces.append(data[o : o + s])
    out = b''.join(pieces)
    logger.info(
        '🎬 MP4 faststart remux | in=%s out=%s moov_moved=1',
        len(data),
        len(out),
    )
    return out


def _es_url_video_mp4(url: str) -> bool:
    u = (url or '').split('?', 1)[0].lower()
    return u.endswith('.mp4') or u.endswith('.m4v') or '/video/' in u


def _s3_key_desde_url(url: str) -> Optional[str]:
    from urllib.parse import unquote, urlparse

    p = urlparse(url)
    host = (p.netloc or '').lower()
    path = unquote(p.path or '').lstrip('/')
    if not path:
        return None
    if 'eki-produccion' in host or 'amazonaws.com' in host:
        if path.startswith('eki-produccion/'):
            path = path[len('eki-produccion/') :]
        return path
    return None


def _public_s3_url(key: str) -> str:
    return f'https://eki-produccion.s3.us-east-2.amazonaws.com/{key.lstrip("/")}'


def _subir_bytes_s3(key: str, data: bytes, content_type: str) -> Optional[str]:
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            's3',
            config=Config(signature_version='s3v4', region_name='us-east-2'),
        )
        put_kw = {
            'Bucket': 'eki-produccion',
            'Key': key,
            'Body': data,
            'ContentType': content_type,
        }
        try:
            client.put_object(**put_kw, ACL='public-read')
        except Exception:
            client.put_object(**put_kw)
        return _public_s3_url(key)
    except Exception as exc:
        logger.warning('No se pudo subir media lista para WhatsApp: %s', exc)
        return None


def _descargar_bytes(url: str, timeout: int = 90) -> Optional[bytes]:
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={'User-Agent': 'eki-whatsapp-media/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:
        logger.warning('No se pudo descargar media para faststart: %s | %s', url[:120], exc)
        return None


def preparar_url_media_whatsapp(url: Optional[str]) -> Optional[str]:
    """
    Prepara URL para MediaUrl de Twilio/WhatsApp.
    - Normaliza S3 regional.
    - Si es MP4 sin faststart (moov al final), remux y re-sube a S3.
    - Audio/imagen/PDF: sin cambios de contenedor (no romper audio).
    """
    clean = normalizar_media_url_s3(url)
    if not clean:
        return None
    if url_no_es_media_directo(clean):
        return clean
    if not _es_url_video_mp4(clean):
        return clean

    # Ya cacheado
    if '/media/whatsapp_ready/' in clean:
        return clean

    import hashlib

    digest = hashlib.sha1(clean.encode('utf-8')).hexdigest()[:20]
    cache_key = f'media/whatsapp_ready/{digest}.mp4'
    cached_url = _public_s3_url(cache_key)

    # ¿Existe ya en S3?
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            's3',
            config=Config(signature_version='s3v4', region_name='us-east-2'),
        )
        client.head_object(Bucket='eki-produccion', Key=cache_key)
        logger.info('🎬 Usando MP4 faststart en caché | %s', cache_key)
        return cached_url
    except Exception:
        pass

    raw = _descargar_bytes(clean)
    if not raw:
        return clean
    if not mp4_necesita_faststart(raw):
        logger.info('🎬 MP4 ya es faststart; sin remux | bytes=%s', len(raw))
        return clean

    fixed = remux_mp4_faststart(raw)
    uploaded = _subir_bytes_s3(cache_key, fixed, 'video/mp4')
    if uploaded:
        return uploaded
    return clean
