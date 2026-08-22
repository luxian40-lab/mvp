"""Saldo y gasto Twilio para la barra del admin (cacheado; nunca lanza)."""
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


def _fmt_money(amount: float, cur: str) -> str:
    cur = (cur or 'USD').upper()
    if cur == 'USD':
        return f'${amount:,.2f}'
    return f'{amount:,.2f} {cur}'


def _fetch_badge() -> tuple[str, str]:
    sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip()
    token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
    if not sid or not token:
        return 'Twilio sin credenciales', 'danger'
    try:
        from twilio.rest import Client

        client = Client(sid, token)
        bal = client.api.v2010.balance.fetch()
        amount = float(bal.balance)
        cur = (bal.currency or 'USD').upper()
        queda = _fmt_money(amount, cur)

        gastado = None
        try:
            rows = client.usage.records.this_month.list(category='totalprice', limit=1)
            if rows:
                gastado = float(rows[0].price)
        except Exception:
            logger.info('Twilio usage this_month no disponible', exc_info=True)

        if gastado is not None:
            texto = f'Twilio { _fmt_money(gastado, cur) } este mes · {queda} queda'
        else:
            texto = f'Twilio {queda} queda'

        if amount < 15:
            tone = 'danger'
        elif amount < 40:
            tone = 'warning'
        else:
            tone = 'info'
        return texto, tone
    except Exception:
        logger.warning('No se pudo leer saldo Twilio', exc_info=True)
        return 'Twilio saldo no leído', 'danger'
