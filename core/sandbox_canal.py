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
    "Antes de continuar, autorice el tratamiento de sus datos "
    "para la formación y la asesoría en esta línea.\n\n"
    "Pulse *Acepto* o *No acepto*."
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
    import twilio.rest as twilio_rest

    if twilio_rest.Client is MetaOutboundClient:
        yield
        return
    original = twilio_rest.Client
    twilio_rest.Client = MetaOutboundClient
    try:
        yield
    finally:
        twilio_rest.Client = original


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


def sandbox_e164() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_SANDBOX_NUMBER', '14155238886') or '14155238886'
    )


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
    sb = sandbox_e164()
    return bool(to_limpio and sb and to_limpio == sb)


def phone_id_es_sandbox(payload: Any) -> bool:
    expected = sandbox_phone_id()
    if not expected or payload is None or isinstance(payload, str):
        return False
    try:
        got = str(payload.get('_eki_phone_number_id') or '').strip()
    except Exception:
        return False
    return bool(got and got == expected)


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


def _tipo_media_desde_url(url: str) -> str:
    u = (url or '').lower().split('?')[0]
    if any(u.endswith(ext) for ext in ('.mp4', '.mov', '.3gp', '.webm')):
        return 'video'
    if any(u.endswith(ext) for ext in ('.mp3', '.ogg', '.opus', '.amr', '.m4a', '.wav', '.aac')):
        return 'audio'
    if any(u.endswith(ext) for ext in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip')):
        return 'document'
    return 'image'


def _telefono_graph(telefono: str) -> str:
    return normalizar_telefono_whatsapp(telefono)


def _graph_headers() -> dict[str, str] | None:
    token = (getattr(settings, 'WHATSAPP_TOKEN', None) or '').strip()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def _graph_messages_url(api_version: str | None = None) -> str | None:
    phone_id = sandbox_phone_id()
    if not phone_id:
        return None
    version = api_version or getattr(settings, 'WHATSAPP_API_VERSION', 'v19.0') or 'v19.0'
    return f'https://graph.facebook.com/{version}/{phone_id}/messages'


def _post_graph(payload: dict, api_version: str | None = None, agente: str = '') -> dict:
    from django.utils import timezone

    from core.models import WhatsappLog

    headers = _graph_headers()
    url = _graph_messages_url(api_version)
    to = payload.get('to') or ''
    texto_log = ''
    if payload.get('type') == 'text':
        texto_log = ((payload.get('text') or {}).get('body') or '')[:1500]
    elif payload.get('type') == 'interactive':
        texto_log = (((payload.get('interactive') or {}).get('body') or {}).get('text') or '')[:1500]
    else:
        bloque = payload.get(payload.get('type') or '') or {}
        texto_log = (bloque.get('caption') or bloque.get('link') or payload.get('type') or '')[:1500]

    if not headers or not url:
        logger.error('sandbox_meta_sin_credenciales')
        return {'success': False, 'mensaje_id': None, 'response': 'Credentials not set'}

    log = WhatsappLog.objects.create(
        telefono=to,
        mensaje=texto_log or '[META]',
        estado='PENDING',
        tipo='SENT',
        fecha=timezone.now(),
        agente_usado=(agente or 'sandbox_meta')[:50],
    )
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        try:
            data = resp.json()
        except Exception:
            data = {'raw': resp.text}
        if resp.status_code in (200, 201) and 'messages' in data:
            mensaje_id = (data.get('messages') or [{}])[0].get('id')
            log.mensaje_id = mensaje_id
            log.estado = 'SENT'
            log.save(update_fields=['mensaje_id', 'estado'])
            quitar_reaccion_espera(to)
            return {'success': True, 'mensaje_id': mensaje_id, 'response': data}
        err = data.get('error', data)
        log.estado = 'ERROR'
        log.save(update_fields=['estado'])
        logger.warning('sandbox_meta_graph_error status=%s err=%s', resp.status_code, err)
        return {'success': False, 'mensaje_id': None, 'response': err}
    except Exception as exc:
        log.estado = 'ERROR'
        log.save(update_fields=['estado'])
        logger.exception('sandbox_meta_graph_fail')
        return {'success': False, 'mensaje_id': None, 'response': str(exc)}


def _clave_reaccion(to: str) -> str:
    return f'sandbox_reaccion:{to}'


def _enviar_reaccion(to: str, message_id: str, emoji: str) -> bool:
    """Reacción sobre el mensaje de la persona. Sin WhatsappLog: no es un mensaje ni cuenta en memoria."""
    headers = _graph_headers()
    url = _graph_messages_url()
    if not headers or not url:
        return False
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'reaction',
        'reaction': {'message_id': message_id, 'emoji': emoji},
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code in (200, 201):
            return True
        logger.warning('sandbox_reaccion_error status=%s body=%s', resp.status_code, resp.text[:300])
    except Exception:
        logger.exception('sandbox_reaccion_fail')
    return False


def _pendientes_reaccion(to: str) -> list[str]:
    from django.core.cache import cache

    valor = cache.get(_clave_reaccion(to)) or []
    return [valor] if isinstance(valor, str) else list(valor)


def hay_reaccion_espera(telefono: str) -> bool:
    to = _telefono_graph(telefono)
    try:
        return bool(to and _pendientes_reaccion(to))
    except Exception:
        return False


def poner_reaccion_espera(telefono: str, message_id: str) -> None:
    """⏳ sobre el mensaje de la persona; el siguiente envío exitoso lo cambia a SANDBOX_REACCION_FIN."""
    emoji = (getattr(settings, 'SANDBOX_REACCION_ESPERA', '⏳') or '').strip()
    message_id = (message_id or '').strip()
    if not emoji or not message_id.startswith('wamid.') or not sandbox_via_meta():
        return
    to = _telefono_graph(telefono)
    if not to:
        return
    from django.core.cache import cache

    if _enviar_reaccion(to, message_id, emoji):
        try:
            pendientes = [m for m in _pendientes_reaccion(to) if m != message_id][-4:]
            cache.set(_clave_reaccion(to), pendientes + [message_id], timeout=600)
        except Exception:
            logger.exception('sandbox_reaccion_cache_fail')


def descartar_reaccion_espera(telefono: str) -> None:
    """Quita el ⏳ de un *listo* repetido, sin poner ✅: ese turno no envía nada."""
    to = _telefono_graph(telefono)
    if not to:
        return
    try:
        from django.core.cache import cache

        message_id = (_pendientes_reaccion(to) or [None])[-1]
        if not message_id:
            return
        pendientes = [m for m in _pendientes_reaccion(to) if m != message_id]
        if pendientes:
            cache.set(_clave_reaccion(to), pendientes, timeout=600)
        else:
            cache.delete(_clave_reaccion(to))
    except Exception:
        logger.exception('sandbox_reaccion_cache_fail')
        return
    _enviar_reaccion(to, message_id, '')


def quitar_reaccion_espera(to: str) -> None:
    if not to:
        return
    try:
        from django.core.cache import cache

        pendientes = _pendientes_reaccion(to)
        if not pendientes:
            return
        cache.delete(_clave_reaccion(to))
    except Exception:
        logger.exception('sandbox_reaccion_cache_fail')
        return
    fin = (getattr(settings, 'SANDBOX_REACCION_FIN', '✅') or '').strip()
    for message_id in pendientes:
        _enviar_reaccion(to, message_id, fin)


def _con_aviso_del_dia(to: str, texto: str) -> str:
    """Antepone la racha/insignia pendiente una sola vez; nunca como mensaje aparte."""
    if not texto:
        return texto
    try:
        from core.rachas_linea import tomar_aviso_pendiente

        aviso = tomar_aviso_pendiente(to)
    except Exception:
        logger.exception('sandbox_aviso_racha_fail')
        return texto
    return f"{aviso}\n\n{texto}" if aviso else texto


def enviar_sandbox(
    telefono: str,
    texto: str,
    *,
    media_url: str | None = None,
    from_number: str | None = None,
    canal_evento: str = 'whatsapp_sandbox',
    agente_evento: str = '',
) -> dict:
    """Envío sandbox: Meta Graph si SANDBOX_PROVEEDOR=meta; si no, Twilio legacy."""
    del from_number  # Meta usa SANDBOX_WHATSAPP_PHONE_ID / WHATSAPP_PHONE_ID
    if not sandbox_via_meta():
        from core.utils import enviar_whatsapp_twilio

        return enviar_whatsapp_twilio(
            telefono,
            texto,
            media_url=media_url,
            canal_evento=canal_evento,
            agente_evento=agente_evento,
        )
    return enviar_meta(telefono, texto, media_url=media_url, canal_evento=canal_evento, agente_evento=agente_evento)


def enviar_meta(
    telefono: str,
    texto: str,
    *,
    media_url: str | None = None,
    canal_evento: str = 'whatsapp_sandbox',
    agente_evento: str = '',
) -> dict:
    to = _telefono_graph(telefono)
    if not to:
        return {'success': False, 'mensaje_id': None, 'response': 'Invalid destination phone'}

    from core.response_templates import dividir_contenido_seguro

    texto = str(texto or '').strip()
    clean_url = str(media_url or '').strip() or None
    last: dict = {'success': False, 'mensaje_id': None, 'response': 'Empty body and no media'}
    from core.response_templates import TEXTO_MODULO_CARGANDO

    if texto == TEXTO_MODULO_CARGANDO and not clean_url and hay_reaccion_espera(to):
        # El ⏳ sobre su *listo* ya dice que el módulo viene; no gastar un mensaje.
        return {'success': True, 'mensaje_id': None, 'response': 'reaccion_espera'}
    if texto:
        texto = _con_aviso_del_dia(to, texto)

    if clean_url:
        kind = _tipo_media_desde_url(clean_url)
        caption = texto[:1024] if texto else ''
        payload = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': kind,
            kind: {'link': clean_url},
        }
        if caption:
            payload[kind]['caption'] = caption
        last = _post_graph(payload, agente=agente_evento)
        resto = texto[len(caption):].strip() if caption else ''
        if resto and last.get('success'):
            last = enviar_meta(to, resto, canal_evento=canal_evento, agente_evento=agente_evento)
        _emit_enviado(to, texto or clean_url, last.get('mensaje_id'), canal_evento, agente_evento)
        return last

    if not texto:
        return {'success': False, 'mensaje_id': None, 'response': 'Empty body and no media'}

    chunks = dividir_contenido_seguro(texto, max_chars=3900) or [texto]
    for chunk in chunks:
        last = _post_graph({
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {'body': chunk},
        }, agente=agente_evento)
        if not last.get('success'):
            return last
    _emit_enviado(to, texto, last.get('mensaje_id'), canal_evento, agente_evento)
    return last


