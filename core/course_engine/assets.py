"""Generación de assets por escena (local-first; S3 opcional)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from django.conf import settings

from core.course_engine.tts import generar_narracion
from core.course_engine.types import Scene, SceneType, Storyboard

logger = logging.getLogger(__name__)

# Escenas que llevan voz
_NARRATION_TYPES = frozenset({SceneType.NARRACION, SceneType.RESUMEN})


def generar_assets_storyboard(
    storyboard: Storyboard,
    run_dir: Path,
    *,
    generar_audio: bool = True,
    stub_visual: bool = True,
) -> Storyboard:
    """
    Por cada escena: narración → ElevenLabs/OpenAI → S3;
    visuales → stub JSON local (imagen/video_ia pendiente integración).
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = run_dir / 'assets'
    assets_dir.mkdir(exist_ok=True)

    nuevas: list[Scene] = []
    for escena in storyboard.escenas:
        meta = dict(escena.metadata)
        updated = Scene(
            orden=escena.orden,
            tipo=escena.tipo,
            titulo=escena.titulo,
            guion=escena.guion,
            duracion_seg=escena.duracion_seg,
            notas_visuales=escena.notas_visuales,
            asset_url=escena.asset_url,
            asset_s3_key=escena.asset_s3_key,
            metadata=meta,
        )

        if generar_audio and escena.tipo in _NARRATION_TYPES and escena.guion.strip():
            tts = generar_narracion(escena.guion)
            if tts:
                updated.asset_url = tts.url
                updated.asset_s3_key = tts.s3_key
                meta['tts_provider'] = tts.provider
                meta['tts_voice'] = tts.voice
                updated.metadata = meta
            else:
                meta['tts_error'] = True
                updated.metadata = meta

        if stub_visual and escena.tipo in {
            SceneType.IMAGEN,
            SceneType.IMAGEN_ZOOM,
            SceneType.DIAGRAMA,
            SceneType.VIDEO_IA,
            SceneType.TEXTO,
        }:
            stub_path = assets_dir / f'escena_{escena.orden:02d}_{escena.tipo.value}.json'
            stub_path.write_text(
                _stub_visual_json(escena),
                encoding='utf-8',
            )
            meta['visual_stub'] = str(stub_path)
            updated.metadata = meta

        nuevas.append(updated)

    return Storyboard(
        titulo_leccion=storyboard.titulo_leccion,
        objetivo=storyboard.objetivo,
        escenas=nuevas,
        modelo_ia=storyboard.modelo_ia,
    )


def _stub_visual_json(escena: Scene) -> str:
    import json

    return json.dumps(
        {
            'orden': escena.orden,
            'tipo': escena.tipo.value,
            'titulo': escena.titulo,
            'notas_visuales': escena.notas_visuales,
            'status': 'stub_local',
            'pendiente': 'integrar DALL-E / ffmpeg / video IA',
        },
        ensure_ascii=False,
        indent=2,
    )
