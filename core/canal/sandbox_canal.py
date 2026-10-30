"""Canal sandbox WhatsApp: transporte Meta Cloud API (no Twilio).

El menú de agentes y los cursos que salen por ese menú viven aquí.
Los cursos de producción (WABA Twilio) no pasan por este módulo.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
from typing import Any, Iterator

import requests
from django.conf import settings

from core.nati import normalizar_telefono_whatsapp

logger = logging.getLogger(__name__)

PROVEEDOR_META = 'meta'
PROVEEDOR_TWILIO = 'twilio'

_sandbox_meta_ctx: ContextVar[bool] = ContextVar('sandbox_meta_ctx', default=False)

_TEXTO_HABEAS_SANDBOX = (
    "eki (Colombia) tratará sus datos para formación, asesoría y tutoría "
    "asistida por IA en WhatsApp. No los vendemos. Base legal: Ley 1581 de 2012.\n\n"
    "Política completa: https://www.eki.com.co/habeas-data\n\n"
    "Acceso, rectificación o supresión: comunidad.educativa@eki.com.co.\n\n"
    "Pulse *Acepto* para continuar o *No acepto* para no usar el servicio."
)


def sandbox_via_meta() -> bool:
    raw = (getattr(settings, 'SANDBOX_PROVEEDOR', 'meta') or 'meta').strip().lower()
    return raw in ('meta', 'cloud', 'whatsapp_cloud')


def sandbox_phone_id() -> str:
    return (
        (getattr(settings, 'SANDBOX_WHATSAPP_PHONE_ID', '') or '').strip()
        or (getattr(settings, 'WHATSAPP_PHONE_ID', '') or '').strip()
    )


def sandbox_meta_activo() -> bool:
    """True solo dentro de un request/turno sandbox Meta (no redirige Twilio prod)."""
    return bool(_sandbox_meta_ctx.get()) and sandbox_via_meta()


@contextmanager
def canal_sandbox_meta():
    token = _sandbox_meta_ctx.set(True)
    try:
        with patch_twilio_rest_client_si_meta():
            yield
    finally:
        _sandbox_meta_ctx.reset(token)


class _MetaSid:
    def __init__(self, sid: str, status: str = 'sent'):
        self.sid = sid
        self.status = status


class MetaOutboundClient:
    """Sustituye twilio.rest.Client durante un turno sandbox Meta (sync worker)."""

    def __init__(self, *args, **kwargs):
        self.messages = self

    def create(self, **params):
        body = params.get('body') or ''
        media = params.get('media_url')
        if isinstance(media, (list, tuple)):
            media = media[0] if media else None
        to = params.get('to') or ''
        result = enviar_meta(to, body, media_url=media)
        if not result.get('success'):
            raise RuntimeError(str(result.get('response') or 'meta send failed'))
        return _MetaSid(result.get('mensaje_id') or '')


@contextmanager
def patch_twilio_rest_client_si_meta():
    if not sandbox_meta_activo():
        yield
        return
    from core.lineas.cliente_canal import capa_cliente

    with capa_cliente('meta', lambda _base: MetaOutboundClient):
        yield


@contextmanager
def canal_sandbox_si_meta():
    if sandbox_via_meta():
        with canal_sandbox_meta():
            yield
    else:
        yield


def inbound_es_meta(payload: Any) -> bool:
    if payload is None or isinstance(payload, str):
        return False
    try:
        return (payload.get('_eki_proveedor') or '') == PROVEEDOR_META
    except Exception:
        return False


def es_inbound_twilio_http(payload: Any) -> bool:
    """True si el payload viene del webhook HTTP de Twilio (no tests ni adapter Meta)."""
    if payload is None or isinstance(payload, str):
        return False
    try:
        proveedor = (payload.get('_eki_proveedor') or '').strip().lower()
    except Exception:
        return False
    if proveedor == PROVEEDOR_META:
        return False
    if proveedor == PROVEEDOR_TWILIO:
        return True
    try:
        if payload.get('AccountSid'):
            return True
        sid = str(payload.get('MessageSid') or '')
    except Exception:
        return False
    return sid.startswith(('SM', 'MM', 'IM', 'WA'))


_pnid_salida: ContextVar[str] = ContextVar('eki_pnid_salida', default='')


def sandbox_e164() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_SANDBOX_NUMBER', '14155238886') or '14155238886'
    )


def phone_ids_meta() -> tuple[str, ...]:
    """Líneas Cloud API que comparten menú. La lista vive en core.lineas."""
    from core.lineas.meta import phone_ids

    return phone_ids()


def e164_lineas_meta() -> tuple[str, ...]:
    from core.lineas.meta import numeros_e164

    return numeros_e164()


@contextmanager
def salida_por_phone_id(pnid: str | None):
    """Mientras dura el turno, Graph envía por este phone number id."""
    token = _pnid_salida.set(str(pnid or '').strip())
    try:
        yield
    finally:
        _pnid_salida.reset(token)


def phone_id_de_salida() -> str:
    explicito = (_pnid_salida.get() or '').strip()
    if explicito:
        return explicito
    return sandbox_phone_id()


def to_es_sandbox(to_or_payload: Any) -> bool:
    """Match por E164 del número sandbox (independiente del proveedor)."""
    if isinstance(to_or_payload, str):
        to_raw = to_or_payload
    elif to_or_payload is None:
        to_raw = ''
    else:
        try:
            to_raw = to_or_payload.get('To', '') or ''
        except Exception:
            to_raw = ''
    to_limpio = normalizar_telefono_whatsapp(to_raw)
    if not to_limpio:
        return False
    return to_limpio in e164_lineas_meta()


def phone_id_es_sandbox(payload: Any) -> bool:
    if payload is None or isinstance(payload, str):
        return False
    try:
        got = str(payload.get('_eki_phone_number_id') or '').strip()
    except Exception:
        return False
    return bool(got and got in phone_ids_meta())


def activar_sandbox_meta_si_inbound(post_data):
    if inbound_es_meta(post_data) and sandbox_via_meta():
        return canal_sandbox_meta()
    return nullcontext()


def con_canal_sandbox_meta(fn):
    @wraps(fn)
    def wrapped(post_data, *args, **kwargs):
        with activar_sandbox_meta_si_inbound(post_data):
            return fn(post_data, *args, **kwargs)

    return wrapped


from core.lineas.envio import (
    _tipo_media_desde_url,
    _telefono_graph,
    _graph_headers,
    _graph_messages_url,
    _post_graph,
    _clave_reaccion,
    _enviar_reaccion,
    _pendientes_reaccion,
    hay_reaccion_espera,
    poner_reaccion_espera,
    descartar_reaccion_espera,
    quitar_reaccion_espera,
    _con_aviso_del_dia,
    enviar_sandbox,
    enviar_meta,
    enviar_meta_plantilla,
    enviar_meta_plantilla_imagen,
    enviar_meta_botones,
    enviar_meta_lista,
    enviar_meta_url,
    _par_ver,
    _cards_carrusel,
    _payload_carrusel,
    enviar_meta_carrusel,
    enviar_meta_flow,
    enviar_sandbox_habeas,
    _sid_es_habeas,
    enviar_sandbox_template_fallback,
    _emit_enviado,
    _descargar_bytes_meta,
    transcribir_audio_meta,
    media_meta_a_data_url,
)


def inbound_desde_meta_message(message: dict, value: dict) -> dict:
    """Meta Cloud API message → dict canónico estilo From/To/Body (sin HTTP Twilio)."""
    meta = value.get('metadata') or {}
    display = str(meta.get('display_phone_number') or '').strip()
    phone_id = str(meta.get('phone_number_id') or '').strip()
    from_n = str(message.get('from') or '').strip()
    msg_id = str(message.get('id') or '').strip()
    mtype = str(message.get('type') or 'text').strip().lower()
    body = ''
    num_media = '0'
    media_url = ''
    media_type = ''
    lat = ''
    lng = ''

    from core.meta_inbound import clasificar_mensaje

    info = clasificar_mensaje(message)
    if info['skip']:
        body = ''
    elif mtype == 'text':
        body = info['texto']
    elif mtype == 'interactive':
        inter = message.get('interactive') or {}
        nfm = inter.get('nfm_reply') or {}
        if nfm:
            from core.puentes import MARCA_FLOW

            body = MARCA_FLOW + str(nfm.get('response_json') or '{}')
        else:
            body = info['texto']
    elif mtype == 'button':
        body = info['texto']
    elif mtype in ('audio', 'image', 'video', 'document', 'voice'):
        kind = 'audio' if mtype == 'voice' else mtype
        blob = message.get(kind) or message.get('audio') or {}
        media_url = str(blob.get('id') or '').strip()
        media_type = str(blob.get('mime_type') or '').strip()
        body = str(blob.get('caption') or '').strip()
        if media_url:
            num_media = '1'
        if mtype in ('audio', 'voice') and not media_type:
            media_type = 'audio/ogg'
        if mtype == 'image' and not media_type:
            media_type = 'image/jpeg'
    elif mtype == 'location':
        loc = message.get('location') or {}
        lat = str(loc.get('latitude') or '')
        lng = str(loc.get('longitude') or '')
        body = str(loc.get('name') or loc.get('address') or '').strip()

    to_digits = normalizar_telefono_whatsapp(display) or sandbox_phone_id()
    from_digits = normalizar_telefono_whatsapp(from_n)
    inbound = {
        'From': f'whatsapp:+{from_digits}' if from_digits else '',
        'To': f'whatsapp:+{to_digits}' if to_digits else '',
        'Body': body,
        'MessageSid': msg_id,
        'NumMedia': num_media,
        'MediaUrl0': media_url,
        'MediaContentType0': media_type,
        '_eki_proveedor': PROVEEDOR_META,
        '_eki_phone_number_id': phone_id,
        '_eki_tipo': info['tipo'],
        '_eki_skip': info['skip'],
    }
    if lat and lng:
        inbound['Latitude'] = lat
        inbound['Longitude'] = lng
    return inbound


def iter_mensajes_inbound_meta(payload: dict) -> Iterator[dict]:
    for entry in payload.get('entry') or []:
        for change in (entry.get('changes') or []):
            value = change.get('value') or {}
            for message in value.get('messages') or []:
                if not isinstance(message, dict):
                    continue
                yield inbound_desde_meta_message(message, value)
