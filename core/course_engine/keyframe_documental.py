# -*- coding: utf-8 -*-
"""Genera keyframe documental (OpenAI) para smoke Runway realista."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from django.conf import settings

from core.course_engine.visual_style import prompt_keyframe_documental

logger = logging.getLogger(__name__)


def generar_keyframe_documental(
    run_dir: Path,
    *,
    tema: str = '',
    openai_client=None,
) -> Optional[Path]:
    """PNG local listo para image-to-video Runway."""
    prompt = prompt_keyframe_documental(tema=tema)
    ph = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]
    out_dir = run_dir / 'images'
    out_dir.mkdir(parents=True, exist_ok=True)
    local_path = out_dir / f'keyframe_documental_{ph}.png'

    if local_path.is_file():
        return local_path

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        model = getattr(settings, 'COURSE_ENGINE_IMAGE_MODEL', 'gpt-image-1')
        quality = getattr(settings, 'COURSE_ENGINE_IMAGE_QUALITY', '') or 'medium'
        if 'dall-e' in model.lower():
            quality = 'standard'
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
        return local_path
    except Exception as exc:
        logger.exception('Keyframe documental: %s', exc)
        return None
