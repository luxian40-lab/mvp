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


def preparar_mp4_eki_wa_v1(data: bytes) -> tuple[bytes | None, dict]:
    """
    Gate eki_wa_v1 — mismo criterio que Module Builder (H.264 Main, faststart, ≤16 MB).
    Returns (bytes_ready, gate_dict). bytes_ready None si no pasa el gate.
    """
    from core.twilio_media import (
        evaluar_mp4_listo_whatsapp,
        optimizar_mp4_bytes_whatsapp,
        remux_mp4_faststart,
    )

    if not data:
        return None, {'apto': False, 'razon': 'vacio', 'bytes': 0}

    gate_pre = evaluar_mp4_listo_whatsapp(data)
    out = data
    if gate_pre.get('apto'):
        if gate_pre.get('necesita_faststart'):
            out = remux_mp4_faststart(data) or data
    else:
        out = optimizar_mp4_bytes_whatsapp(data) or data

    gate = evaluar_mp4_listo_whatsapp(out)
    if not gate.get('apto'):
        logger.error(
            'Course Engine MP4 no apto WA (%s, %s bytes)',
            gate.get('razon'),
            gate.get('bytes'),
        )
        return None, gate
    return out, gate


def subir_video_s3(local_path: Path, run_id: str) -> Optional[str]:
    """Sube MP4 final a S3 tras gate eki_wa_v1 (WhatsApp rural)."""
    if not local_path.is_file():
        return None
    try:
        raw = local_path.read_bytes()
        prepared, gate = preparar_mp4_eki_wa_v1(raw)
        if prepared is None:
            return None
        from core.twilio_media import _subir_bytes_s3

        safe_rid = ''.join(c if c.isalnum() or c in '-_' else '_' for c in (run_id or ''))[:40]
        key = f'media/course_engine/videos/wa_safe/{safe_rid}_h264_main_faststart.mp4'
        url = _subir_bytes_s3(key, prepared, 'video/mp4')
        if url:
            logger.info(
                'Course Engine video WA OK run=%s apto=%s bytes=%s',
                run_id,
                gate.get('apto'),
                gate.get('bytes'),
            )
        return url
    except Exception as exc:
        logger.exception('subir_video_s3: %s', exc)
        return None


def subir_asset_s3(
    local_path: Path,
    run_id: str,
    *,
    ext: str,
    content_type: str,
    subpath: str,
) -> Optional[str]:
    if not local_path.is_file():
        return None
    try:
        from core.twilio_media import _subir_bytes_s3

        data = local_path.read_bytes()
        key = f'media/course_engine/{subpath}/{run_id}.{ext}'
        return _subir_bytes_s3(key, data, content_type)
    except Exception as exc:
        logger.exception('subir_asset_s3: %s', exc)
        return None
