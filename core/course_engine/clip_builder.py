"""Clips por escena: imagen + audio → MP4 (ffmpeg)."""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from core.course_engine.types import SceneType

logger = logging.getLogger(__name__)

# 1280x720 H.264 — apto WA tras faststart; vertical 1080x1920 vía COURSE_ENGINE_ASPECT
_W = 1280
_H = 720
_V_W = 1080
_V_H = 1920
_FPS_TARJETA = 15


def _aspect_vertical() -> bool:
    try:
        from django.conf import settings

        return getattr(settings, 'COURSE_ENGINE_ASPECT', '16:9') == '9:16'
    except Exception:
        return False


def _out_wh() -> tuple[int, int]:
    if _aspect_vertical():
        return _V_W, _V_H
    return _W, _H


def _vf_pad_output(base: str) -> str:
    ow, oh = _out_wh()
    if ow == _W and oh == _H:
        return base
    return f"{base},scale={ow}:-2,pad={ow}:{oh}:0:(oh-ih)/2:color=0x121018"


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


def _escape_drawtext(text: str) -> str:
    """Escape para filtro drawtext de ffmpeg."""
    t = (text or '').strip().replace('\n', ' ')
    for ch, rep in (('\\', '\\\\'), ("'", "\\'"), (':', '\\:'), ('%', '\\%')):
        t = t.replace(ch, rep)
    return t


def _wrap_text(text: str, max_chars: int = 42) -> list[str]:
    words = (text or '').split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = ' '.join(cur + [w])
        if len(trial) > max_chars and cur:
            lines.append(' '.join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(' '.join(cur))
    return lines[:4]


def _ms_to_srt(ms: int) -> str:
    ms = max(0, int(ms))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def _escribir_srt(srt_path: Path, texto: str, duracion_seg: float) -> None:
    """SRT UTF-8 para filtro subtitles (sin depender de fontconfig)."""
    lineas = _wrap_text(texto, max_chars=48)
    if not lineas:
        lineas = ['']
    cuerpo = '\n'.join(lineas)
    fin = _ms_to_srt(int(max(0.5, duracion_seg) * 1000))
    contenido = f'1\n00:00:00,000 --> {fin}\n{cuerpo}\n'
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(contenido, encoding='utf-8')


def _escape_subtitles_path(path: Path) -> str:
    p = str(path.resolve()).replace('\\', '/')
    return p.replace(':', '\\:').replace("'", "\\'")


def _vf_subtitulos_inferior(base_vf: str, srt_path: Path, *, franja_legible: bool = False) -> str:
    """Subtítulos inferiores vía SRT (sin fontconfig).

    franja_legible: franja oscura semitransparente — necesaria sobre lámina blanca/morada.
    """
    sp = _escape_subtitles_path(srt_path)
    if franja_legible:
        style = (
            "force_style='FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
            "BackColour=&H80000000&,BorderStyle=3,Outline=1,Alignment=2,MarginV=22'"
        )
    else:
        style = (
            "force_style='FontSize=20,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
            "BorderStyle=3,Outline=1,Alignment=2,MarginV=24'"
        )
    return f"{base_vf},subtitles='{sp}':{style}"


def _vf_text_overlay(
    base_vf: str,
    overlay_text: str,
    *,
    posicion: str = 'centro',
    duracion: float = 5.0,
    srt_path: Optional[Path] = None,
    franja_legible: bool = False,
) -> str:
    lines = _wrap_text(overlay_text)
    if not lines:
        return base_vf
    if posicion == 'inferior':
        dest = srt_path or Path(tempfile.gettempdir()) / f'eki_ce_sub_{abs(hash(overlay_text)) & 0xFFFFFFFF:08x}.srt'
        _escribir_srt(dest, overlay_text, duracion)
        return _vf_subtitulos_inferior(base_vf, dest, franja_legible=franja_legible)
    y0 = 520 - (len(lines) * 28)
    filters = [base_vf]
    font = _drawtext_fontfile()
    font_part = f"fontfile={font}:" if font else ''
    for i, line in enumerate(lines):
        esc = _escape_drawtext(line)
        y = y0 + i * 56
        filters.append(
            f"drawtext={font_part}text='{esc}':fontcolor=white:fontsize=34:borderw=2:bordercolor=black@0.85:"
            f"x=(w-text_w)/2:y={y}"
        )
    return ','.join(filters)


def _drawtext_fontfile() -> str:
    """Ruta TTF para drawtext (centro legacy); vacío si no hay fuente."""
    candidatas = [
        Path(__file__).resolve().parent.parent / 'fonts' / 'GreatVibes-Regular.ttf',
        Path('/var/app/current/core/fonts/GreatVibes-Regular.ttf'),
        Path('C:/Windows/Fonts/arial.ttf'),
    ]
    for p in candidatas:
        if p.is_file():
            return _escape_subtitles_path(p)
    return ''


def recortar_audio(
    audio_path: Path,
    salida: Path,
    *,
    inicio_seg: float = 0.0,
    duracion_seg: float = 0.0,
) -> bool:
    """Extrae un segmento de audio para sincronizar con un clip visual."""
    if not audio_path.is_file():
        return False
    salida.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.3, float(duracion_seg))
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(max(0.0, inicio_seg)),
        '-i', str(audio_path),
        '-t', str(dur),
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
        str(salida),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
        return salida.is_file() and salida.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.error('ffmpeg recortar_audio: %s', exc.stderr[:400])
        return False


