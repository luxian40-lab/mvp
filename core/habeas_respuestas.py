"""Clasificación y flujo Habeas Data (texto libre o botones Twilio)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

CTX_CONFIRMA_RECHAZO = 'habeas_confirmando_rechazo'

MSG_CONFIRMA_RECHAZO = (
    "¿Seguro que *no* quieres aceptar el tratamiento de datos?\n\n"
    "Sin esa autorización no podemos activar tu curso.\n\n"
    "👉 Responde *No* para confirmar que no aceptas.\n"
    "👉 O escribe *Acepto* si cambiaste de opinión."
)

MSG_RECHAZO_FINAL = (
    "😔 Entendemos tu decisión.\n\n"
    "Sin la aceptación de la política de datos no podemos "
    "activar tu cuenta en la plataforma.\n\n"
    "Si cambias de opinión, escríbenos en cualquier momento. 🌱"
)

MSG_ACEPTO_CEDULA = (
    "✅ *¡Gracias por aceptar!*\n\n"
    "Para verificar tu identidad, por favor escribe "
    "tu *número de cédula* (solo los números, sin puntos ni espacios).\n\n"
    "👉 Ejemplo: 1234567890"
)


def _fold(s: str) -> str:
    s = (s or '').strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^\w\s]+', ' ', s)
    return ' '.join(s.split())


def texto_desde_webhook_twilio(post_data: dict, msg_body: str = '') -> str:
    """Prefer Body; si viene vacío (quick reply), usa ButtonPayload/Text."""
    from .campana_respuestas import extraer_texto_respuesta

    return extraer_texto_respuesta(post_data or {}, msg_body or '')


def clasificar_respuesta_habeas(texto: str) -> Optional[str]:
    """
    Devuelve 'acepto' | 'rechazo' | None.

    Regla dura: evaluar rechazo ANTES que aceptación, y con igualdad/token
    (no substring). Evita que "No acepto" matchee "acepto".
    """
    folded = _fold(texto)
    if not folded:
        return None

    if folded in {
        'no_acepto',
        'noacepto',
        'reject',
        'rechazo',
        'rechazar',
        'deny',
        'opt_out',
        'habeas_no',
        'habeas_rechazo',
    }:
        return 'rechazo'
    if folded in {
        'acepto',
        'aceptar',
        'accept',
        'opt_in',
        'habeas_si',
        'habeas_acepto',
        'si_acepto',
    }:
        return 'acepto'

    rechazo_exactos = {
        'no',
        'n',
        'no acepto',
        'no aceptar',
        'no estoy de acuerdo',
        'no de acuerdo',
        'rechazo',
        'rechazar',
    }
    if folded in rechazo_exactos or folded.startswith('no acept'):
        return 'rechazo'

    acepto_exactos = {
        'si',
        's',
        'yes',
        'y',
        'ok',
        'okay',
        'acepto',
        'aceptar',
        'de acuerdo',
        'estoy de acuerdo',
        'adelante',
    }
    if folded in acepto_exactos:
        return 'acepto'

    tokens = folded.split()
    if tokens and tokens[0] == 'no' and any(t.startswith('acept') for t in tokens[1:]):
        return 'rechazo'
    if 'acepto' in tokens or 'aceptar' in tokens:
        if tokens[0] == 'no':
            return 'rechazo'
        return 'acepto'

    return None


def clasificar_confirmacion_rechazo(texto: str) -> Optional[str]:
    """
    Segundo paso tras un primer «No acepto».

    - 'acepto': cambió de opinión
    - 'confirmar_rechazo': confirma que no quiere → cerrar
    - None: repreguntar
    """
    folded = _fold(texto)
    if not folded:
        return None

    # En confirmación, "sí" / "ok" = sí, confirmo que NO acepto (no activar cuenta).
    confirmar = {
        'si',
        's',
        'yes',
        'y',
        'ok',
        'okay',
        'confirmo',
        'seguro',
        'no',
        'n',
        'no acepto',
        'noacepto',
        'no_acepto',
        'rechazo',
        'rechazar',
        'si no acepto',
        'no quiero',
    }
    if folded in confirmar or folded.startswith('no acept'):
        return 'confirmar_rechazo'

    if folded in {
        'acepto',
        'aceptar',
        'si acepto',
        'quiero aceptar',
        'cambio de opinion',
        'cambie de opinion',
        'de acuerdo',
        'estoy de acuerdo',
        'adelante',
        'habeas_acepto',
        'habeas_si',
    }:
        return 'acepto'

    base = clasificar_respuesta_habeas(texto)
    if base == 'acepto':
        return 'acepto'
    if base == 'rechazo':
        return 'confirmar_rechazo'
    return None


def _ctx(estudiante) -> dict:
    raw = getattr(estudiante, 'contexto_temporal', None)
    return dict(raw) if isinstance(raw, dict) else {}


def _set_ctx(estudiante, ctx: dict) -> None:
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['contexto_temporal'])


def aplicar_respuesta_habeas(estudiante, texto: str) -> dict[str, Any]:
    """
    Aplica el paso de habeas (con confirmación de rechazo).

    Returns:
        {
          'accion': 'acepto' | 'pide_confirmacion' | 'rechazo_final' | 'reenviar_plantilla' | 'repite_confirmacion',
          'texto': str | None,
        }
    """
    from django.utils import timezone

    ctx = _ctx(estudiante)
    confirmando = bool(ctx.get(CTX_CONFIRMA_RECHAZO))

    if confirmando:
        paso = clasificar_confirmacion_rechazo(texto)
        if paso == 'acepto':
            ctx.pop(CTX_CONFIRMA_RECHAZO, None)
            estudiante.acepto_terminos = True
            estudiante.fecha_aceptacion_terminos = timezone.now()
            estudiante.estado_chat = 'ESPERANDO_CEDULA'
            estudiante.contexto_temporal = ctx
            estudiante.save(
                update_fields=[
                    'acepto_terminos',
                    'fecha_aceptacion_terminos',
                    'estado_chat',
                    'contexto_temporal',
                ]
            )
            return {'accion': 'acepto', 'texto': MSG_ACEPTO_CEDULA}
        if paso == 'confirmar_rechazo':
            ctx.pop(CTX_CONFIRMA_RECHAZO, None)
            _set_ctx(estudiante, ctx)
            return {'accion': 'rechazo_final', 'texto': MSG_RECHAZO_FINAL}
        return {'accion': 'repite_confirmacion', 'texto': MSG_CONFIRMA_RECHAZO}

    decision = clasificar_respuesta_habeas(texto)
    if decision == 'acepto':
        ctx.pop(CTX_CONFIRMA_RECHAZO, None)
        estudiante.acepto_terminos = True
        estudiante.fecha_aceptacion_terminos = timezone.now()
        estudiante.estado_chat = 'ESPERANDO_CEDULA'
        estudiante.contexto_temporal = ctx
        estudiante.save(
            update_fields=[
                'acepto_terminos',
                'fecha_aceptacion_terminos',
                'estado_chat',
                'contexto_temporal',
            ]
        )
        return {'accion': 'acepto', 'texto': MSG_ACEPTO_CEDULA}

    if decision == 'rechazo':
        ctx[CTX_CONFIRMA_RECHAZO] = True
        _set_ctx(estudiante, ctx)
        return {'accion': 'pide_confirmacion', 'texto': MSG_CONFIRMA_RECHAZO}

    return {'accion': 'reenviar_plantilla', 'texto': None}