def enviar_meta_botones(
    telefono: str,
    texto: str,
    botones: list[tuple[str, str]],
    *,
    canal_evento: str = 'whatsapp_sandbox',
    agente_evento: str = 'sandbox_menu',
) -> dict:
    """Botones de respuesta Meta (máximo 3, título de 20 caracteres)."""
    to = _telefono_graph(telefono)
    if not to:
        return {'success': False, 'mensaje_id': None, 'response': 'Invalid destination phone'}
    completo = _con_aviso_del_dia(to, (texto or '').strip())
    cuerpo = completo[:1024]
    acciones = []
    for bid, title in botones[:3]:
        acciones.append({
            'type': 'reply',
            'reply': {
                'id': str(bid)[:200],
                'title': str(title)[:20],
            },
        })
    if not acciones or not cuerpo:
        return enviar_meta(telefono, completo, canal_evento=canal_evento, agente_evento=agente_evento)
    result = _post_graph({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': cuerpo},
            'action': {'buttons': acciones},
        },
    }, agente=agente_evento)
    if result.get('success'):
        _emit_enviado(to, cuerpo, result.get('mensaje_id'), canal_evento, agente_evento)
        return result
    return enviar_meta(telefono, completo, canal_evento=canal_evento, agente_evento=agente_evento)


