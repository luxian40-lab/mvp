"""
Validación de firma Twilio en webhooks WhatsApp.

Orden: bytes crudos (request.body) → HMAC vía RequestValidator
(usa hmac.compare_digest) → recién entonces el caller parsea/procesa.
"""
from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


def twilio_signature_validation_enabled() -> bool:
    return bool(getattr(settings, 'TWILIO_VALIDATE_SIGNATURE', False))


def looks_like_meta_whatsapp_payload(raw_body: bytes) -> bool:
    """True si el body JSON parece webhook Meta Cloud API (entry/object)."""
    if not raw_body:
        return False
    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return False
    return isinstance(payload, dict) and ('entry' in payload or payload.get('object') == 'whatsapp_business_account')


def _public_webhook_url(request: HttpRequest) -> str:
    """
    URL absoluta que Twilio firmó. Respeta override y X-Forwarded-Proto (EB/ALB).
    """
    override = (getattr(settings, 'TWILIO_WEBHOOK_PUBLIC_URL', '') or '').strip()
    if override:
        base = override.rstrip('/')
        path = request.path
        if not path.startswith('/'):
            path = '/' + path
        qs = request.META.get('QUERY_STRING', '')
        url = f'{base}{path}'
        if qs:
            url = f'{url}?{qs}'
        return url

    url = request.build_absolute_uri()
    forwarded = (request.META.get('HTTP_X_FORWARDED_PROTO') or '').split(',')[0].strip().lower()
    if forwarded == 'https' and url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    elif getattr(settings, 'SECURE_SSL_REDIRECT', False) and url.startswith('http://'):
        url = 'https://' + url[len('http://'):]

    # Normalizar sin fragment
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))


def validate_twilio_request(request: HttpRequest) -> Optional[HttpResponse]:
    """
    Valida X-Twilio-Signature. Retorna HttpResponse 403 si falla, None si OK / skip.
    """
    if not twilio_signature_validation_enabled():
        return None

    # Touch raw body primero (canon: bytes crudos antes de confiar en el request)
    raw_body = request.body

    signature = (request.META.get('HTTP_X_TWILIO_SIGNATURE') or '').strip()
    if not signature:
        logger.warning(
            'twilio_webhook_rejected',
            extra={'reason': 'missing_signature', 'path': request.path},
        )
        return HttpResponse('Forbidden', status=403)

    auth_token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
    if not auth_token:
        logger.error(
            'twilio_webhook_rejected',
            extra={'reason': 'missing_auth_token', 'path': request.path},
        )
        return HttpResponse('Forbidden', status=403)

    from twilio.request_validator import RequestValidator

    url = _public_webhook_url(request)
    validator = RequestValidator(auth_token)
    content_type = (request.content_type or '').lower()

    if 'application/json' in content_type or (
        raw_body[:1] in (b'{', b'[') and 'application/x-www-form-urlencoded' not in content_type
    ):
        # JSON: body string (soporta bodySHA256 en query si aplica)
        params = raw_body.decode('utf-8') if raw_body else ''
        ok = validator.validate(url, params, signature)
    else:
        # form-urlencoded típico de Twilio WhatsApp
        ok = validator.validate(url, request.POST, signature)

    if not ok:
        logger.warning(
            'twilio_webhook_rejected',
            extra={'reason': 'invalid_signature', 'path': request.path},
        )
        return HttpResponse('Forbidden', status=403)

    return None
