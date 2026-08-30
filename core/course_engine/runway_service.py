"""Video IA via Runway Dev API (image-to-video / text-to-video)."""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

RUNWAY_API_BASE = 'https://api.dev.runwayml.com'
RUNWAY_VERSION = '2024-11-06'

# gen4_turbo ~5 credits/s; estimado conservador USD
COST_VIDEO_IA_PER_SEC_USD = 0.05

_ultimo_error: Optional[str] = None


@dataclass(frozen=True)
class RunwayVideoResult:
    local_path: Path
    task_id: str
    duration_sec: int
    cost_usd: float
    model: str
    source_url: Optional[str] = None


def ultimo_error_runway() -> Optional[str]:
    return _ultimo_error


def _set_error(msg: str) -> None:
    global _ultimo_error
    _ultimo_error = msg
    logger.error('Runway: %s', msg)


def runway_disponible() -> bool:
    key = getattr(settings, 'RUNWAY_API_KEY', None)
    return bool(key and str(key).strip())


def _headers() -> dict[str, str]:
    return {
        'Authorization': f'Bearer {settings.RUNWAY_API_KEY}',
        'X-Runway-Version': RUNWAY_VERSION,
        'Content-Type': 'application/json',
    }


def _image_uri(*, local_path: Optional[Path] = None, public_url: Optional[str] = None) -> str:
    # Local primero: más fiable que URL S3 si Runway no puede fetch o hay latencia.
    if local_path and local_path.is_file():
        raw = local_path.read_bytes()
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError(f'Imagen demasiado grande para data URI Runway: {local_path}')
        b64 = base64.b64encode(raw).decode('ascii')
        return f'data:image/png;base64,{b64}'
    if public_url and public_url.startswith('https://'):
        return public_url
    raise ValueError('Se requiere imagen local o URL HTTPS publica')


def _extract_output_urls(task: dict) -> list[str]:
    out = task.get('output')
    if isinstance(out, list):
        return [u for u in out if isinstance(u, str) and u.startswith('http')]
    if isinstance(out, str) and out.startswith('http'):
        return [out]
    artifacts = task.get('artifacts')
    if isinstance(artifacts, list):
        urls = []
        for item in artifacts:
            if isinstance(item, str) and item.startswith('http'):
                urls.append(item)
            elif isinstance(item, dict):
                url = item.get('url') or item.get('uri')
                if isinstance(url, str) and url.startswith('http'):
                    urls.append(url)
        return urls
    return []


