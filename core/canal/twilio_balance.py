"""Saldo y gasto Twilio para la barra del admin (cacheado; nunca lanza)."""
from __future__ import annotations

import json
import logging
from base64 import b64encode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_KEY = 'eki_twilio_account_balance_v2'
_CACHE_TTL_OK = 900
_CACHE_TTL_FAIL = 45


def twilio_balance_badge() -> tuple[str, str]:
    cached = cache.get(_CACHE_KEY)
    if isinstance(cached, tuple) and len(cached) == 2:
        return cached[0], cached[1]
    label, tone = _fetch_badge()
    ttl = _CACHE_TTL_FAIL if tone == 'danger' and 'queda' not in label.lower() else _CACHE_TTL_OK
    if 'queda' in label.lower() or 'este mes' in label.lower():
        ttl = _CACHE_TTL_OK
    cache.set(_CACHE_KEY, (label, tone), ttl)
    return label, tone


def _creds() -> tuple[str, str]:
    sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip().strip('"').strip("'")
    token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip().strip('"').strip("'")
    return sid, token


def _fmt_money(amount: float, cur: str) -> str:
    cur = (cur or 'USD').upper()
    if cur == 'USD':
        return f'${amount:,.2f}'
    return f'{amount:,.2f} {cur}'


def _http_json(url: str, sid: str, token: str) -> dict:
    auth = b64encode(f'{sid}:{token}'.encode()).decode('ascii')
    req = Request(
        url,
        headers={
            'Authorization': f'Basic {auth}',
            'Accept': 'application/json',
        },
        method='GET',
    )
    with urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _fetch_badge() -> tuple[str, str]:
    sid, token = _creds()
    if not sid or not token:
        return 'Twilio sin credenciales', 'danger'
    if not sid.startswith('AC'):
        logger.warning('TWILIO_ACCOUNT_SID no parece Account SID (AC…)')
    try:
        bal_url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Balance.json'
        payload = _http_json(bal_url, sid, token)
        amount = float(payload.get('balance') or 0)
        cur = (payload.get('currency') or 'USD').upper()
        queda = _fmt_money(amount, cur)

        gastado = None
        try:
            usage_url = (
                f'https://api.twilio.com/2010-04-01/Accounts/{sid}'
                f'/Usage/Records/ThisMonth.json?Category=totalprice&PageSize=1'
            )
            usage = _http_json(usage_url, sid, token)
            recs = usage.get('usage_records') or []
            if recs:
                gastado = float(recs[0].get('price') or 0)
        except (HTTPError, URLError, ValueError, TypeError, KeyError):
            logger.info('Twilio usage this_month no disponible', exc_info=True)

        if gastado is not None:
            texto = f'Twilio {_fmt_money(gastado, cur)} este mes · {queda} queda'
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