def enviar_meta_lista(
    telefono: str,
    texto: str,
    boton: str,
    filas: list[tuple[str, str, str]],
    *,
    texto_respaldo: str = '',
    canal_evento: str = 'whatsapp_sandbox',
    agente_evento: str = 'sandbox_menu',
) -> dict:
    """Lista interactiva Meta (hasta 10 filas: id, título ≤24, descripción ≤72). Si falla, manda texto."""
    to = _telefono_graph(telefono)
    if not to:
        return {'success': False, 'mensaje_id': None, 'response': 'Invalid destination phone'}
    cuerpo = _con_aviso_del_dia(to, (texto or '').strip())
    rows = [
        {'id': str(fid)[:200], 'title': str(titulo)[:24], 'description': str(desc)[:72]}
        for fid, titulo, desc in filas[:10]
    ]
    if rows and cuerpo:
        result = _post_graph({
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'interactive',
            'interactive': {
                'type': 'list',
                'body': {'text': cuerpo[:1024]},
                'action': {'button': str(boton)[:20], 'sections': [{'title': str(boton)[:24], 'rows': rows}]},
            },
        }, agente=agente_evento)
        if result.get('success'):
            _emit_enviado(to, cuerpo, result.get('mensaje_id'), canal_evento, agente_evento)
            return result
    aviso = cuerpo[: len(cuerpo) - len((texto or '').strip())]
    respaldo = f"{aviso}{texto_respaldo}" if texto_respaldo else cuerpo
    return enviar_meta(telefono, respaldo, canal_evento=canal_evento, agente_evento=agente_evento)