def _poll_task(client: httpx.Client, task_id: str, *, timeout_sec: int = 420) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        resp = client.get(f'{RUNWAY_API_BASE}/v1/tasks/{task_id}', headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        status = str(data.get('status', '')).upper()
        if status == 'SUCCEEDED':
            return data
        if status in {'FAILED', 'CANCELLED', 'CANCELED'}:
            detail = data.get('failure') or data.get('failureCode') or data.get('error') or status
            raise RuntimeError(f'Tarea Runway {status}: {detail}')
        time.sleep(5)
    raise TimeoutError(f'Runway task {task_id} no termino en {timeout_sec}s')


def _download_video(client: httpx.Client, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with client.stream('GET', url, follow_redirects=True, timeout=120) as resp:
        resp.raise_for_status()
        dest.write_bytes(resp.read())


def generar_video_desde_imagen(
    *,
    prompt: str,
    run_dir: Path,
    escena_orden: int = 1,
    local_image: Optional[Path] = None,
    image_url: Optional[str] = None,
    duration_sec: Optional[int] = None,
    model: Optional[str] = None,
) -> Optional[RunwayVideoResult]:
    """Image-to-video (gen4_turbo por defecto — mas economico con keyframe)."""
    if not runway_disponible():
        _set_error('RUNWAY_API_KEY no configurada')
        return None

    dur = duration_sec or int(getattr(settings, 'RUNWAY_DURATION_SEC', 4) or 4)
    dur = max(2, min(10, dur))
    mdl = model or getattr(settings, 'RUNWAY_IMAGE_TO_VIDEO_MODEL', 'gen4_turbo')

    try:
        img_uri = _image_uri(local_path=local_image, public_url=image_url)
    except ValueError as exc:
        _set_error(str(exc))
        return None

    body = {
        'model': mdl,
        'promptImage': img_uri,
        'promptText': (prompt or 'Movimiento suave de camara, escena educativa rural')[:1000],
        'ratio': getattr(settings, 'RUNWAY_RATIO', '1280:720'),
        'duration': dur,
    }

    out_dir = run_dir / 'runway'
    out_dir.mkdir(parents=True, exist_ok=True)
    local_out = out_dir / f'escena_{escena_orden:02d}.mp4'

    try:
        with httpx.Client(timeout=60) as client:
            create = client.post(
                f'{RUNWAY_API_BASE}/v1/image_to_video',
                headers=_headers(),
                json=body,
            )
            if create.status_code >= 400:
                _set_error(f'HTTP {create.status_code}: {create.text[:500]}')
                return None
            task_id = create.json().get('id')
            if not task_id:
                _set_error('Runway no devolvio task id')
                return None

            logger.info('Runway task %s (%s, %ss)', task_id, mdl, dur)
            task = _poll_task(client, task_id)
            urls = _extract_output_urls(task)
            if not urls:
                _set_error(f'Tarea OK pero sin URL de video: {task}')
                return None

            _download_video(client, urls[0], local_out)
    except Exception as exc:
        _set_error(str(exc))
        logger.exception('Runway image_to_video')
        return None

    if not local_out.is_file() or local_out.stat().st_size == 0:
        _set_error('Descarga Runway vacia')
        return None

    return RunwayVideoResult(
        local_path=local_out,
        task_id=task_id,
        duration_sec=dur,
        cost_usd=dur * COST_VIDEO_IA_PER_SEC_USD,
        model=mdl,
        source_url=urls[0] if urls else None,
    )


def generar_video_desde_texto(
    *,
    prompt: str,
    run_dir: Path,
    nombre: str = 'text_smoke',
    duration_sec: Optional[int] = None,
    model: Optional[str] = None,
) -> Optional[RunwayVideoResult]:
    """Text-to-video (gen4.5) — util para smoke sin imagen previa."""
    if not runway_disponible():
        _set_error('RUNWAY_API_KEY no configurada')
        return None

    dur = duration_sec or int(getattr(settings, 'RUNWAY_DURATION_SEC', 4) or 4)
    dur = max(2, min(10, dur))
    mdl = model or getattr(settings, 'RUNWAY_TEXT_TO_VIDEO_MODEL', 'gen4.5')

    body = {
        'model': mdl,
        'promptText': prompt[:1000],
        'ratio': getattr(settings, 'RUNWAY_RATIO', '1280:720'),
        'duration': dur,
    }

    out_dir = run_dir / 'runway'
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in nombre)[:40]
    local_out = out_dir / f'{safe}.mp4'

    try:
        with httpx.Client(timeout=60) as client:
            create = client.post(
                f'{RUNWAY_API_BASE}/v1/text_to_video',
                headers=_headers(),
                json=body,
            )
            if create.status_code >= 400:
                _set_error(f'HTTP {create.status_code}: {create.text[:500]}')
                return None
            task_id = create.json().get('id')
            if not task_id:
                _set_error('Runway no devolvio task id')
                return None

            logger.info('Runway text_to_video task %s (%s)', task_id, mdl)
            task = _poll_task(client, task_id)
            urls = _extract_output_urls(task)
            if not urls:
                _set_error(f'Tarea OK pero sin URL: {task}')
                return None

            _download_video(client, urls[0], local_out)
    except Exception as exc:
        _set_error(str(exc))
        logger.exception('Runway text_to_video')
        return None

    return RunwayVideoResult(
        local_path=local_out,
        task_id=task_id,
        duration_sec=dur,
        cost_usd=dur * COST_VIDEO_IA_PER_SEC_USD * 2,
        model=mdl,
        source_url=urls[0] if urls else None,
    )
