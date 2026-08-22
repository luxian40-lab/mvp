"""Saldo Twilio para el badge del admin (cacheado; nunca lanza)."""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_KEY = 'eki_twilio_account_balance'
_CACHE_TTL = 900  # 15 min


def twilio_balance_badge() -> tuple[str, str]:
    """
    (texto, tono Unfold).
    tono: info | warning | danger
    """
    cached = cache.get(_CACHE_KEY)
    if isinstance(cached, tuple) and len(cached) == 2:
        return cached[0], cached[1]
    label, tone = _fetch_badge()
    cache.set(_CACHE_KEY, (label, tone), _CACHE_TTL)
    return label, tone


def _fetch_badge() -> tuple[str, str]:
    sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip()
    token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
    if not sid or not token:
        return 'PRODUCCIÓN', 'danger'
    try:
        from twilio.rest import Client

        bal = Client(sid, token).api.v2010.balance.fetch()
        amount = float(bal.balance)
        cur = (bal.currency or 'USD').upper()
        if cur == 'USD':
            texto = f'Twilio ${amount:,.0f}'
        else:
            texto = f'Twilio {amount:,.0f} {cur}'
        if amount < 15:
            tone = 'danger'
        elif amount < 40:
            tone = 'warning'
        else:
            tone = 'info'
        return texto, tone
    except Exception:
        logger.warning('No se pudo leer saldo Twilio', exc_info=True)
        return 'PRODUCCIÓN', 'danger'
