"""Imágenes educativas vía OpenAI (DALL-E 3) → local + S3."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.conf import settings

from core.course_engine.budget import COST_IMAGE_USD
from core.course_engine.types import Scene, SceneType
from core.twilio_media import _subir_bytes_s3

logger = logging.getLogger(__name__)

S3_PREFIX = 'media/course_engine/images'


@dataclass(frozen=True)
class ImageResult:
    local_path: Path
    url: Optional[str]
    s3_key: Optional[str]
    cost_usd: float


def _quality_for_model(model: str) -> str:
    """gpt-image-1: low|medium|high|auto; dall-e-3: standard|hd."""
    if 'dall-e' in model.lower():
        return 'standard'
    return 'medium'


def _prompt_escena(escena: Scene) -> str:
    base = (escena.notas_visuales or escena.titulo or 'Ilustración educativa rural').strip()
    if escena.tipo == SceneType.DIAGRAMA:
        return (
            f'Diagrama educativo simple, estilo infografía clara, fondo blanco, '
            f'sin texto ilegible, para WhatsApp rural: {base}'
        )
    return (
        f'Ilustración educativa realista, campo rural latinoamericano, '
        f'luz natural, sin marcas de agua, sin texto en imagen: {base}'
    )


def generar_imagen_escena(
    escena: Scene,
    run_dir: Path,
    *,
    openai_client=None,
    subir_s3: bool = True,
) -> Optional[ImageResult]:
    prompt = _prompt_escena(escena)
    ph = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]
    out_dir = run_dir / 'images'
    out_dir.mkdir(parents=True, exist_ok=True)
    local_path = out_dir / f'escena_{escena.orden:02d}_{ph}.png'

    if local_path.is_file():
        return ImageResult(local_path=local_path, url=None, s3_key=None, cost_usd=0.0)

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        model = getattr(settings, 'COURSE_ENGINE_IMAGE_MODEL', 'gpt-image-1')
        quality = getattr(settings, 'COURSE_ENGINE_IMAGE_QUALITY', '') or _quality_for_model(model)
        kwargs = {
            'model': model,
            'prompt': prompt[:4000],
            'size': '1024x1024',
            'n': 1,
        }
        if quality:
            kwargs['quality'] = quality
        resp = openai_client.images.generate(**kwargs)
        item = resp.data[0]
        data = None
        if getattr(item, 'b64_json', None):
            import base64

            data = base64.b64decode(item.b64_json)
        elif getattr(item, 'url', None):
            import httpx

            dl = httpx.get(item.url, timeout=90, follow_redirects=True)
            dl.raise_for_status()
            data = dl.content
        if not data:
            return None
        local_path.write_bytes(data)
    except Exception as exc:
        logger.exception('DALL-E escena %s: %s', escena.orden, exc)
        return None

    url = None
    s3_key = None
    if subir_s3:
        s3_key = f'{S3_PREFIX}/{ph}.png'
        url = _subir_bytes_s3(s3_key, local_path.read_bytes(), 'image/png')

    return ImageResult(
        local_path=local_path,
        url=url,
        s3_key=s3_key,
        cost_usd=COST_IMAGE_USD,
    )