def recortar_video_duracion(video_path: Path, salida: Path, *, max_seg: float) -> bool:
    """Recorta MP4 a max_seg (demo studio)."""
    if not video_path.is_file() or max_seg <= 0:
        return False
    salida.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-t', str(max_seg),
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        str(salida),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
        return salida.is_file() and salida.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.error('ffmpeg recortar_video_duracion: %s', exc.stderr[:400] if exc.stderr else exc)
        return False


def construir_clip_escena(
    *,
    imagen_path: Path,
    audio_path: Optional[Path],
    tipo: SceneType,
    duracion_objetivo: float,
    salida: Path,
    overlay_text: str = '',
) -> bool:
    if not imagen_path.is_file():
        logger.error('Imagen no existe: %s', imagen_path)
        return False

    dur = duracion_objetivo
    if audio_path and audio_path.is_file():
        dur = max(duracion_objetivo, _audio_duration_sec(audio_path))

    vf = _vf_for_scene(tipo, dur)
    if overlay_text.strip() and tipo in {SceneType.TEXTO, SceneType.RESUMEN}:
        vf = _vf_text_overlay(vf, overlay_text, duracion=dur)
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


def construir_clip_desde_video_ia(
    *,
    video_path: Path,
    audio_path: Optional[Path],
    salida: Path,
    duracion_objetivo: float = 0.0,
) -> bool:
    """Combina clip Runway + narracion; extiende video si el audio es más largo."""
    if not video_path.is_file():
        logger.error('Video IA no existe: %s', video_path)
        return False

    audio_dur = _audio_duration_sec(audio_path) if audio_path and audio_path.is_file() else 0.0
    target_dur = max(duracion_objetivo, audio_dur, 1.0)

    salida.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-stream_loop', '-1', '-i', str(video_path)]
    if audio_path and audio_path.is_file():
        cmd.extend(['-i', str(audio_path)])
        if audio_dur < target_dur - 0.05:
            cmd.extend([
                '-filter_complex', f'[1:a]apad=whole_dur={target_dur}[aout]',
                '-map', '0:v:0', '-map', '[aout]',
            ])
        else:
            cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])
        cmd.extend([
            '-t', str(target_dur),
            '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
            '-movflags', '+faststart', str(salida),
        ])
    else:
        cmd.extend([
            '-t', str(target_dur),
            '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart', str(salida),
        ])

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
        return salida.is_file() and salida.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.error('ffmpeg video_ia: %s', exc.stderr[:500])
        return False


def construir_segmento_imagen(
    *,
    imagen_path: Path,
    audio_path: Optional[Path],
    salida: Path,
    duracion_seg: float,
    subtitulo: str = '',
    zoom: bool = False,
    subtitulo_franja: bool = False,
) -> bool:
    """Segmento estático (tarjeta o keyframe) con subtítulo inferior y audio."""
    if not imagen_path.is_file():
        return False
    dur = max(0.5, float(duracion_seg))
    if audio_path and audio_path.is_file():
        dur = max(dur, _audio_duration_sec(audio_path))

    tipo = SceneType.IMAGEN_ZOOM if zoom else SceneType.IMAGEN
    if _aspect_vertical():
        ow, oh = _out_wh()
        vf = f'scale={ow}:{oh}:force_original_aspect_ratio=decrease,pad={ow}:{oh}:(ow-iw)/2:(oh-ih)/2'
    else:
        vf = _vf_for_scene(tipo, dur)
    if subtitulo.strip():
        vf = _vf_text_overlay(
            vf,
            subtitulo,
            posicion='inferior',
            duracion=dur,
            srt_path=salida.with_suffix('.srt'),
            franja_legible=subtitulo_franja,
        )

    salida.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-loop', '1', '-i', str(imagen_path)]
    if audio_path and audio_path.is_file():
        cmd.extend(['-i', str(audio_path)])
    else:
        cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'])

    cmd.extend([
        '-t', str(dur),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
        '-movflags', '+faststart', '-shortest',
        str(salida),
    ])
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
        return salida.is_file() and salida.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.error('ffmpeg segmento imagen: %s\nstderr: %s', salida.name, (exc.stderr or '')[-1200:])
        return False


