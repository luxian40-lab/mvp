"""Composición video final (ffmpeg) — stub local + path futuro S3."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from core.course_engine.types import Storyboard

logger = logging.getLogger(__name__)


def componer_video_local(
    storyboard: Storyboard,
    run_dir: Path,
) -> tuple[Optional[Path], list[str]]:
    """
    MVP local: manifest de composición + ffmpeg solo si hay audio narración.

    Returns:
        (path_video_or_none, warnings)
    """
    warnings: list[str] = []
    compose_dir = run_dir / 'compose'
    compose_dir.mkdir(exist_ok=True)

    manifest = {
        'titulo': storyboard.titulo_leccion,
        'escenas': [s.to_dict() for s in storyboard.escenas],
        'ffmpeg_disponible': bool(shutil.which('ffmpeg')),
    }
    manifest_path = compose_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    audios = [
        s for s in storyboard.escenas
        if s.asset_s3_key and s.tipo.value in ('narracion', 'resumen')
    ]
    if not audios:
        warnings.append('Sin audios generados — composición omitida')
        return None, warnings

    if not shutil.which('ffmpeg'):
        warnings.append('ffmpeg no instalado — solo manifest.json')
        return None, warnings

    # MVP: placeholder video negro + primer audio (descarga manual pendiente en local sin S3 pull)
    warnings.append(
        'Composición ffmpeg completa pendiente (concat escenas + visuales). '
        'Manifest listo en compose/manifest.json'
    )
    return None, warnings


def subir_video_s3(local_path: Path, run_id: str) -> Optional[str]:
    """Sube MP4 final a S3 cuando exista archivo local."""
    if not local_path.is_file():
        return None
    try:
        from core.twilio_media import _subir_bytes_s3

        data = local_path.read_bytes()
        key = f'media/course_engine/videos/{run_id}.mp4'
        return _subir_bytes_s3(key, data, 'video/mp4')
    except Exception as exc:
        logger.exception('subir_video_s3: %s', exc)
        return None
