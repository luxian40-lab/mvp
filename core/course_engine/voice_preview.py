"""Muestra TTS ~5 s para validar Voice ID antes de generar video."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.course_engine.tts import TtsResult, generar_narracion, ultimo_error_tts

MUESTRA_VOZ_TEXTO = (
    'Hola, soy la voz de este curso eki. '
    'Asi escucharan los productores del campo la narracion de cada leccion.'
)


@dataclass(frozen=True)
class VoicePreviewResult:
    ok: bool
    voice_id: str
    voice_label: str
    tts: Optional[TtsResult] = None
    error: str = ''


def generar_muestra_voz(
    voice_id: Optional[str],
    *,
    voice_label: str = '',
) -> VoicePreviewResult:
    vid = (voice_id or '').strip()
    if not vid:
        return VoicePreviewResult(
            ok=False,
            voice_id='',
            voice_label=voice_label,
            error='Voice ID vacio — configure en curso/modulo o ELEVENLABS_VOICE_ID',
        )

    tts = generar_narracion(MUESTRA_VOZ_TEXTO, provider='elevenlabs', voice=vid)
    if not tts:
        return VoicePreviewResult(
            ok=False,
            voice_id=vid,
            voice_label=voice_label,
            error=ultimo_error_tts() or 'TTS fallo',
        )

    return VoicePreviewResult(
        ok=True,
        voice_id=vid,
        voice_label=voice_label or vid,
        tts=tts,
    )