def _vf_ken_burns_suave(duracion_seg: float) -> str:
    """Pan/zoom muy lento — sensación NotebookLM sin tapar texto."""
    fps = 25
    frames = max(int(duracion_seg * fps), 1)
    return (
        f"scale={_W * 2}:{_H * 2},"
        f"zoompan=z='min(1.0+0.00035*on,1.06)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={_W}x{_H}:fps={fps}"
    )


def construir_segmento_tarjeta_animada(
    *,
    frames: list[Path],
    audio_path: Optional[Path],
    salida: Path,
    ken_burns: bool = False,
    fps: int = _FPS_TARJETA,
) -> bool:
    """Lámina animada: secuencia PNG + audio. Split 9:16 usa framerate fijo."""
    frames = sorted(f for f in frames if f.is_file())
    if not frames:
        return False

    dur = max(0.5, float(_audio_duration_sec(audio_path) if audio_path and audio_path.is_file() else 5.0))
    ow, oh = _out_wh()
    salida.parent.mkdir(parents=True, exist_ok=True)

    split_fps = frames[0].name.startswith('frame_')
    if split_fps:
        parent = frames[0].parent
        pattern = str(parent / 'frame_%05d.png')
        vf = f'scale={ow}:{oh}:flags=lanczos,format=yuv420p'
        cmd = ['ffmpeg', '-y', '-framerate', str(fps), '-start_number', '0', '-i', pattern]
        if audio_path and audio_path.is_file():
            cmd.extend(['-i', str(audio_path)])
        else:
            cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'])
        cmd.extend([
            '-t', str(dur),
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
            '-movflags', '+faststart', '-shortest',
            str(salida),
        ])
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
            return salida.is_file() and salida.stat().st_size > 0
        except subprocess.CalledProcessError as exc:
            logger.error('ffmpeg tarjeta split: %s\nstderr: %s', salida.name, (exc.stderr or '')[-1200:])
            return False

    n = len(frames)
    seg_dur = max(0.45, dur / n)

    lista = salida.parent / f'{salida.stem}_frames.txt'
    lines: list[str] = []
    for i, frame in enumerate(frames):
        safe = str(frame.resolve()).replace("'", "'\\''")
        lines.append(f"file '{safe}'")
        lines.append(f"duration {seg_dur:.3f}")
    safe_last = str(frames[-1].resolve()).replace("'", "'\\''")
    lines.append(f"file '{safe_last}'")
    lista.write_text('\n'.join(lines), encoding='utf-8')

    scale_pad = f'scale={ow}:{oh}:force_original_aspect_ratio=decrease,pad={ow}:{oh}:(ow-iw)/2:(oh-ih)/2'
    if ken_burns:
        vf = _vf_ken_burns_suave(dur)
        vf = _vf_pad_output(vf.split(f':s={_W}x{_H}')[0]) if _W not in vf else vf
    else:
        vf = scale_pad
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(lista)]
    if audio_path and audio_path.is_file():
        cmd.extend(['-i', str(audio_path)])
    else:
        cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'])

    cmd.extend([
        '-t', str(dur),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
        '-movflags', '+faststart', '-shortest',
        str(salida),
    ])
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=240, check=True)
        return salida.is_file() and salida.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.error('ffmpeg tarjeta animada: %s\nstderr: %s', salida.name, (exc.stderr or '')[-1200:])
        return False


def construir_segmento_video_ia(
    *,
    video_path: Path,
    audio_path: Optional[Path],
    salida: Path,
    duracion_seg: float,
    subtitulo: str = '',
) -> bool:
    """Clip Runway con subtítulo inferior y audio sincronizado."""
    if not video_path.is_file():
        return False
    dur = max(0.5, float(duracion_seg))
    if audio_path and audio_path.is_file():
        dur = max(dur, _audio_duration_sec(audio_path))

    vf_scale = f'scale={_W}:{_H}:force_original_aspect_ratio=decrease,pad={_W}:{_H}:(ow-iw)/2:(oh-ih)/2'
    vf_scale = _vf_pad_output(vf_scale)
    if subtitulo.strip():
        vf = _vf_text_overlay(
            vf_scale,
            subtitulo,
            posicion='inferior',
            duracion=dur,
            srt_path=salida.with_suffix('.srt'),
        )
    else:
        vf = vf_scale

    salida.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-stream_loop', '-1', '-i', str(video_path)]
    if audio_path and audio_path.is_file():
        cmd.extend(['-i', str(audio_path)])
        cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])
    else:
        cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'])
        cmd.extend(['-map', '0:v:0', '-map', '2:a:0'])

    cmd.extend([
        '-t', str(dur),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
        '-movflags', '+faststart', '-shortest',
        str(salida),
    ])
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
        return salida.is_file() and salida.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.error('ffmpeg segmento video_ia: %s\nstderr: %s', salida.name, (exc.stderr or '')[-1200:])
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
