"""Preview de Content Templates Twilio (HX…) para admin de campañas/plantillas."""
from __future__ import annotations

import logging
import re
from html import escape

from django.conf import settings
from django.core.cache import cache
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)

_CACHE_TTL_OK = 300
_CACHE_TTL_FAIL = 45
_VAR_RE = re.compile(r'\{\{(\d+)\}\}')


def content_sid_de_campana(obj) -> str:
    sid = (getattr(obj, 'template_twilio_id', None) or '').strip()
    if sid:
        return sid
    plantilla = getattr(obj, 'plantilla', None)
    if plantilla is not None:
        return (getattr(plantilla, 'twilio_template_sid', None) or '').strip()
    return ''


def fetch_content_preview(sid: str) -> dict:
    """Dict serializable (cache). Nunca lanza."""
    sid = (sid or '').strip()
    empty = {
        'ok': False,
        'sid': sid,
        'name': '',
        'language': '',
        'kind': '',
        'body': '',
        'buttons': [],
        'variables': {},
        'approval': '',
        'error': '',
    }
    if not sid:
        empty['error'] = 'Sin Content SID (HX…).'
        return empty
    if not sid.upper().startswith('HX'):
        empty['error'] = 'El SID no parece un Content SID (HX…).'
        return empty

    cache_key = f'eki_hx_preview_{sid}'
    cached = cache.get(cache_key)
    if isinstance(cached, dict) and 'ok' in cached:
        return cached

    data = dict(empty)
    try:
        data = _fetch_from_twilio(sid)
    except Exception as exc:
        logger.warning('Twilio Content preview falló sid=%s: %s', sid, exc)
        data['error'] = str(exc)[:180]
        data['ok'] = False

    ttl = _CACHE_TTL_OK if data.get('ok') else _CACHE_TTL_FAIL
    cache.set(cache_key, data, ttl)
    return data


def _creds() -> tuple[str, str]:
    sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip().strip('"').strip("'")
    token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip().strip('"').strip("'")
    return sid, token


def _as_dict(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, 'items'):
        try:
            return dict(raw.items())
        except Exception:
            pass
    return {}


def _fetch_from_twilio(sid: str) -> dict:
    from twilio.rest import Client

    account, token = _creds()
    if not account or not token:
        return {
            'ok': False,
            'sid': sid,
            'name': '',
            'language': '',
            'kind': '',
            'body': '',
            'buttons': [],
            'variables': {},
            'approval': '',
            'error': 'Twilio sin credenciales en este entorno.',
        }

    client = Client(account, token)
    content = client.content.v1.contents(sid).fetch()
    types = _as_dict(getattr(content, 'types', None))
    kind, body, buttons = _parse_types(types)
    variables = _as_dict(getattr(content, 'variables', None))
    variables = {str(k): str(v) if v is not None else '' for k, v in variables.items()}

    approval = ''
    try:
        req = client.content.v1.contents(sid).approval_fetch()
        approval = (
            getattr(req, 'whatsapp', None)
            or getattr(req, 'status', None)
            or ''
        )
        if isinstance(approval, dict):
            approval = str(approval.get('status') or approval.get('name') or '')
        approval = str(approval or '')
    except Exception:
        approval = ''

    return {
        'ok': True,
        'sid': sid,
        'name': getattr(content, 'friendly_name', '') or '',
        'language': getattr(content, 'language', '') or '',
        'kind': kind,
        'body': body,
        'buttons': buttons,
        'variables': variables,
        'approval': approval,
        'error': '',
    }


