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

        resp = openai_client.images.generate(
            model='dall-e-3',
            prompt=prompt[:4000],
            size='1024x1024',
            quality='standard',
            n=1,
            response_format='b64_json',
        )
        import base64

        b64 = resp.data[0].b64_json
        if not b64:
            return None
        data = base64.b64decode(b64)
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