def enviar_meta_carrusel(
    telefono: str,
    texto: str,
    tarjetas: list[dict],
    *,
    canal_evento: str = 'whatsapp_sandbox',
    agente_evento: str = 'sandbox_formacion',
) -> dict:
    """Carrusel con foto. Las dos acciones son respuesta: Ver curso e información. Mismo tipo en cada card."""
    to = _telefono_graph(telefono)
    cuerpo = (texto or '').strip()[:1024]
    cards = []
    for i, tarjeta in enumerate(list(tarjetas)[:10]):
        imagen = (tarjeta.get('imagen') or '').strip()
        body = (tarjeta.get('body') or '').strip()[:160]
        botones = []
        for bid, title in list(tarjeta.get('botones') or [])[:2]:
            bid = str(bid or '').strip()
            title = str(title or '').strip()[:20]
            if bid and title:
                botones.append({
                    'type': 'quick_reply',
                    'quick_reply': {'id': bid[:256], 'title': title},
                })
        if not imagen or not body or len(botones) != 2:
            continue
        cards.append({
            'card_index': i,
            'type': 'cta_url',
            'header': {'type': 'image', 'image': {'link': imagen}},
            'body': {'text': body},
            'action': {'buttons': botones},
        })
    if len(cards) < 2 or not to or not cuerpo:
        return {'success': False, 'mensaje_id': None, 'response': 'Carrusel incompleto'}
    result = _post_graph(
        {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'interactive',
            'interactive': {
                'type': 'carousel',
                'body': {'text': cuerpo},
                'action': {'cards': cards},
            },
        },
        api_version='v23.0',
    )
    if result.get('success'):
        _emit_enviado(to, cuerpo, result.get('mensaje_id'), canal_evento, agente_evento)
    return result


def enviar_sandbox_habeas(telefono: str) -> dict:
    to = _telefono_graph(telefono)
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': _TEXTO_HABEAS_SANDBOX},
            'action': {
                'buttons': [
                    {'type': 'reply', 'reply': {'id': 'acepto', 'title': 'Acepto'}},
                    {'type': 'reply', 'reply': {'id': 'no_acepto', 'title': 'No acepto'}},
                ]
            },
        },
    }
    result = _post_graph(payload)
    if result.get('success'):
        return result
    return enviar_meta(telefono, _TEXTO_HABEAS_SANDBOX)


