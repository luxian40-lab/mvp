"""Alertas ops → Slack (webhook opcional)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def slack_ops_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_SLACK_OPS_WEBHOOK', '') or '')


def notify_slack_ops(text: str, *, title: str | None = None) -> bool:
    """
    Envía mensaje al canal ops si EKI_SLACK_OPS_WEBHOOK está configurado.
    Silencioso si no hay webhook (local/dev).
    """
    url = (getattr(settings, 'EKI_SLACK_OPS_WEBHOOK', '') or '').strip()
    if not url:
        return False
    payload = {'text': text}
    if title:
        payload['text'] = f'*{title}*\n{text}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json', 'User-Agent': 'eki-ops/1.0'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning('Slack ops notify falló: %s', exc)
        return False
