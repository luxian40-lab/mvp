"""Clips por escena: imagen + audio → MP4 (ffmpeg)."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from core.course_engine.types import SceneType

logger = logging.getLogger(__name__)

# 1280x720 H.264 — apto WA tras faststart
_W = 1280
_H = 720


def _audio_duration_sec(audio_path: Path) -> float:
    try:
        proc = subprocess.run(
            [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return max(1.0, float(proc.stdout.strip()))
    except Exception:
        return 5.0


def _vf_for_scene(tipo: SceneType, duration: float) -> str:
    fps = 25
    frames = max(int(duration * fps), 1)
    if tipo == SceneType.IMAGEN_ZOOM:
        return (
            f"scale={_W * 2}:{_H * 2},"
            f"zoompan=z='min(zoom+0.0012,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={_W}x{_H}:fps={fps}"
        )
    return f"scale={_W}:{_H}:force_original_aspect_ratio=decrease,pad={_W}:{_H}:(ow-iw)/2:(oh-ih)/2"


def construir_clip_escena(
    *,
    imagen_path: Path,
    audio_path: Optional[Path],
    tipo: SceneType,
    duracion_objetivo: float,
    salida: Path,
) -> bool:
    if not imagen_path.is_file():
        logger.error('Imagen no existe: %s', imagen_path)
        return False

    dur = duracion_objetivo
    if audio_path and audio_path.is_file():
        dur = max(duracion_objetivo, _audio_duration_sec(audio_path))

    vf = _vf_for_scene(tipo, dur)
    salida.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', str(imagen_path),
    ]
    if audio_path and audio_path.is_file():
        cmd.extend(['-i', str(audio_path)])
    else:
        cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'])

    cmd.extend([
        '-t', str(dur),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
        '-movflags', '+faststart',
        '-shortest',
        str(salida),
    ])

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
        return salida.is_file() and salida.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.error('ffmpeg clip escena: %s\n%s', exc.stderr[:500], cmd)
        return False


def concatenar_clips(clips: list[Path], salida: Path) -> bool:
    if not clips:
        return False
    salida.parent.mkdir(parents=True, exist_ok=True)
    lista = salida.parent / 'concat_list.txt'
    lines = []
    for c in clips:
        safe = str(c.resolve()).replace("'", "'\\''")
        lines.append(f"file '{safe}'")
    lista.write_text('\n'.join(lines), encoding='utf-8')

    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(lista),
        '-c', 'copy', '-movflags', '+faststart', str(salida),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
        return salida.is_file()
    except subprocess.CalledProcessError:
        # Re-encode si codecs no coinciden
        cmd2 = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(lista),
            '-c:v', 'libx264', '-c:a', 'aac', '-movflags', '+faststart', str(salida),
        ]
        try:
            subprocess.run(cmd2, capture_output=True, text=True, timeout=300, check=True)
            return salida.is_file()
        except subprocess.CalledProcessError as exc:
            logger.error('ffmpeg concat: %s', exc.stderr[:500])
            return False
