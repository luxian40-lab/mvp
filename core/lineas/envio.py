"""Envio por WhatsApp Cloud API. El curso llama estos nombres y no abre el webhook."""
import logging
import time

import requests
from django.conf import settings

from core.conversacion.marcas import PAUSA, PLANTILLA, es_marcado, partes
from core.nati import normalizar_telefono_whatsapp

logger = logging.getLogger(__name__)


def _salida_phone_id() -> str:
    from core.sandbox_canal import phone_id_de_salida
    return phone_id_de_salida()


def _via_meta() -> bool:
    from core.sandbox_canal import sandbox_via_meta
    return sandbox_via_meta()


def _texto_habeas() -> str:
    from core.sandbox_canal import _TEXTO_HABEAS_SANDBOX
    return _TEXTO_HABEAS_SANDBOX


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
    phone_id = _salida_phone_id()
    if not phone_id:
        return None
    from core.meta_waba import _version

    version = api_version or _version()
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
        canal='meta',
        phone_id=_salida_phone_id(),
        fecha=timezone.now(),
        agente_usado=(agente or 'sandbox_meta')[:50],
    )
    ultimo_error = {'code': '', 'detalle': '', 'status': 0, 'err': {}}
    for intento in range(2):
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
                from core.salida_usuario import marcar_mensaje_salio
                marcar_mensaje_salio()
                return {'success': True, 'mensaje_id': mensaje_id, 'response': data}
            err = data.get('error', data) if isinstance(data, dict) else data
            if not isinstance(err, dict):
                err = {'message': str(err)}
            code = str(err.get('code') or '')[:16]
            tipo = str(err.get('type') or '')[:80]
            message = str(err.get('message') or '')[:500]
            detalle_extra = ''
            error_data = err.get('error_data') if isinstance(err.get('error_data'), dict) else {}
            if error_data:
                detalle_extra = str(error_data.get('details') or '')[:300]
            ultimo_error = {
                'code': code,
                'detalle': ' '.join(
                    parte for parte in (tipo, code, message, detalle_extra) if parte
                )[:2000],
                'status': resp.status_code,
                'err': err,
            }
            transitorio = code == '130429' or resp.status_code >= 500
            if transitorio and intento == 0:
                logger.info('meta_graph_reintento code=%s status=%s', code, resp.status_code)
                continue
            break
        except Exception:
            ultimo_error = {
                'code': '',
                'detalle': 'graph_exception',
                'status': 0,
                'err': {'message': 'graph_exception'},
            }
            if intento == 0:
                logger.info('meta_graph_reintento excepcion')
                continue
            break
    log.estado = 'ERROR'
    log.error_codigo = ultimo_error['code'] or None
    log.error_detalle = ultimo_error['detalle'] or 'graph_exception'
    log.save(update_fields=['estado', 'error_codigo', 'error_detalle'])
    logger.warning(
        'sandbox_meta_graph_error status=%s code=%s',
        ultimo_error['status'],
        ultimo_error['code'],
    )
    from core.meta_token import es_token_invalido, marcar_token_invalido

    if es_token_invalido(ultimo_error['err']):
        marcar_token_invalido()
    return {'success': False, 'mensaje_id': None, 'response': ultimo_error['err']}


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
            from core.salida_usuario import marcar_mensaje_salio
            marcar_mensaje_salio()
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
    if not emoji or not message_id.startswith('wamid.') or not _via_meta():
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
    if not _via_meta():
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
    if es_marcado(texto):
        return _enviar_partes_marcadas(
            to, texto, media_url=clean_url, canal_evento=canal_evento, agente_evento=agente_evento,
        )
    last: dict = {'success': False, 'mensaje_id': None, 'response': 'Empty body and no media'}
    from core.response_templates import TEXTO_MODULO_CARGANDO

    if texto == TEXTO_MODULO_CARGANDO and not clean_url and hay_reaccion_espera(to):
        # El ⏳ sobre su Continuemos ya dice que el módulo viene; no gastar un mensaje.
        return {'success': True, 'mensaje_id': None, 'response': 'reaccion_espera'}
    if '[SEND_BUTTON:continuemos]' in texto and not clean_url:
        from core.avance_whatsapp import (
            BOTON_CONTINUEMOS_ID,
            BOTON_CONTINUEMOS_TITULO,
            separar_boton_continuemos,
        )

        cuerpo, _ = separar_boton_continuemos(texto)
        return enviar_meta_botones(
            to,
            cuerpo,
            [(BOTON_CONTINUEMOS_ID, BOTON_CONTINUEMOS_TITULO)],
            canal_evento=canal_evento,
            agente_evento=agente_evento or 'curso_continuar',
        )
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


