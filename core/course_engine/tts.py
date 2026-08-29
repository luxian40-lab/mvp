"""TTS providers — ElevenLabs (default) u OpenAI (fallback)."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Literal, Optional

from django.conf import settings

from core.twilio_media import _subir_bytes_s3

logger = logging.getLogger(__name__)

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


def generar_narracion(
    texto: str,
    *,
    provider: Optional[TtsProviderName] = None,
    voice: Optional[str] = None,
) -> Optional[TtsResult]:
    """
    Narración outbound → S3 (audio/mpeg).

    Default: ElevenLabs (voz natural ES). Fallback: OpenAI TTS si ElevenLabs falla
    y COURSE_ENGINE_TTS_FALLBACK_OPENAI=true.
    """
    clean = _sanitize(texto)
    if not clean:
        return None

    prov = provider or _provider_default()
    result = None
    if prov == 'elevenlabs':
        result = _tts_elevenlabs(clean, voice=voice)
    else:
        result = _tts_openai(clean, voice=voice or 'nova')

    if result is None and prov == 'elevenlabs' and getattr(settings, 'COURSE_ENGINE_TTS_FALLBACK_OPENAI', True):
        logger.info('ElevenLabs falló — fallback OpenAI TTS')
        result = _tts_openai(clean, voice='nova')

    return result


def _upload_mp3(key: str, data: bytes, provider: str, voice: str, text_hash: str) -> Optional[TtsResult]:
    if not data or len(data) > 16 * 1024 * 1024:
        return None
    url = _subir_bytes_s3(key, data, 'audio/mpeg')
    if not url:
        return None
    return TtsResult(
        url=url,
        s3_key=key,
        bytes_size=len(data),
        provider=provider,
        voice=voice,
        text_hash=text_hash,
    )


def _tts_elevenlabs(texto: str, *, voice: Optional[str] = None) -> Optional[TtsResult]:
    api_key = getattr(settings, 'ELEVENLABS_API_KEY', None)
    voice_id = voice or getattr(settings, 'ELEVENLABS_VOICE_ID', None)
    model_id = getattr(settings, 'ELEVENLABS_MODEL_ID', 'eleven_multilingual_v2')

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
                'voice_settings': {
                    'stability': 0.45,
                    'similarity_boost': 0.75,
                    'style': 0.0,
                    'use_speaker_boost': True,
                },
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return _upload_mp3(key, resp.content, 'elevenlabs', voice_id, th)
    except Exception as exc:
        logger.exception('ElevenLabs TTS: %s', exc)
        return None


def _tts_openai(texto: str, *, voice: str = 'nova') -> Optional[TtsResult]:
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
        return _upload_mp3(key, response.content, 'openai', v, th)
    except Exception as exc:
        logger.exception('OpenAI TTS: %s', exc)
        return None
