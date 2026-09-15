"""Menú sandbox: Agentes (submenú) | Cursos — SOLO número sandbox Twilio.

No afecta WABA de producción ni `numero_whatsapp_nat` de orgs.
Activar/desactivar: SANDBOX_MENU_ENABLED (default True).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.utils import timezone

from core.nati import normalizar_telefono_whatsapp

logger = logging.getLogger(__name__)

MODO_MENU = 'menu'
MODO_AGENTES = 'agentes'
MODO_NAT = 'nat'
MODO_COACH = 'coach'
MODO_IA_CAMPO = 'ia_campo'
MODO_CURSOS = 'cursos'

MODOS_AGENTE = (MODO_NAT, MODO_COACH, MODO_IA_CAMPO)

TEXTO_MENU = (
    "👋 *eki sandbox*\n\n"
    "Elige una opción:\n"
    "1️⃣ Agentes IA\n"
    "2️⃣ Cursos (*Tome las riendas*)\n\n"
    "Escribe *1* o *2*.\n"
    "En cualquier momento: *menu* para volver."
)

TEXTO_AGENTES = (
    "🤖 *Agentes IA* (sandbox)\n\n"
    "1️⃣ Agrónomo (Nat) — cultivo y campo\n"
    "2️⃣ Coach — hábitos y motivación\n"
    "3️⃣ Profe IA — IA fácil para el campo\n\n"
    "Cada agente *recuerda* la conversación.\n"
    "Escribe *1*, *2* o *3*.\n"
    "*reiniciar* = memoria nueva · *menu* = menú principal."
)

# Comandos para cortar memoria (todos los agentes sandbox).
_COMANDOS_REINICIAR = frozenset({
    'reiniciar',
    'reset',
    'nueva',
    'nuevo',
    'limpiar',
    'limpiar memoria',
    'empezar de nuevo',
    'empezar nuevamente',
    'borra memoria',
    'borrar memoria',
})


@dataclass
class SandboxRouteDecision:
    action: str
    # show_menu | show_agentes | nat | coach | ia_campo | cursos | cursos_bootstrap
    from_number: str = ''
    telefono_usuario: str = ''
    texto_menu: str = TEXTO_MENU
    reset_nat: bool = False  # True = comando *reiniciar* (corte de memoria)
    saludo_entrada: bool = False  # Entró por menú; no pasar "1"/"2" al LLM


def sandbox_menu_enabled() -> bool:
    return bool(getattr(settings, 'SANDBOX_MENU_ENABLED', True))


def sandbox_number() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_SANDBOX_NUMBER', '14155238886') or '14155238886'
    )


def es_destino_sandbox(to_or_payload: Any) -> bool:
    if not sandbox_menu_enabled():
        return False
    if isinstance(to_or_payload, str):
        to_raw = to_or_payload
    elif to_or_payload is None:
        to_raw = ''
    else:
        try:
            to_raw = to_or_payload.get('To', '')  # type: ignore[union-attr]
        except Exception:
            to_raw = ''
    to_limpio = normalizar_telefono_whatsapp(to_raw)
    sb = sandbox_number()
    return bool(to_limpio and sb and to_limpio == sb)


def _extract_from_body(payload: Any) -> tuple[str, str, str]:
    if isinstance(payload, str) or payload is None:
        return '', '', ''
    try:
        from_raw = payload.get('From', '')  # type: ignore[union-attr]
        to_raw = payload.get('To', '')  # type: ignore[union-attr]
        body = (payload.get('Body', '') or '').strip()  # type: ignore[union-attr]
    except Exception:
        return '', '', ''
    return (
        normalizar_telefono_whatsapp(from_raw),
        normalizar_telefono_whatsapp(to_raw),
        body,
    )


def _get_or_create_sesion(telefono: str):
    from core.models import SandboxCanalSesion

    sesion, _ = SandboxCanalSesion.objects.get_or_create(
        telefono=telefono,
        defaults={'modo': MODO_MENU},
    )
    return sesion


def _set_modo(sesion, modo: str, *, reset_nat: bool = False) -> None:
    sesion.modo = modo
    fields = ['modo', 'actualizado_en']
    if reset_nat:
        sesion.memoria_corte_en = timezone.now()
        fields.append('memoria_corte_en')
    sesion.save(update_fields=fields)


def _normalizar_eleccion_raiz(body: str) -> str | None:
    t = (body or '').strip().lower()
    if t in ('menu', 'menú', 'inicio', 'start'):
        return 'menu'
    if t in ('hola', 'hi', 'hey', 'buenas', 'buen día', 'buenos días'):
        return 'saludo'
    if t in ('1', '1️⃣', 'uno', 'agente', 'agentes', 'ia', 'ais'):
        return MODO_AGENTES
    if t in ('2', '2️⃣', 'dos', 'curso', 'cursos', 'aprender', 'edu', 'riendas'):
        return MODO_CURSOS
    # Compat: atajos directos
    if t in ('nat', 'nati', 'agronomo', 'agrónomo'):
        return MODO_NAT
    if t in ('coach', 'entrenador'):
        return MODO_COACH
    if t in ('profe', 'profe ia', 'ia campo', 'ia_campo'):
        return MODO_IA_CAMPO
    return None


def _normalizar_eleccion_agentes(body: str) -> str | None:
    t = (body or '').strip().lower()
    if t in ('menu', 'menú', 'inicio', 'atras', 'atrás', 'volver'):
        return 'menu'
    if t in ('1', '1️⃣', 'uno', 'nat', 'nati', 'agronomo', 'agrónomo'):
        return MODO_NAT
    if t in ('2', '2️⃣', 'dos', 'coach', 'entrenador'):
        return MODO_COACH
    if t in ('3', '3️⃣', 'tres', 'profe', 'profe ia', 'ia', 'ia campo'):
        return MODO_IA_CAMPO
    return None


def es_comando_reiniciar(body: str) -> bool:
    t = (body or '').strip().lower()
    if not t:
        return False
    if t in _COMANDOS_REINICIAR:
        return True
    # Variantes cortas / con signos
    t2 = t.replace('!', '').replace('.', '').strip()
    return t2 in _COMANDOS_REINICIAR


def marcar_corte_memoria_nat(telefono: str) -> None:
    """Reinicia memoria conversacional de agentes sandbox para este teléfono."""
    if not telefono:
        return
    sesion = _get_or_create_sesion(telefono)
    sesion.memoria_corte_en = timezone.now()
    sesion.save(update_fields=['memoria_corte_en', 'actualizado_en'])


def memoria_corte_nat(telefono: str):
    """Timestamp de corte: logs anteriores no entran al historial LLM."""
    from core.models import SandboxCanalSesion

    if not telefono:
        return None
    row = SandboxCanalSesion.objects.filter(telefono=telefono).only('memoria_corte_en').first()
    return row.memoria_corte_en if row else None


def resolver_ruta_sandbox(payload: Any) -> SandboxRouteDecision:
    from_tel, to_tel, body = _extract_from_body(payload)
    decision = SandboxRouteDecision(
        action='show_menu',
        from_number=to_tel or sandbox_number(),
        telefono_usuario=from_tel,
    )
    if not from_tel:
        return decision

    sesion = _get_or_create_sesion(from_tel)

    # Dentro del submenú agentes: priorizar 1/2/3 de agentes
    if sesion.modo == MODO_AGENTES:
        eleccion_ag = _normalizar_eleccion_agentes(body)
        if eleccion_ag == 'menu':
            _set_modo(sesion, MODO_MENU)
            decision.action = 'show_menu'
            return decision
        if eleccion_ag == MODO_NAT:
            # Continúa memoria; no cortar al entrar (usar *reiniciar*).
            _set_modo(sesion, MODO_NAT)
            decision.action = 'nat'
            decision.saludo_entrada = True
            return decision
        if eleccion_ag == MODO_COACH:
            _set_modo(sesion, MODO_COACH)
            decision.action = 'coach'
            decision.saludo_entrada = True
            return decision
        if eleccion_ag == MODO_IA_CAMPO:
            _set_modo(sesion, MODO_IA_CAMPO)
            decision.action = 'ia_campo'
            decision.saludo_entrada = True
            return decision
        # Texto libre en submenú → re-mostrar opciones
        decision.action = 'show_agentes'
        return decision

    # Dentro de un agente: *reiniciar* corta memoria sin salir del modo
    if sesion.modo in MODOS_AGENTE and es_comando_reiniciar(body):
        decision.action = sesion.modo
        decision.reset_nat = True
        return decision

    eleccion = _normalizar_eleccion_raiz(body)

    if eleccion == 'menu':
        _set_modo(sesion, MODO_MENU)
        decision.action = 'show_menu'
        return decision

    if eleccion == MODO_AGENTES:
        _set_modo(sesion, MODO_AGENTES)
        decision.action = 'show_agentes'
        return decision

    if eleccion == MODO_NAT:
        _set_modo(sesion, MODO_NAT)
        decision.action = 'nat'
        decision.saludo_entrada = True
        return decision

    if eleccion == MODO_COACH:
        _set_modo(sesion, MODO_COACH)
        decision.action = 'coach'
        decision.saludo_entrada = True
        return decision

    if eleccion == MODO_IA_CAMPO:
        _set_modo(sesion, MODO_IA_CAMPO)
        decision.action = 'ia_campo'
        decision.saludo_entrada = True
        return decision

    if eleccion == MODO_CURSOS:
        _set_modo(sesion, MODO_CURSOS)
        # Primera entrada (eligió 2): bootstrap Riendas; luego sticky cursos
        decision.action = 'cursos_bootstrap'
        return decision

    if eleccion == 'saludo' and sesion.modo == MODO_MENU:
        decision.action = 'show_menu'
        return decision

    if sesion.modo == MODO_NAT:
        decision.action = 'nat'
        return decision

    if sesion.modo == MODO_COACH:
        decision.action = 'coach'
        return decision

    if sesion.modo == MODO_IA_CAMPO:
        decision.action = 'ia_campo'
        return decision

    if sesion.modo == MODO_CURSOS:
        decision.action = 'cursos'
        return decision

    decision.action = 'show_menu'
    return decision


def enviar_texto_sandbox(telefono_usuario: str, from_number: str, texto: str, *, agente: str = 'sandbox_menu') -> dict:
    from core.utils import enviar_whatsapp_twilio
    from core.wa_reply_context import reply_from

    with reply_from(from_number):
        return enviar_whatsapp_twilio(
            telefono_usuario,
            texto,
            from_number=from_number,
            canal_evento='whatsapp_sandbox',
            agente_evento=agente,
        )


def enviar_menu_sandbox(telefono_usuario: str, from_number: str) -> dict:
    return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_MENU)


def enviar_menu_agentes(telefono_usuario: str, from_number: str) -> dict:
    return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_AGENTES, agente='sandbox_agentes')


def bootstrap_cursos_sandbox(telefono_usuario: str, from_number: str) -> bool:
    """Inscribe / reengancha demo Tome las riendas. True si envió algo útil."""
    from core.catalogo_demo_carousel import arrancar_demo_riendas, curso_demo_riendas
    from core.utils import enviar_whatsapp_twilio
    from core.wa_reply_context import reply_from

    curso = curso_demo_riendas()
    if curso is None:
        with reply_from(from_number):
            enviar_whatsapp_twilio(
                telefono_usuario,
                "Aún no hay curso demo configurado (EKI_DEMO_RIENDAS_CURSO_ID). "
                "Avisa a eki tech.\n\n_Escribe *menu* para volver._",
                from_number=from_number,
                canal_evento='whatsapp_sandbox',
                agente_evento='sandbox_cursos',
            )
        return True

    with reply_from(from_number):
        return bool(
            arrancar_demo_riendas(
                telefono=telefono_usuario,
                dest_wa=telefono_usuario,
                sandbox=True,
            )
        )


def _manejar_agente_extra(decision: SandboxRouteDecision, body: str) -> str:
    """Coach / Profe IA: reinicio, saludo de entrada o turno LLM. Returns 'handled'."""
    from core.sandbox_agentes import responder_agente_sandbox, saludo_agente

    agente = 'coach' if decision.action == 'coach' else 'ia_campo'
    from_n = decision.from_number or sandbox_number()

    if decision.reset_nat:
        marcar_corte_memoria_nat(decision.telefono_usuario)
        texto = saludo_agente(agente, reinicio=True)  # type: ignore[arg-type]
    elif decision.saludo_entrada:
        texto = saludo_agente(agente)  # type: ignore[arg-type]
    else:
        texto = responder_agente_sandbox(agente, body, telefono=decision.telefono_usuario)  # type: ignore[arg-type]
    try:
        enviar_texto_sandbox(
            decision.telefono_usuario,
            from_n,
            texto,
            agente=f'sandbox_{agente}',
        )
    except Exception:
        logger.exception('sandbox_agente_send_failed agente=%s', agente)
    return 'handled'


def dispatch_sandbox_menu(payload: Any) -> str | None:
    """
    Intercepta el sandbox Twilio cuando SANDBOX_MENU_ENABLED.

    Returns:
      None — no aplica
      'handled' — respuesta enviada
      'nat' — enrutar a Nat
      'cursos' — enrutar a edu
    """
    if not es_destino_sandbox(payload):
        return None
    decision = resolver_ruta_sandbox(payload)
    from_n = decision.from_number or sandbox_number()
    _, _, body = _extract_from_body(payload)

    if decision.action == 'show_menu':
        try:
            enviar_menu_sandbox(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_menu_send_failed tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'show_agentes':
        try:
            enviar_menu_agentes(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_agentes_send_failed tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'nat':
        if decision.reset_nat:
            marcar_corte_memoria_nat(decision.telefono_usuario)
            try:
                enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    "🌿 *Agrónomo Nat* (sandbox)\n\n"
                    "Memoria reiniciada. Empezamos de cero.\n"
                    "¿En qué cultivo o duda te ayudo?\n\n"
                    "_*reiniciar* otra vez · *menu* para volver._",
                    agente='sandbox_nat',
                )
            except Exception:
                logger.exception('sandbox_nat_saludo_fail')
            return 'handled'
        if decision.saludo_entrada:
            try:
                enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    "🌿 *Agrónomo Nat* (sandbox)\n\n"
                    "Seguimos donde íbamos (memoria larga).\n"
                    "Cuéntame la duda, o escribe *reiniciar* para empezar de cero.\n\n"
                    "_*menu* para volver._",
                    agente='sandbox_nat',
                )
            except Exception:
                logger.exception('sandbox_nat_saludo_entrada_fail')
            return 'handled'
        return 'nat'

    if decision.action in ('coach', 'ia_campo'):
        return _manejar_agente_extra(decision, body)

    if decision.action == 'cursos_bootstrap':
        try:
            bootstrap_cursos_sandbox(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_cursos_bootstrap_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'cursos':
        return 'cursos'

    try:
        enviar_menu_sandbox(decision.telefono_usuario, from_n)
    except Exception:
        logger.exception('sandbox_menu_send_failed tel=%s', decision.telefono_usuario)
    return 'handled'
