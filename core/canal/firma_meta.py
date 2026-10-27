"""Firma de los webhooks de Meta (HMAC-SHA256 del body crudo). Sin imports de core."""
from __future__ import annotations

import hashlib
import hmac


def firma_meta_ok(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """HMAC-SHA256 del body crudo. compare_digest, nunca ==."""
    secret = (secret or '').strip()
    header = (signature_header or '').strip()
    if not secret or not header or raw_body is None:
        return False
    if header.lower().startswith('sha256='):
        header = header.split('=', 1)[1].strip()
    digest = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    if len(digest) != len(header):
        return False
    return hmac.compare_digest(digest, header)