def _parse_types(types: dict) -> tuple[str, str, list]:
    if not types:
        return '', '', []

    order = (
        'twilio/quick-reply',
        'twilio/call-to-action',
        'twilio/card',
        'twilio/carousel',
        'twilio/media',
        'twilio/text',
        'whatsapp/card',
        'whatsapp/quick-reply',
    )
    kind = ''
    payload = {}
    for key in order:
        if key in types and types[key]:
            kind = key
            payload = _as_dict(types[key])
            break
    if not kind:
        kind = next(iter(types))
        payload = _as_dict(types[kind])

    body = (
        payload.get('body')
        or payload.get('title')
        or payload.get('subtitle')
        or ''
    )
    if kind == 'twilio/carousel':
        cards = payload.get('cards') or []
        if cards:
            first = _as_dict(cards[0])
            body = first.get('body') or first.get('title') or body
            extra = _buttons_from(first.get('actions'))
            rest = max(0, len(cards) - 1)
            if rest:
                extra.append({'title': f'+{rest} tarjeta(s) del carrusel', 'kind': 'info'})
            return kind, str(body or ''), extra

    buttons = _buttons_from(payload.get('actions'))
    return kind, str(body or ''), buttons


def _buttons_from(actions) -> list:
    out = []
    if not actions:
        return out
    for raw in actions:
        item = _as_dict(raw)
        title = (item.get('title') or item.get('id') or '').strip()
        if not title:
            continue
        kind = (item.get('type') or item.get('kind') or 'reply').lower()
        out.append({'title': title[:80], 'kind': kind})
    return out[:10]


def highlight_variables(body: str) -> str:
    """HTML escapado con {{n}} resaltados."""
    if not body:
        return ''
    parts = []
    last = 0
    for match in _VAR_RE.finditer(body):
        parts.append(escape(body[last:match.start()]))
        parts.append(
            f'<mark class="eki-hx-var">{{{{{match.group(1)}}}}}</mark>'
        )
        last = match.end()
    parts.append(escape(body[last:]))
    return ''.join(parts).replace('\n', '<br>')


def fill_samples(body: str, variables: dict) -> str:
    def repl(match):
        key = match.group(1)
        sample = variables.get(key) or variables.get(str(key))
        return str(sample) if sample else match.group(0)

    return _VAR_RE.sub(repl, body or '')


def preview_html(data: dict) -> str:
    """Burbuja lista para admin (mark_safe)."""
    if not data:
        return mark_safe('')
    if not data.get('ok'):
        err = escape(data.get('error') or 'No se pudo leer Twilio.')
        sid = escape(data.get('sid') or '')
        return mark_safe(
            f'<p class="eki-hx-miss">No es la plantilla de Meta. {err}'
            f'{" · " + sid if sid else ""}</p>'
        )

    body_html = highlight_variables(data.get('body') or '(sin body en este tipo)')
    sample = fill_samples(data.get('body') or '', data.get('variables') or {})
    sample_html = ''
    if sample and sample != (data.get('body') or ''):
        sample_html = (
            '<p class="eki-hx-sample-label">Con samples de Twilio</p>'
            f'<div class="eki-camp-wa__bubble eki-camp-wa__bubble--sample">'
            f'{escape(sample).replace(chr(10), "<br>")}</div>'
        )

    btns = []
    for btn in data.get('buttons') or []:
        title = escape(btn.get('title') or '')
        btns.append(f'<div class="eki-camp-wa__cta">{title}</div>')
    btns_html = ''.join(btns)

    meta_bits = [
        escape(data.get('sid') or ''),
        escape(data.get('kind') or ''),
        escape(data.get('language') or ''),
    ]
    if data.get('name'):
        meta_bits.insert(1, escape(data['name']))
    if data.get('approval'):
        meta_bits.append('estado ' + escape(str(data['approval'])))
    meta = ' · '.join(b for b in meta_bits if b)

    vars_html = ''
    variables = data.get('variables') or {}
    if variables:
        chips = ''.join(
            f'<code class="eki-hx-chip">{{{{{escape(str(k))}}}}} = {escape(str(v))}</code>'
            for k, v in sorted(variables.items(), key=lambda kv: str(kv[0]))
        )
        vars_html = f'<p class="eki-hx-vars">{chips}</p>'

    return mark_safe(
        f'<div class="eki-camp-wa__bubble">{body_html}{btns_html}</div>'
        f'{sample_html}{vars_html}'
        f'<p class="eki-hx-meta">{meta} · cache ~5 min · no es un envío real</p>'
    )
