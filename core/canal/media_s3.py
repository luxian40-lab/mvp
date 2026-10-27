"""URLs públicas de S3 para la media de WhatsApp. Sin imports de core."""
from __future__ import annotations

from typing import Optional


def _encode_s3_key_path(key: str) -> str:
    """
    Codifica key S3 para URL pública.

    Usa unquote_plus: en prod muchas keys/URLs tienen '+' donde el objeto real
    tiene espacio (p.ej. '2.2.+Presupuesto' → 404; '%20' → 200).
    """
    from urllib.parse import quote, unquote_plus

    parts = []
    for part in (key or '').lstrip('/').split('/'):
        if not part:
            continue
        parts.append(quote(unquote_plus(part), safe=''))
    return '/'.join(parts)


def normalizar_media_url_s3(url: Optional[str]) -> Optional[str]:
    """
    URL pública regional (us-east-2) para MediaUrl de Twilio.

    Importante: NO reescribir el host de una URL firmada (X-Amz-*) — eso invalida
    la firma (403) y Twilio responde 63019. Si viene firmada, se convierte a URL
    pública regional del objeto.
    """
    if not url:
        return None
    clean = str(url).strip()
    if not clean:
        return None

    lower = clean.lower()
    firmada = 'x-amz-signature' in lower or 'x-amz-algorithm' in lower
    if 'amazonaws.com' in lower or 'eki-produccion' in lower:
        key = _s3_key_desde_url(clean)
        if key:
            encoded = _encode_s3_key_path(key)
            return f'https://eki-produccion.s3.us-east-2.amazonaws.com/{encoded}'
        if firmada:
            # Sin key parseable: mejor no tocar host (firma intacta)
            return clean
        if '.s3.amazonaws.com/' in clean and '.s3.us-east-2.amazonaws.com/' not in clean:
            clean = clean.replace('.s3.amazonaws.com/', '.s3.us-east-2.amazonaws.com/')
            # Quitar query de firma si quedó basura
            if '?' in clean and 'x-amz-' in clean.lower():
                clean = clean.split('?', 1)[0]
    return clean


def _s3_key_desde_url(url: str) -> Optional[str]:
    from urllib.parse import unquote_plus, urlparse

    p = urlparse(url)
    host = (p.netloc or '').lower()
    # unquote_plus: '+' en path → espacio (misencoding frecuente en catálogo)
    path = unquote_plus(p.path or '').lstrip('/')
    if not path:
        return None
    if 'eki-produccion' in host or 'amazonaws.com' in host:
        if path.startswith('eki-produccion/'):
            path = path[len('eki-produccion/') :]
        return path
    return None