def enviar_sandbox_template_fallback(telefono: str, content_sid: str, variables: dict | None = None) -> dict:
    """Plantillas Twilio no existen en Graph: habeas interactivo o texto plano."""
    sid = (content_sid or '').strip()
    habeas_sid = ''
    try:
        from core.whatsapp_service import TWILIO_CONTENT_SIDS

        habeas_sid = (TWILIO_CONTENT_SIDS.get('habeas_data') or '').strip()
    except Exception:
        habeas_sid = ''
    if sid and habeas_sid and sid == habeas_sid:
        return enviar_sandbox_habeas(telefono)
    partes = []
    if sid:
        partes.append('Mensaje del curso')
    if variables:
        partes.extend(str(v) for v in variables.values() if v)
    texto = '\n'.join(partes) if partes else 'Continúa escribiendo *listo*.'
    return enviar_meta(telefono, texto)


def _emit_enviado(telefono: str, texto: str, mensaje_id, canal: str, agente: str) -> None:
    try:
        from core.ai_capabilities import resolver_ai_capability
        from core.eventos_ia import emit_mensaje_enviado

        if resolver_ai_capability('eventos_ia'):
            emit_mensaje_enviado(
                telefono=telefono,
                texto=texto,
                mensaje_id=mensaje_id,
                canal=canal,
                agente=agente,
            )
    except Exception:
        pass


def _descargar_bytes_meta(media_id: str) -> tuple[bytes, str]:
    token = (getattr(settings, 'WHATSAPP_TOKEN', None) or '').strip()
    if not token or not media_id:
        return b'', ''
    api_version = getattr(settings, 'WHATSAPP_API_VERSION', 'v19.0') or 'v19.0'
    headers = {'Authorization': f'Bearer {token}'}
    info = requests.get(
        f'https://graph.facebook.com/{api_version}/{media_id}',
        headers=headers,
        timeout=25,
    )
    if info.status_code != 200:
        logger.warning('sandbox_meta_media_info status=%s', info.status_code)
        return b'', ''
    data = info.json()
    media_url = data.get('url') or ''
    mime = data.get('mime_type') or ''
    if not media_url:
        return b'', mime
    resp = requests.get(media_url, headers=headers, timeout=30)
    if resp.status_code != 200:
        logger.warning('sandbox_meta_media_dl status=%s', resp.status_code)
        return b'', mime
    return resp.content or b'', mime or (resp.headers.get('Content-Type') or '')


def transcribir_audio_meta(media_id: str, media_type: str = 'audio/ogg') -> str | None:
    del media_type
    from core.audio_processor import AudioProcessor

    proc = AudioProcessor()
    result = proc.procesar_audio_completo(media_id, proveedor='meta') or {}
    return (result.get('texto') or '').strip() or None


def media_meta_a_data_url(media_id: str, media_type: str = '') -> str:
    import base64

    raw, mime = _descargar_bytes_meta(media_id)
    if not raw:
        return ''
    if len(raw) > 4 * 1024 * 1024:
        logger.warning('sandbox_meta_vision imagen grande (%s)', len(raw))
        return ''
    mime_ok = (mime or media_type or 'image/jpeg').split(';')[0].strip() or 'image/jpeg'
    b64 = base64.b64encode(raw).decode('ascii')
    return f'data:{mime_ok};base64,{b64}'


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

    if mtype == 'text':
        body = str((message.get('text') or {}).get('body') or '').strip()
    elif mtype == 'interactive':
        inter = message.get('interactive') or {}
        reply = inter.get('button_reply') or inter.get('list_reply') or {}
        body = str(reply.get('id') or reply.get('title') or '').strip()
    elif mtype == 'button':
        btn = message.get('button') or {}
        body = str(btn.get('payload') or btn.get('text') or '').strip()
    elif mtype in ('audio', 'image', 'video', 'document', 'sticker', 'voice'):
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
