"""Demos de voz Course Engine — MP3 estáticos o caché local/S3."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.contrib.staticfiles import finders

from core.course_engine.voice_config import catalogo_voces
from core.course_engine.voice_preview import MUESTRA_VOZ_TEXTO, generar_muestra_voz
from mvp_project.static_safe import static_safe

logger = logging.getLogger(__name__)

_DEMO_DIR_STATIC = 'course_engine/voices'
_DEMO_DIR_MEDIA = 'course_engine/voice_demos'


def _slug_label(label: str) -> str:
    base = re.sub(r'[^a-z0-9]+', '_', (label or '').strip().lower())
    return base.strip('_') or 'voz'


def demo_slug_for_voice_id(voice_id: str) -> str:
    vid = (voice_id or '').strip()
    for v in catalogo_voces():
        if v['id'] == vid:
            return _slug_label(v['label'])
    return _slug_label(vid[:16])


def _media_demo_path(voice_id: str) -> Path:
    root = Path(getattr(settings, 'MEDIA_ROOT', '') or '')
    return root / _DEMO_DIR_MEDIA / f'{voice_id}.mp3'


def _static_demo_rel(slug: str) -> str:
    return f'{_DEMO_DIR_STATIC}/{slug}.mp3'


def _static_demo_exists(slug: str) -> bool:
    rel = _static_demo_rel(slug)
    if finders.find(rel):
        return True
    path = Path(settings.BASE_DIR) / 'static' / _DEMO_DIR_STATIC / f'{slug}.mp3'
    return path.is_file()


def url_demo_voz(
    voice_id: str,
    *,
    generar_si_falta: bool = False,
    force_regenerate: bool = False,
    request=None,
) -> dict:
    """
    Resuelve URL de muestra (~5 s) para una Voice ID del catálogo eki.

    Orden (si force_regenerate=False):
      static → MEDIA → generar TTS (si generar_si_falta).
    Con force_regenerate=True salta static/MEDIA y regenera TTS.
    """
    vid = (voice_id or '').strip()
    if not vid:
        return {'ok': False, 'url': '', 'cached': False, 'label': '', 'error': 'Voice ID vacío'}

    label = vid
    for v in catalogo_voces():
        if v['id'] == vid:
            label = v['label']
            break

    def _abs(url: str) -> str:
        if not url:
            return ''
        if request is not None and url.startswith('/'):
            try:
                return request.build_absolute_uri(url)
            except Exception:
                return url
        return url

    slug = demo_slug_for_voice_id(vid)

    if not force_regenerate:
        if _static_demo_exists(slug):
            return {
                'ok': True,
                'url': _abs(static_safe(_static_demo_rel(slug))),
                'cached': True,
                'label': label,
                'source': 'static',
            }

        media_path = _media_demo_path(vid)
        if media_path.is_file():
            media_url = getattr(settings, 'MEDIA_URL', '/media/') or '/media/'
            if not media_url.endswith('/'):
                media_url += '/'
            return {
                'ok': True,
                'url': _abs(f'{media_url}{_DEMO_DIR_MEDIA}/{vid}.mp3'),
                'cached': True,
                'label': label,
                'source': 'media',
            }

        if not generar_si_falta:
            return {
                'ok': False,
                'url': '',
                'cached': False,
                'label': label,
                'error': 'Demo no generada — ejecute course_engine_seed_voice_demos',
            }
    elif not generar_si_falta:
        # force sin generate no tiene sentido: pedir generate
        return {
            'ok': False,
            'url': '',
            'cached': False,
            'label': label,
            'error': 'force requiere generate=1',
        }

    out = generar_muestra_voz(vid, voice_label=label)
    if not out.ok or not out.tts:
        return {
            'ok': False,
            'url': '',
            'cached': False,
            'label': label,
            'error': out.error or 'TTS falló (revisa ELEVENLABS_API_KEY)',
        }

    url = (out.tts.url or '').strip()
    media_path = _media_demo_path(vid)

    # Preferir URL S3/pública; si solo hay path local, publicar vía MEDIA
    if not url and out.tts.local_path:
        try:
            src = Path(out.tts.local_path)
            if src.is_file():
                media_path.parent.mkdir(parents=True, exist_ok=True)
                media_path.write_bytes(src.read_bytes())
                media_url = getattr(settings, 'MEDIA_URL', '/media/') or '/media/'
                if not media_url.endswith('/'):
                    media_url += '/'
                url = f'{media_url}{_DEMO_DIR_MEDIA}/{vid}.mp3'
        except Exception:
            logger.exception('No se pudo materializar demo voz local %s', vid)

    elif url and not url.startswith('http'):
        # relative ok
        pass
    elif url.startswith('http'):
        # Cachear en MEDIA para reuso local (best-effort)
        try:
            import httpx

            media_path.parent.mkdir(parents=True, exist_ok=True)
            resp = httpx.get(url, timeout=60.0)
            if resp.status_code == 200 and resp.content:
                media_path.write_bytes(resp.content)
        except Exception:
            logger.exception('No se pudo cachear demo voz %s', vid)

    return {
        'ok': bool(url),
        'url': _abs(url or ''),
        'cached': False,
        'label': label,
        'source': 'generated',
        'error': '' if url else 'Sin URL de audio (TTS OK pero S3/MEDIA falló)',
    }


def catalogo_voces_demo(*, curso=None, generar_si_falta: bool = False, request=None) -> list[dict]:
    """Lista las 4 voces eki con URL de demo para el Studio."""
    selected = ''
    if curso is not None:
        from core.course_engine.voice_config import resolver_voice_id_curso

        selected = (resolver_voice_id_curso(curso) or '').strip()

    rows: list[dict] = []
    for v in catalogo_voces():
        demo = url_demo_voz(v['id'], generar_si_falta=generar_si_falta, request=request)
        genero = (v.get('genero') or '').upper()
        tag = {'F': 'mujer', 'M': 'hombre'}.get(genero, '')
        rows.append(
            {
                'id': v['id'],
                'label': v['label'],
                'tag': tag,
                'audio_url': demo.get('url') or '',
                'demo_ok': demo.get('ok', False),
                'demo_cached': demo.get('cached', False),
                'selected': v['id'] == selected,
                'muestra_texto': MUESTRA_VOZ_TEXTO,
            }
        )
    return rows
