"""Clasifica el inbound de Cloud API y deja rastro si el menú no alcanza a responder.

No decide el menú. Solo registra el motivo y, si el proceso revienta, manda el fallback.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)

TEXTO_PROBLEMA = (
    'Tuvimos un problema con su mensaje. Escriba *menu* para empezar de nuevo.'
)
TEXTO_TIPO_NO_SOPORTADO = 'Por ahora solo leo texto y notas de voz.'

_TIPOS_MEDIA = {'audio', 'image', 'video', 'document', 'voice', 'location'}
_TIPOS_IGNORAR = {'reaction'}
_TIPOS_FALLBACK = {'sticker', 'unsupported', 'system', 'contacts', 'order'}

_traza: ContextVar = ContextVar('meta_inbound_traza', default=None)


def clasificar_mensaje(message: dict) -> dict:
    """type de Cloud API → texto usable, o skip si no hay que entrar al menú."""
    if not isinstance(message, dict):
        return {'tipo': 'desconocido', 'texto': '', 'skip': 'tipo_no_soportado'}
    tipo = str(message.get('type') or 'text').strip().lower() or 'text'
    if tipo == 'text':
        texto = str((message.get('text') or {}).get('body') or '').strip()
        return {'tipo': tipo, 'texto': texto, 'skip': ''}
    if tipo == 'interactive':
        inter = message.get('interactive') or {}
        reply = inter.get('button_reply') or inter.get('list_reply') or {}
        texto = str(reply.get('id') or reply.get('title') or '').strip()
        return {'tipo': tipo, 'texto': texto, 'skip': ''}
    if tipo == 'button':
        btn = message.get('button') or {}
        texto = str(btn.get('payload') or btn.get('text') or '').strip()
        return {'tipo': tipo, 'texto': texto, 'skip': ''}
    if tipo in _TIPOS_IGNORAR:
        return {'tipo': tipo, 'texto': '', 'skip': 'ignorar'}
    if tipo in _TIPOS_FALLBACK:
        return {'tipo': tipo, 'texto': '', 'skip': 'tipo_no_soportado'}
    if tipo in _TIPOS_MEDIA:
        return {'tipo': tipo, 'texto': '', 'skip': ''}
    return {'tipo': tipo, 'texto': '', 'skip': 'tipo_no_soportado'}


def marcar_resultado(resultado: str, *, ruta: str = '', error: str = '') -> None:
    traza = _traza.get()
    if traza is None:
        return
    if resultado:
        traza['resultado'] = resultado
    if ruta:
        traza['ruta'] = ruta
    if error:
        traza['error'] = error[:200]


def _telefono_de(data) -> str:
    from core.utils_telefono import normalizar_e164_co

    if not isinstance(data, dict):
        return ''
    bruto = str(data.get('From') or data.get('from') or '')
    return normalizar_e164_co(bruto)


def _abrir(data, mensaje: dict | None = None):
    from django.utils import timezone

    from core.models import Estudiante
    from core.models_meta_webhook import MetaWebhookEvento
    from core.planes_linea import explicar_plan

    if isinstance(data, dict):
        wamid = str(data.get('MessageSid') or data.get('id') or '').strip()
        tipo = str(data.get('_eki_tipo') or 'text')
        telefono = _telefono_de(data)
    else:
        wamid = ''
        tipo = 'text'
        telefono = ''
    if isinstance(mensaje, dict):
        wamid = str(mensaje.get('id') or wamid).strip()
        tipo = str(mensaje.get('type') or tipo).strip().lower() or tipo
        if not telefono:
            telefono = normalizar_desde_mensaje(mensaje)
    if not wamid:
        wamid = f'noid-{uuid.uuid4().hex}'
    est = (
        Estudiante.objects.filter(telefono=telefono).order_by('-id').first()
        if telefono
        else None
    )
    plan = explicar_plan(telefono) if telefono else {}
    payload = {'type': tipo, 'id': wamid[:255]}
    evento, _ = MetaWebhookEvento.objects.get_or_create(
        wamid=wamid[:255],
        defaults={
            'telefono': (telefono or '')[:20],
            'tipo': tipo[:32],
            'payload_raw': payload,
            'firma_ok': True,
            'resultado': 'recibido',
            'estado_chat_antes': (getattr(est, 'estado_chat', '') or '')[:50],
            'plan_efectivo': (plan.get('clave') or plan.get('causa') or '')[:40],
        },
    )
    return evento, timezone


def normalizar_desde_mensaje(mensaje: dict) -> str:
    from core.utils_telefono import normalizar_e164_co

    return normalizar_e164_co(str((mensaje or {}).get('from') or ''))


def _cerrar(evento, resultado: str, error: str, ruta: str, inicio: float) -> None:
    from django.utils import timezone

    if evento is None:
        return
    try:
        evento.resultado = (resultado or 'error')[:32]
        evento.error = (error or '')[:200]
        evento.procesado_en = timezone.now()
        evento.save(update_fields=['resultado', 'error', 'procesado_en'])
    except Exception:
        logger.exception('meta_webhook_evento_cerrar_fail')
    telefono = evento.telefono or ''
    logger.info(
        'meta_inbound wamid=%s phone_last4=%s estado_chat=%s plan=%s ruta=%s resultado=%s latencia_ms=%s',
        evento.wamid,
        telefono[-4:],
        evento.estado_chat_antes,
        evento.plan_efectivo,
        ruta or '-',
        evento.resultado,
        int((time.perf_counter() - inicio) * 1000),
    )


def _enviar_texto(data, texto: str) -> None:
    from core.sandbox_menu import enviar_texto_sandbox, sandbox_number

    telefono = _telefono_de(data)
    if not telefono:
        return
    destino = ''
    if isinstance(data, dict):
        destino = str(data.get('To') or '')
    enviar_texto_sandbox(telefono, destino or sandbox_number(), texto, agente='meta_inbound')


def _resultado_si_vacio(data) -> str:
    telefono = _telefono_de(data)
    if not telefono:
        return 'respondido'
    try:
        from core.planes_linea import explicar_plan

        plan = explicar_plan(telefono)
    except Exception:
        logger.exception('meta_inbound_plan_fail')
        return 'respondido'
    if not plan.get('activo'):
        return 'sin_plan'
    return 'respondido'


@contextmanager
def traza_inbound(data):
    """Envuelve el menú. Si revienta, responde el fallback y guarda resultado=error."""
    inicio = time.perf_counter()
    evento = None
    estado = {'resultado': '', 'ruta': '', 'error': ''}
    token = _traza.set(estado)
    try:
        evento, _tz = _abrir(data)
    except Exception:
        logger.exception('meta_webhook_evento_abrir_fail')
    try:
        yield estado
    except Exception as exc:
        logger.exception('meta_inbound_fail')
        estado['resultado'] = 'error'
        estado['error'] = type(exc).__name__
        try:
            _enviar_texto(data, TEXTO_PROBLEMA)
        except Exception:
            logger.exception('meta_inbound_fallback_fail')
    finally:
        _traza.reset(token)
        if not estado['resultado']:
            skip = ''
            if isinstance(data, dict):
                skip = str(data.get('_eki_skip') or '')
            if skip == 'ignorar':
                estado['resultado'] = 'ignorado'
            elif skip == 'tipo_no_soportado':
                estado['resultado'] = 'tipo_no_soportado'
            else:
                estado['resultado'] = _resultado_si_vacio(data)
        _cerrar(evento, estado['resultado'], estado['error'], estado['ruta'], inicio)


def registrar_mensaje_legacy(mensaje: dict, resultado: str, error: str = '') -> None:
    """El camino viejo de _procesar_meta_webhook, cuando el menú sandbox no tomó el mensaje."""
    inicio = time.perf_counter()
    try:
        evento, _tz = _abrir({}, mensaje)
    except Exception:
        logger.exception('meta_webhook_evento_legacy_fail')
        return
    _cerrar(evento, resultado, error, 'legacy', inicio)