def _enviar_partes_marcadas(
    to: str,
    texto: str,
    *,
    media_url: str | None,
    canal_evento: str,
    agente_evento: str,
) -> dict:
    """Texto armado por el curso: un mensaje por parte, en orden.

    Las plantillas de Twilio no existen en Meta y se omiten.
    """
    last: dict = {'success': False, 'mensaje_id': None, 'response': 'Empty body and no media'}
    if media_url:
        last = enviar_meta(to, '', media_url=media_url, canal_evento=canal_evento, agente_evento=agente_evento)
    for parte in partes(texto):
        if parte.tipo == PAUSA:
            time.sleep(parte.segundos)
            continue
        if parte.tipo == PLANTILLA:
            logger.warning('meta_partes_plantilla_twilio_omitida to=***%s', to[-4:])
            continue
        last = enviar_meta(
            to, parte.texto, media_url=parte.media, canal_evento=canal_evento, agente_evento=agente_evento,
        )
        if not last.get('success'):
            return last
        time.sleep(0.5)
    return last


def enviar_meta_plantilla(
    telefono: str,
    nombre: str,
    variables: dict,
    *,
    idioma: str = 'es',
    agente_evento: str = 'reenganche_drip',
) -> dict:
    """Plantilla aprobada de Cloud API. variables usa claves '1', '2', …"""
    to = _telefono_graph(telefono)
    if not to:
        return {'success': False, 'mensaje_id': None, 'response': 'Invalid destination phone'}
    nombre = (nombre or '').strip()
    if not nombre:
        return {'success': False, 'mensaje_id': None, 'response': 'sin_plantilla'}
    parameters = []
    for clave in sorted(variables or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        parameters.append({'type': 'text', 'text': str(variables[clave])[:1024]})
    plantilla = {
        'name': nombre,
        'language': {'code': (idioma or 'es').strip() or 'es'},
    }
    if parameters:
        plantilla['components'] = [{'type': 'body', 'parameters': parameters}]
    return _post_graph({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'template',
        'template': plantilla,
    }, agente=agente_evento)


def enviar_meta_plantilla_imagen(
    telefono: str,
    nombre: str,
    media_url: str,
    variables: dict,
    *,
    idioma: str = 'es',
    agente_evento: str = 'diploma_meta',
) -> dict:
    """Plantilla con imagen en el encabezado. Sirve fuera de la ventana de 24 h."""
    to = _telefono_graph(telefono)
    if not to:
        return {'success': False, 'mensaje_id': None, 'response': 'Invalid destination phone'}
    nombre = (nombre or '').strip()
    link = (media_url or '').strip()
    if not nombre or not link:
        return {'success': False, 'mensaje_id': None, 'response': 'sin_plantilla'}
    parameters = []
    for clave in sorted(variables or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        parameters.append({'type': 'text', 'text': str(variables[clave])[:1024]})
    components = [{
        'type': 'header',
        'parameters': [{'type': 'image', 'image': {'link': link}}],
    }]
    if parameters:
        components.append({'type': 'body', 'parameters': parameters})
    return _post_graph({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'template',
        'template': {
            'name': nombre,
            'language': {'code': (idioma or 'es').strip() or 'es'},
            'components': components,
        },
    }, agente=agente_evento)


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


def enviar_meta_url(
    telefono: str,
    texto: str,
    url: str,
    *,
    boton: str = 'Abrir página',
    imagen: str = '',
    canal_evento: str = 'whatsapp_sandbox',
    agente_evento: str = 'sandbox_formacion',
) -> dict:
    """Botón que abre una página. Si Meta no lo acepta, manda el enlace en texto."""
    to = _telefono_graph(telefono)
    cuerpo = (texto or '').strip()[:1024]
    destino = (url or '').strip()
    foto = (imagen or '').strip()
    if to and cuerpo and destino.startswith('https://'):
        interactive = {
            'type': 'cta_url',
            'body': {'text': cuerpo},
            'action': {
                'name': 'cta_url',
                'parameters': {
                    'display_text': (boton or 'Abrir página')[:20],
                    'url': destino[:2000],
                },
            },
        }
        if foto.startswith('https://'):
            interactive['header'] = {'type': 'image', 'image': {'link': foto[:2000]}}
        result = _post_graph({
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'interactive',
            'interactive': interactive,
        }, agente=agente_evento)
        if result.get('success'):
            _emit_enviado(to, cuerpo, result.get('mensaje_id'), canal_evento, agente_evento)
            return result
    aviso = cuerpo or destino
    if destino and destino not in aviso:
        aviso = f'{aviso}\n\n{destino}'.strip()
    return enviar_meta(telefono, aviso, canal_evento=canal_evento, agente_evento=agente_evento)


def _par_ver(tarjeta: dict) -> tuple[str, str]:
    for bid, title in list(tarjeta.get('botones') or [])[:2]:
        titulo = str(title or '').strip()[:20]
        if titulo and titulo != 'Más información':
            return str(bid or '').strip()[:256], titulo
    return '', ''


def _cards_carrusel(tarjetas: list[dict], *, modo: str) -> list[dict]:
    """modo enlace: un botón nativo que abre la página. modo respuesta: dos quick reply."""
    cards = []
    for i, tarjeta in enumerate(list(tarjetas)[:10]):
        imagen = (tarjeta.get('imagen') or '').strip()
        body = (tarjeta.get('body') or '').strip()[:160]
        url = str(tarjeta.get('url') or '').strip()
        if not imagen or not body:
            continue
        if modo == 'enlace' and url.startswith('https://'):
            cards.append({
                'card_index': len(cards),
                'type': 'cta_url',
                'header': {'type': 'image', 'image': {'link': imagen}},
                'body': {'text': body},
                'action': {
                    'name': 'cta_url',
                    'parameters': {
                        'display_text': 'Más información',
                        'url': url[:2000],
                    },
                },
            })
            continue
        botones = []
        ver_id, ver_titulo = _par_ver(tarjeta)
        if ver_id and ver_titulo:
            botones.append({
                'type': 'quick_reply',
                'quick_reply': {'id': ver_id, 'title': ver_titulo},
            })
        for bid, title in list(tarjeta.get('botones') or [])[:2]:
            titulo = str(title or '').strip()[:20]
            ident = str(bid or '').strip()[:256]
            if titulo == 'Más información' and ident:
                botones.append({
                    'type': 'quick_reply',
                    'quick_reply': {'id': ident, 'title': titulo},
                })
        if len(botones) != 2:
            continue
        cards.append({
            'card_index': i,
            'type': 'cta_url',
            'header': {'type': 'image', 'image': {'link': imagen}},
            'body': {'text': body},
            'action': {'buttons': botones},
        })
    return cards


def _payload_carrusel(to: str, cuerpo: str, cards: list[dict]) -> dict:
    return {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'carousel',
            'body': {'text': cuerpo},
            'action': {'cards': cards},
        },
    }


def enviar_meta_carrusel(
    telefono: str,
    texto: str,
    tarjetas: list[dict],
    *,
    canal_evento: str = 'whatsapp_sandbox',
    agente_evento: str = 'sandbox_formacion',
) -> dict:
    """Carrusel con foto. Ver curso inscribe. El enlace de la tarjeta abre la página."""
    to = _telefono_graph(telefono)
    cuerpo = (texto or '').strip()[:1024]
    lista = list(tarjetas)[:10]
    cards = _cards_carrusel(lista, modo='respuesta')
    if len(cards) < 2 or not to or not cuerpo:
        return {'success': False, 'mensaje_id': None, 'response': 'Carrusel incompleto'}
    logger.info('sandbox_carrusel_modo respuesta cards=%s', len(cards))
    result = _post_graph(
        _payload_carrusel(to, cuerpo, cards),
        agente=agente_evento,
    )
    if result.get('success'):
        _emit_enviado(to, cuerpo, result.get('mensaje_id'), canal_evento, agente_evento)
    return result


def enviar_meta_flow(
    telefono: str,
    texto: str,
    flow_id: str,
    *,
    pantalla: str,
    flow_token: str,
    cta: str = 'Llenar ficha',
    agente_evento: str = 'sandbox_formulario',
) -> dict:
    """Formulario nativo de WhatsApp (Flow). El chat sigue como respaldo si esto falla."""
    to = _telefono_graph(telefono)
    cuerpo = (texto or '').strip()[:1024]
    if not to or not cuerpo or not flow_id or not pantalla:
        return {'success': False, 'mensaje_id': None, 'response': 'Flow incompleto'}
    result = _post_graph(
        {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'interactive',
            'interactive': {
                'type': 'flow',
                'body': {'text': cuerpo},
                'action': {
                    'name': 'flow',
                    'parameters': {
                        'flow_message_version': '3',
                        'flow_token': str(flow_token or 'gei')[:128],
                        'flow_id': str(flow_id),
                        'flow_cta': (cta or 'Llenar ficha')[:20],
                        'flow_action': 'navigate',
                        'flow_action_payload': {'screen': pantalla, 'data': {}},
                    },
                },
            },
        },
        agente=agente_evento,
    )
    if result.get('success'):
        _emit_enviado(to, cuerpo, result.get('mensaje_id'), 'whatsapp_sandbox', agente_evento)
    return result


def enviar_sandbox_habeas(telefono: str) -> dict:
    to = _telefono_graph(telefono)
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': _texto_habeas()},
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
    return enviar_meta(telefono, _texto_habeas())


def _sid_es_habeas(sid: str, sid_historico: str = '') -> bool:
    """True si el HX es la plantilla de autorización, aunque no sea el SID histórico."""
    if not sid:
        return False
    if sid_historico and sid == sid_historico:
        return True
    try:
        from core.models import Cliente, ConfiguracionGlobal

        global_sid = (ConfiguracionGlobal.get_solo().content_sid_habeas_data_global or '').strip()
        if global_sid and sid == global_sid:
            return True
        return Cliente.objects.filter(content_sid_habeas_data_twilio=sid).exists()
    except Exception:
        return False


def enviar_sandbox_template_fallback(telefono: str, content_sid: str, variables: dict | None = None) -> dict:
    """Plantillas Twilio no existen en Graph: habeas interactivo o texto plano."""
    sid = (content_sid or '').strip()
    habeas_sid = ''
    try:
        from core.whatsapp_service import TWILIO_CONTENT_SIDS

        habeas_sid = (TWILIO_CONTENT_SIDS.get('habeas_data') or '').strip()
    except Exception:
        habeas_sid = ''
    if sid and _sid_es_habeas(sid, habeas_sid):
        return enviar_sandbox_habeas(telefono)
    from core.avance_whatsapp import (
        BOTON_CONTINUEMOS_ID,
        BOTON_CONTINUEMOS_TITULO,
        CUERPO_BOTON_CONTINUEMOS,
        SID_BOTON_LISTO_DEFAULT,
    )

    if sid and sid == SID_BOTON_LISTO_DEFAULT:
        return enviar_meta_botones(
            telefono,
            CUERPO_BOTON_CONTINUEMOS,
            [(BOTON_CONTINUEMOS_ID, BOTON_CONTINUEMOS_TITULO)],
        )
    try:
        from core.whatsapp_service import TWILIO_CONTENT_SIDS as _SIDS
        sid_datos = (_SIDS.get('confirmar_datos_v2') or '').strip()
    except Exception:
        sid_datos = ''
    if sid and sid_datos and sid == sid_datos:
        datos = variables or {}
        cuerpo = (
            '¿Sus datos están bien?\n\n'
            f"Nombre: {datos.get('1') or 'No registrado'}\n"
            f"Documento: {datos.get('2') or 'No registrada'}\n"
            f"Organización: {datos.get('3') or 'eki'}\n"
            f"Edad: {datos.get('4') or 'No registrada'}\n"
            f"Municipio: {datos.get('5') or 'No registrado'}"
        )
        return enviar_meta_botones(
            telefono,
            cuerpo,
            [('si', 'Están bien'), ('no', 'Hay un error')],
        )
    partes = []
    if sid:
        partes.append('Mensaje del curso')
    if variables:
        partes.extend(str(v) for v in variables.values() if v)
    texto = '\n'.join(partes) if partes else CUERPO_BOTON_CONTINUEMOS
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
    from core.meta_waba import _version

    api_version = _version()
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


def enviar_respuesta_linea(
    telefono: str,
    texto: str,
    *,
    media_url: str | None = None,
    agente: str = 'curso',
) -> dict:
    """Respuesta del curso por la línea de Meta que recibió el mensaje.

    El aula no pasa por aquí. Un arreglo de botón o de texto llama esta
    función y no abre el cuerpo del webhook ni el cliente de Twilio.
    """
    return enviar_meta(
        telefono,
        texto,
        media_url=media_url,
        agente_evento=agente or 'curso',
    )


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


