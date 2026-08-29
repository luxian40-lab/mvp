"""Generación de audio outbound (texto → MP3 → S3) para Course Engine."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from core.twilio_media import _subir_bytes_s3

logger = logging.getLogger(__name__)

# OpenAI TTS: https://platform.openai.com/docs/guides/text-to-speech
DEFAULT_VOICE = 'nova'
DEFAULT_MODEL = 'tts-1'
MAX_CHARS = 4096
S3_PREFIX = 'media/course_engine/tts'

_VOICES = frozenset({'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'})


@dataclass(frozen=True)
class TtsResult:
    url: str
    s3_key: str
    bytes_size: int
    voice: str
    model: str
    text_hash: str


def _normalize_voice(voice: str) -> str:
    v = (voice or DEFAULT_VOICE).strip().lower()
    return v if v in _VOICES else DEFAULT_VOICE


def _text_hash(texto: str, voice: str, model: str) -> str:
    payload = f'{model}|{voice}|{(texto or "").strip()}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def _s3_key_for(text_hash: str) -> str:
    return f'{S3_PREFIX}/{text_hash}.mp3'


def _sanitize_text(texto: str) -> str:
    t = (texto or '').strip()
    t = re.sub(r'\s+', ' ', t)
    if len(t) > MAX_CHARS:
        t = t[:MAX_CHARS]
    return t


def generar_audio_tts(
    texto: str,
    *,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    openai_client=None,
) -> Optional[TtsResult]:
    """
    Texto → OpenAI TTS → MP3 en S3 con Content-Type audio/mpeg.

    Returns None si falla API, upload o texto vacío.
    """
    clean = _sanitize_text(texto)
    if not clean:
        logger.warning('TTS: texto vacío')
        return None

    voice = _normalize_voice(voice)
    model = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    th = _text_hash(clean, voice, model)
    key = _s3_key_for(th)

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        response = openai_client.audio.speech.create(
            model=model,
            voice=voice,
            input=clean,
            response_format='mp3',
        )
        audio_bytes = response.content
    except Exception as exc:
        logger.exception('TTS OpenAI falló: %s', exc)
        return None

    if not audio_bytes:
        logger.warning('TTS: respuesta vacía de OpenAI')
        return None

    if len(audio_bytes) > 16 * 1024 * 1024:
        logger.warning('TTS: audio >16MB (%s bytes)', len(audio_bytes))
        return None

    url = _subir_bytes_s3(key, audio_bytes, 'audio/mpeg')
    if not url:
        logger.warning('TTS: falló upload S3 key=%s', key)
        return None

    return TtsResult(
        url=url,
        s3_key=key,
        bytes_size=len(audio_bytes),
        voice=voice,
        model=model,
        text_hash=th,
    )
