"""
Emisión y consulta de eventos IA (Parte 2A — observabilidad).

Uso:
    from core.eventos_ia import emit_checkpoint_evaluado, get_or_create_trace_id

Cada webhook / turno de conversación debe compartir ``trace_id`` para replay.
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('eki_trace_id', default=None)


def get_or_create_trace_id() -> str:
    tid = _trace_id_var.get()
    if not tid:
        tid = str(uuid.uuid4())
        _trace_id_var.set(tid)
    return tid


def set_trace_id(trace_id: str | None = None) -> str:
    tid = trace_id or str(uuid.uuid4())
    _trace_id_var.set(tid)
    return tid


def clear_trace_id() -> None:
    _trace_id_var.set(None)


def _preview(text: str | None, limit: int = 500) -> str:
    raw = (text or '').strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3] + '...'


def emit_evento(
    tipo: str,
    *,
    trace_id: str | None = None,
    estudiante=None,
    cliente=None,
    curso=None,
    modulo=None,
    agente: str = '',
    canal: str = 'whatsapp_edu',
    facilitador_checkpoint: str = '',
    regla_aplicada: str = '',
    es_reto: bool | None = None,
    modelo: str = '',
    latencia_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    input_preview: str = '',
    output_preview: str = '',
    metadata: dict | None = None,
) -> 'EventoIA | None':
    """Persiste un evento IA. Falla en silencio (no rompe flujo WhatsApp)."""
    try:
        from core.models import EventoIA

        tid = trace_id or get_or_create_trace_id()
        evento = EventoIA.objects.create(
            trace_id=tid,
            tipo=tipo,
            estudiante=estudiante,
            cliente=cliente,
            curso=curso,
            modulo=modulo,
            agente=agente or '',
            canal=canal or EventoIA.CANAL_WHATSAPP_EDU,
            facilitador_checkpoint=facilitador_checkpoint or '',
            regla_aplicada=regla_aplicada or '',
            es_reto=es_reto,
            modelo=modelo or '',
            latencia_ms=latencia_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            input_preview=_preview(input_preview, 800),
            output_preview=_preview(output_preview, 800),
            metadata=metadata or {},
        )
        return evento
    except Exception as exc:
        logger.warning('No se pudo emitir evento IA tipo=%s: %s', tipo, exc)
        return None


def emit_modulo_completado(modulo_completado, *, origen: str = 'signal') -> None:
    from core.models import EventoIA

    prog = modulo_completado.progreso
    emit_evento(
        EventoIA.TIPO_MODULO_COMPLETADO,
        estudiante=prog.estudiante,
        cliente=getattr(prog.estudiante, 'cliente', None),
        curso=prog.curso,
        modulo=modulo_completado.modulo,
        metadata={
            'origen': origen,
            'modulo_completado_id': modulo_completado.id,
            'respuesta_correcta': modulo_completado.respuesta_correcta,
        },
    )


def emit_checkpoint_evaluado(
    decision,
    *,
    estudiante,
    curso,
    modulo,
    origen: str = 'webhook',
) -> None:
    from core.models import EventoIA

    emit_evento(
        EventoIA.TIPO_CHECKPOINT_EVALUADO,
        estudiante=estudiante,
        cliente=getattr(estudiante, 'cliente', None),
        curso=curso,
        modulo=modulo,
        facilitador_checkpoint=decision.facilitador_checkpoint,
        regla_aplicada=decision.regla_aplicada,
        es_reto=decision.es_reto,
        metadata={
            'origen': origen,
            'numero_modulo': decision.numero_modulo,
            'total_modulos': decision.total_modulos,
            'usar_agentes_ia_curso': decision.usar_agentes_ia_curso,
            'modulo_ya_completado_anulo': decision.modulo_ya_completado_anulo,
        },
    )


def emit_ia_agent_triggered(
    *,
    estudiante=None,
    cliente=None,
    curso=None,
    modulo=None,
    agente: str,
    mensaje: str = '',
    respuesta: str = '',
    modelo: str = '',
    latencia_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    canal: str = 'whatsapp_edu',
    metadata: dict | None = None,
) -> None:
    from core.models import EventoIA

    emit_evento(
        EventoIA.TIPO_IA_AGENT_TRIGGERED,
        estudiante=estudiante,
        cliente=cliente,
        curso=curso,
        modulo=modulo,
        agente=agente,
        canal=canal,
        modelo=modelo,
        latencia_ms=latencia_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        input_preview=mensaje,
        output_preview=respuesta,
        metadata=metadata or {},
    )


def emit_rag_query_executed(
    *,
    pregunta: str,
    cliente=None,
    canal: str = 'whatsapp_comercial',
    chunks_count: int = 0,
    contexto_chars: int = 0,
    chunks: list | None = None,
    metadata: dict | None = None,
) -> None:
    from core.models import EventoIA

    meta = dict(metadata or {})
    meta.update({
        'chunks_count': chunks_count,
        'contexto_chars': contexto_chars,
        'chunks': (chunks or [])[:20],
    })
    emit_evento(
        EventoIA.TIPO_RAG_QUERY_EXECUTED,
        cliente=cliente,
        canal=canal,
        agente='nati',
        input_preview=pregunta,
        metadata=meta,
    )


def emit_webhook_recibido(
    *,
    mensaje: str,
    telefono: str = '',
    canal: str = 'whatsapp_edu',
    estudiante=None,
    cliente=None,
    metadata: dict | None = None,
) -> None:
    from core.models import EventoIA

    meta = dict(metadata or {})
    if telefono:
        meta['telefono_suffix'] = telefono[-4:]
    emit_evento(
        EventoIA.TIPO_WEBHOOK_RECIBIDO,
        estudiante=estudiante,
        cliente=cliente,
        canal=canal,
        input_preview=mensaje,
        metadata=meta,
    )


def emit_intent_detectado(
    *,
    intent: str,
    mensaje: str,
    estudiante=None,
    curso=None,
    modulo=None,
    canal: str = 'whatsapp_edu',
    metadata: dict | None = None,
) -> None:
    from core.models import EventoIA

    meta = dict(metadata or {})
    meta['intent'] = intent
    emit_evento(
        EventoIA.TIPO_INTENT_DETECTADO,
        estudiante=estudiante,
        cliente=getattr(estudiante, 'cliente', None) if estudiante else None,
        curso=curso,
        modulo=modulo,
        canal=canal,
        regla_aplicada=intent,
        input_preview=mensaje,
        metadata=meta,
    )


def detectar_intent_con_evento(
    mensaje: str,
    *,
    estudiante=None,
    curso=None,
    modulo=None,
    canal: str = 'whatsapp_edu',
) -> str:
    """Detecta intent y emite evento auditable en el mismo trace."""
    from core.intent_detector import detect_intent

    intent = detect_intent(mensaje)
    emit_intent_detectado(
        intent=intent,
        mensaje=mensaje,
        estudiante=estudiante,
        curso=curso,
        modulo=modulo,
        canal=canal,
    )
    return intent


def emit_mensaje_enviado(
    *,
    telefono: str,
    texto: str,
    mensaje_id: str | None = None,
    estudiante=None,
    cliente=None,
    curso=None,
    canal: str = 'whatsapp_edu',
    agente: str = '',
    metadata: dict | None = None,
) -> None:
    from core.models import EventoIA

    if estudiante is None and telefono:
        try:
            from core.models import Estudiante
            import re

            tel = re.sub(r'\D', '', telefono or '')
            estudiante = Estudiante.objects.filter(telefono=tel).first()
            if not estudiante and len(tel) >= 10:
                estudiante = Estudiante.objects.filter(telefono__endswith=tel[-10:]).first()
        except Exception:
            pass

    meta = dict(metadata or {})
    if mensaje_id:
        meta['twilio_sid'] = mensaje_id
    if telefono:
        meta['telefono_suffix'] = telefono[-4:]

    emit_evento(
        EventoIA.TIPO_MENSAJE_ENVIADO,
        estudiante=estudiante,
        cliente=cliente or (getattr(estudiante, 'cliente', None) if estudiante else None),
        curso=curso,
        canal=canal,
        agente=agente,
        output_preview=texto,
        metadata=meta,
    )


def serializar_evento(evento) -> dict[str, Any]:
    return {
        'id': evento.id,
        'trace_id': str(evento.trace_id),
        'tipo': evento.tipo,
        'tipo_label': evento.get_tipo_display(),
        'agente': evento.agente,
        'canal': evento.canal,
        'facilitador_checkpoint': evento.facilitador_checkpoint,
        'regla_aplicada': evento.regla_aplicada,
        'es_reto': evento.es_reto,
        'modelo': evento.modelo,
        'latencia_ms': evento.latencia_ms,
        'input_preview': evento.input_preview,
        'output_preview': evento.output_preview,
        'metadata': evento.metadata,
        'estudiante_id': evento.estudiante_id,
        'estudiante_nombre': getattr(evento.estudiante, 'nombre', '') if evento.estudiante_id else '',
        'curso_id': evento.curso_id,
        'curso_nombre': getattr(evento.curso, 'nombre', '') if evento.curso_id else '',
        'modulo_id': evento.modulo_id,
        'created_at': evento.created_at.isoformat(),
    }
