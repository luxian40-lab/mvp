"""Despacho de la línea principal: plan y permisos, identidad, menú, asesores y cursos.

Cada paso devuelve None si la acción no es suya; el orden es el del despachador original.
Los nombres de `core.sandbox_menu` se buscan ahí al momento de llamar: los tests parchean ahí.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.sandbox_menu import SandboxRouteDecision

logger = logging.getLogger(__name__)


def _menu():
    from core import sandbox_menu

    return sandbox_menu


def despachar(decision: SandboxRouteDecision, payload: Any, body: str, from_n: str) -> str:
    """'handled', 'nat' o 'cursos'. Una acción que ningún paso reconoce vuelve al menú."""
    for paso in (
        _corte_por_permiso_o_plan,
        _responder_identidad,
        _responder_menu,
        _responder_asesor,
        _responder_cursos,
    ):
        respuesta = paso(decision, payload, body, from_n)
        if respuesta is not None:
            return respuesta
    try:
        _menu().enviar_menu_sandbox(decision.telefono_usuario, from_n)
    except Exception:
        logger.exception('sandbox_menu_send_failed tel=%s', decision.telefono_usuario)
    return 'handled'


def _corte_por_permiso_o_plan(decision: SandboxRouteDecision, payload: Any, body: str, from_n: str) -> str | None:
    """Asesor no permitido en la línea, o el plan no incluye lo pedido."""
    if decision.action in ('nat', 'coach', 'ia_campo', 'ventas', 'finanzas', 'cafe'):
        from core.lineas.oferta import agente_permitido

        if not agente_permitido(decision.telefono_usuario, decision.action):
            _menu()._set_modo(_menu()._get_or_create_sesion(decision.telefono_usuario), _menu().MODO_MENU)
            try:
                _menu().enviar_menu_agentes(decision.telefono_usuario, from_n)
            except Exception:
                logger.exception('sandbox_agente_no_permitido tel=%s', decision.telefono_usuario)
            return 'handled'

    if (
        decision.action in _menu()._ACCIONES_ASESOR or decision.action == 'show_formacion'
    ):
        plan = _menu().resolver_plan(decision.telefono_usuario)
        bloqueo = ''
        if not plan.activo:
            bloqueo = _menu().TEXTO_SIN_PLAN
        elif decision.action == 'show_formacion' and not plan.incluye_cursos:
            bloqueo = _menu().TEXTO_PLAN_SIN_CURSOS
        elif decision.action in _menu()._ACCIONES_ASESOR and not plan.incluye_asesor:
            bloqueo = _menu().TEXTO_PLAN_SIN_ASESOR
        if bloqueo:
            _menu()._set_modo(_menu()._get_or_create_sesion(decision.telefono_usuario), _menu().MODO_MENU)
            try:
                _menu().enviar_texto_sandbox(decision.telefono_usuario, from_n, bloqueo, agente='sandbox_plan')
            except Exception:
                logger.exception('sandbox_plan_send_failed tel=%s', decision.telefono_usuario)
            return 'handled'
    return None


def _responder_identidad(decision: SandboxRouteDecision, payload: Any, body: str, from_n: str) -> str | None:
    """Habeas, cédula o confirmación pedidos desde el menú."""
    if decision.action == 'pedir_habeas':
        try:
            from core.sandbox_canal import enviar_sandbox_habeas

            enviar_sandbox_habeas(decision.telefono_usuario)
        except Exception:
            logger.exception('sandbox_pedir_habeas_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'pedir_cedula':
        from core.habeas_respuestas import MSG_ACEPTO_CEDULA

        try:
            _menu().enviar_texto_sandbox(
                decision.telefono_usuario, from_n, MSG_ACEPTO_CEDULA, agente='habeas_meta',
            )
        except Exception:
            logger.exception('sandbox_pedir_cedula_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'confirmar_datos':
        from core.utils_telefono import estudiante_por_telefono

        est = estudiante_por_telefono(decision.telefono_usuario)
        if est is not None:
            try:
                _menu()._enviar_confirma_numero(decision.telefono_usuario, from_n, est)
            except Exception:
                logger.exception('sandbox_confirmar_datos_fail tel=%s', decision.telefono_usuario)
        return 'handled'
    return None


def _responder_menu(decision: SandboxRouteDecision, payload: Any, body: str, from_n: str) -> str | None:
    """Menú, lista de agentes, cursos empezados y catálogo de formación."""
    if decision.action == 'show_menu':
        try:
            _menu().enviar_menu_sandbox(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_menu_send_failed tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'show_agentes':
        try:
            _menu().enviar_menu_agentes(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_agentes_send_failed tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'continuar_curso':
        try:
            curso_id = int(decision.texto_menu)
            progreso = next(p for p in _menu()._abiertos_del_mes(decision.telefono_usuario) if p.curso_id == curso_id)
            _menu()._entrar_en_progreso(decision.telefono_usuario, from_n, progreso)
        except StopIteration:
            _menu().enviar_menu_sandbox(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_continuar_curso_fail')
        return 'handled'

    if decision.action == 'seguir_curso':
        try:
            _menu().entrar_cursos_inscrito(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_seguir_curso_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'show_formacion':
        try:
            _menu().enviar_catalogo_formacion(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_formacion_send_failed')
        return 'handled'

    if decision.action == 'catalogo_general':
        try:
            _menu().responder_catalogo_general(decision.telefono_usuario, from_n, decision.texto_menu)
        except Exception:
            logger.exception('sandbox_catalogo_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action in ('show_asesoria', 'repreguntar_asesoria'):
        from django.conf import settings

        from core.lineas.principal.asesores import (
            enviar_pregunta_asesoria,
            enviar_repregunta_asesoria,
        )

        try:
            if decision.action == 'repreguntar_asesoria':
                enviar_repregunta_asesoria(decision.telefono_usuario, from_n)
            elif getattr(settings, 'EKI_ASESORIA_PREGUNTA', False):
                enviar_pregunta_asesoria(decision.telefono_usuario, from_n)
            else:
                _menu().enviar_menu_agentes(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_asesoria_send_failed')
        return 'handled'
    return None


def _responder_asesor(decision: SandboxRouteDecision, payload: Any, body: str, from_n: str) -> str | None:
    """Nat y los demás asesores."""
    if decision.action == 'nat':
        if decision.reset_nat:
            _menu().marcar_corte_memoria_nat(decision.telefono_usuario)
            try:
                from core.sandbox_agentes import presentacion_agente

                _menu().enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    presentacion_agente('nat', reinicio=True),
                    agente='sandbox_nat',
                )
            except Exception:
                logger.exception('sandbox_nat_saludo_fail')
            return 'handled'
        if decision.saludo_entrada:
            try:
                from core.sandbox_agentes import presentacion_agente

                _menu().enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    presentacion_agente('nat'),
                    agente='sandbox_nat',
                )
            except Exception:
                logger.exception('sandbox_nat_saludo_entrada_fail')
            return 'handled'
        from core.planes_linea import registrar_pregunta_asesor
        from core.sandbox_agentes import _tope_asesor_mes, excedio_cupo_ia_linea

        if decision.es_toque:
            try:
                _menu().enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    _menu().TEXTO_TOQUE_NO_PREGUNTA,
                    agente='sandbox_plan',
                )
            except Exception:
                logger.exception('sandbox_nat_toque_fail')
            return 'handled'
        if excedio_cupo_ia_linea(decision.telefono_usuario):
            try:
                _menu().enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    _menu().texto_cupo_ia(_tope_asesor_mes(decision.telefono_usuario)),
                    agente='sandbox_plan',
                )
            except Exception:
                logger.exception('sandbox_nat_cupo_fail')
            return 'handled'
        registrar_pregunta_asesor(decision.telefono_usuario)
        _menu()._reaccion_espera(decision.telefono_usuario, _menu()._message_id(payload))
        return 'nat'

    if decision.action in ('coach', 'ia_campo', 'ventas', 'finanzas', 'cafe'):
        return _menu()._manejar_agente_extra(decision, body, _menu()._message_id(payload))
    return None


def _responder_cursos(decision: SandboxRouteDecision, payload: Any, body: str, from_n: str) -> str | None:
    """Entrada al curso."""
    if decision.action == 'cursos_bootstrap':
        try:
            _menu().bootstrap_cursos_sandbox(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_cursos_bootstrap_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'cursos':
        _menu()._reaccion_espera(decision.telefono_usuario, _menu()._message_id(payload))
        return 'cursos'
    return None
