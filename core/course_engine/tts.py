"""TTS providers — ElevenLabs (default) u OpenAI (fallback)."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from django.conf import settings

from core.twilio_media import _subir_bytes_s3

logger = logging.getLogger(__name__)

_last_tts_error: Optional[str] = None

MAX_TTS_CHARS = 4096
S3_PREFIX = 'media/course_engine/tts'

TtsProviderName = Literal['elevenlabs', 'openai']


@dataclass(frozen=True)
class TtsResult:
    url: str
    s3_key: str
    bytes_size: int
    provider: str
    voice: str
    text_hash: str
    local_path: Optional[str] = None


def _text_hash(texto: str, provider: str, voice: str) -> str:
    payload = f'{provider}|{voice}|{(texto or "").strip()}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def _s3_key(text_hash: str, ext: str = 'mp3') -> str:
    return f'{S3_PREFIX}/{text_hash}.{ext}'


def _sanitize(texto: str) -> str:
    t = re.sub(r'\s+', ' ', (texto or '').strip())
    return t[:MAX_TTS_CHARS] if len(t) > MAX_TTS_CHARS else t


def _provider_default() -> TtsProviderName:
    p = (getattr(settings, 'COURSE_ENGINE_TTS_PROVIDER', None) or 'elevenlabs').strip().lower()
    return 'openai' if p == 'openai' else 'elevenlabs'


def ultimo_error_tts() -> Optional[str]:
    """Detalle del último fallo TTS (para smoke / ops)."""
    return _last_tts_error


def _set_tts_error(msg: Optional[str]) -> None:
    global _last_tts_error
    _last_tts_error = msg


def _mensaje_error_elevenlabs(resp) -> str:
    try:
        body = resp.json()
        detail = body.get('detail') or body
        if isinstance(detail, dict):
            code = detail.get('code') or detail.get('type') or 'error'
            message = detail.get('message') or str(detail)
            return f'ElevenLabs {code}: {message}'
        return f'ElevenLabs HTTP {resp.status_code}: {detail}'
    except Exception:
        return f'ElevenLabs HTTP {resp.status_code}'


def generar_narracion(
    texto: str,
    *,
    provider: Optional[TtsProviderName] = None,
    voice: Optional[str] = None,
    model_id: Optional[str] = None,
    voice_profile: Literal['video', 'podcast'] = 'video',
) -> Optional[TtsResult]:
    """
    Narración outbound → S3 (audio/mpeg).

    Default: ElevenLabs (voz natural ES). Fallback: OpenAI TTS si ElevenLabs falla
    y COURSE_ENGINE_TTS_FALLBACK_OPENAI=true.
    """
    _set_tts_error(None)
    clean = _sanitize(texto)
    if not clean:
        return None

    prov = provider or _provider_default()
    result = None
    if prov == 'elevenlabs':
        result = _tts_elevenlabs(
            clean, voice=voice, model_id=model_id, voice_profile=voice_profile,
        )
    else:
        result = _tts_openai(clean, voice=voice or 'nova')

    if result is None and prov == 'elevenlabs' and getattr(settings, 'COURSE_ENGINE_TTS_FALLBACK_OPENAI', True):
        logger.info('ElevenLabs falló — fallback OpenAI TTS')
        result = _tts_openai(clean, voice='nova')

    return result


def generar_narracion_archivo(
    texto: str,
    dest: Path,
    *,
    provider: Optional[TtsProviderName] = None,
    voice: Optional[str] = None,
    model_id: Optional[str] = None,
    voice_profile: Literal['video', 'podcast'] = 'video',
) -> Optional[TtsResult]:
    """TTS → archivo local MP3 (+ S3 si está configurado)."""
    _set_tts_error(None)
    clean = _sanitize(texto)
    if not clean:
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    prov = provider or _provider_default()

    if prov == 'elevenlabs':
        result = _tts_elevenlabs(
            clean, voice=voice, local_copy=dest,
            model_id=model_id, voice_profile=voice_profile,
        )
    else:
        result = _tts_openai(clean, voice=voice or 'nova', local_copy=dest)

    if result is None and prov == 'elevenlabs' and getattr(settings, 'COURSE_ENGINE_TTS_FALLBACK_OPENAI', True):
        result = _tts_openai(clean, voice='nova', local_copy=dest)
    return result


def _upload_mp3(
    key: str,
    data: bytes,
    provider: str,
    voice: str,
    text_hash: str,
    *,
    local_copy: Optional[Path] = None,
) -> Optional[TtsResult]:
    if not data or len(data) > 16 * 1024 * 1024:
        return None
    local_str = None
    if local_copy:
        local_copy.parent.mkdir(parents=True, exist_ok=True)
        local_copy.write_bytes(data)
        local_str = str(local_copy)
    url = _subir_bytes_s3(key, data, 'audio/mpeg')
    if not url and not local_str:
        return None
    return TtsResult(
        url=url or '',
        s3_key=key,
        bytes_size=len(data),
        provider=provider,
        voice=voice,
        text_hash=text_hash,
        local_path=local_str,
    )


def _voice_settings(profile: Literal['video', 'podcast']) -> dict:
    if profile == 'podcast':
        return {
            'stability': 0.55,
            'similarity_boost': 0.80,
            'style': 0.12,
            'use_speaker_boost': True,
        }
    return {
        'stability': 0.45,
        'similarity_boost': 0.75,
        'style': 0.0,
        'use_speaker_boost': True,
    }


def _resolve_elevenlabs_model(model_id: Optional[str], voice_profile: Literal['video', 'podcast']) -> str:
    if model_id:
        return model_id
    if voice_profile == 'podcast':
        return getattr(settings, 'ELEVENLABS_MODEL_ID_PODCAST', 'eleven_multilingual_v2')
    return getattr(settings, 'ELEVENLABS_MODEL_ID_VIDEO', 'eleven_multilingual_v2')


def _tts_elevenlabs(
    texto: str,
    *,
    voice: Optional[str] = None,
    local_copy: Optional[Path] = None,
    model_id: Optional[str] = None,
    voice_profile: Literal['video', 'podcast'] = 'video',
) -> Optional[TtsResult]:
    api_key = getattr(settings, 'ELEVENLABS_API_KEY', None)
    voice_id = voice or getattr(settings, 'ELEVENLABS_VOICE_ID', None)
    model_id = _resolve_elevenlabs_model(model_id, voice_profile)

    if not api_key or not voice_id:
        logger.warning('ElevenLabs: falta ELEVENLABS_API_KEY o ELEVENLABS_VOICE_ID')
        return None

    th = _text_hash(texto, 'elevenlabs', voice_id)
    key = _s3_key(th)

    try:
        import httpx

        url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
        resp = httpx.post(
            url,
            headers={
                'xi-api-key': api_key,
                'Content-Type': 'application/json',
                'Accept': 'audio/mpeg',
            },
            json={
                'text': texto,
                'model_id': model_id,
                'voice_settings': _voice_settings(voice_profile),
            },
            timeout=120.0,
        )
        if resp.status_code >= 400:
            err = _mensaje_error_elevenlabs(resp)
            _set_tts_error(err)
            logger.error(err)
            return None
        return _upload_mp3(key, resp.content, 'elevenlabs', voice_id, th, local_copy=local_copy)
    except Exception as exc:
        _set_tts_error(str(exc))
        logger.exception('ElevenLabs TTS: %s', exc)
        return None


def _tts_openai(texto: str, *, voice: str = 'nova', local_copy: Optional[Path] = None) -> Optional[TtsResult]:
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        return None

    voices = {'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'}
    v = voice if voice in voices else 'nova'
    th = _text_hash(texto, 'openai', v)
    key = _s3_key(th)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model='tts-1',
            voice=v,
            input=texto,
            response_format='mp3',
        )
        return _upload_mp3(key, response.content, 'openai', v, th, local_copy=local_copy)
    except Exception as exc:
        logger.exception('OpenAI TTS: %s', exc)
        return None
