"""Asesoría de la línea principal: pregunta o lista de agentes y turno de Coach, Profe IA, Ventas, Finanzas.

Los envíos y la sesión se buscan en `core.sandbox_menu` al momento de llamar:
los tests parchean ahí.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import DatabaseError

if TYPE_CHECKING:
    from core.sandbox_menu import SandboxRouteDecision

logger = logging.getLogger(__name__)


def _menu():
    from core import sandbox_menu

    return sandbox_menu


FILAS_AGENTES = [
    ('nat', 'Agrónomo', 'Experto en café'),
    ('coach', 'Coach', 'Motivación y metas diarias'),
    ('profe', 'Innovación e IA', 'Mejor apropiación tecnológica'),
    ('ventas', 'Ventas', 'Aumenta tus ingresos'),
    ('finanzas', 'Finanzas', 'Educación financiera a tu alcance'),
]


def texto_lista_agentes(tope: int) -> str:
    cupo = f"Tiene hasta {tope} preguntas este mes.\n\n" if tope > 0 else ''
    return (
        "¿Con qué experto quiere hablar? Elija un agente en la lista.\n\n"
        "También puede escribir su pregunta y lo llevamos al agente que corresponde.\n\n"
        f"{cupo}"
        "_*reiniciar* = memoria nueva · *menu* = menú principal._"
    )


def enviar_menu_agentes(telefono_usuario: str, from_number: str) -> dict:
    from core.sandbox_agentes import _tope_asesor_mes
    from core.sandbox_canal import enviar_meta_lista, sandbox_via_meta

    if not sandbox_via_meta():
        return _menu().enviar_texto_sandbox(telefono_usuario, from_number, _menu().TEXTO_AGENTES, agente='sandbox_agentes')
    from core.lineas.oferta import filas_agentes

    filas = filas_agentes(telefono_usuario)
    if not filas:
        return _menu().enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            "En esta línea no hay agentes.\n\nEscriba *formacion* para ver los cursos.\n\n_*menu* para volver._",
            agente='sandbox_agentes',
        )
    return enviar_meta_lista(
        telefono_usuario,
        texto_lista_agentes(_tope_asesor_mes(telefono_usuario)),
        'Ver agentes',
        filas,
        texto_respaldo=_menu().TEXTO_AGENTES,
        agente_evento='sandbox_agentes',
    )


def enviar_pregunta_asesoria(telefono_usuario: str, from_number: str) -> dict:
    """«¿Qué quiere mejorar hoy?» con los temas de los agentes que la línea abre."""
    from core.lineas.oferta import modos_agente
    from core.lineas.principal.derivar_asesoria import (
        AGENTE_PREGUNTA,
        olvidar_repregunta,
        texto_pregunta,
    )
    from core.sandbox_agentes import _tope_asesor_mes

    permitidos = modos_agente(telefono_usuario)
    if not permitidos:
        return _menu().enviar_menu_agentes(telefono_usuario, from_number)
    olvidar_repregunta(telefono_usuario)
    return _menu().enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        texto_pregunta(permitidos, _tope_asesor_mes(telefono_usuario)),
        agente=AGENTE_PREGUNTA,
    )


def enviar_repregunta_asesoria(telefono_usuario: str, from_number: str) -> dict:
    from core.lineas.oferta import modos_agente
    from core.lineas.principal.derivar_asesoria import (
        AGENTE_REPREGUNTA,
        texto_repregunta,
    )

    return _menu().enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        texto_repregunta(modos_agente(telefono_usuario)),
        agente=AGENTE_REPREGUNTA,
    )


def toca_ficha(telefono_usuario: str) -> bool:
    """Después de esta respuesta sale una pregunta de la ficha: el asesor no debe cerrar preguntando."""
    from core.lineas.principal.ficha_negocio import siguiente_pregunta

    try:
        return siguiente_pregunta(telefono_usuario) is not None
    except DatabaseError:
        logger.exception('ficha_toca_fail')
        return False


def preguntar_ficha_si_toca(telefono_usuario: str, from_number: str) -> None:
    """Después de una respuesta útil del agente: una pregunta de la ficha, si toca."""
    from core.lineas.principal.ficha_negocio import AGENTE_FICHA, marcar_preguntada, siguiente_pregunta
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    try:
        pregunta = siguiente_pregunta(telefono_usuario)
        if pregunta is None:
            return
        if pregunta.botones and sandbox_via_meta():
            enviar_meta_botones(
                telefono_usuario, pregunta.mensaje, list(pregunta.botones), agente_evento=AGENTE_FICHA,
            )
        else:
            _menu().enviar_texto_sandbox(
                telefono_usuario, from_number, pregunta.mensaje_sin_botones, agente=AGENTE_FICHA,
            )
        marcar_preguntada(telefono_usuario, pregunta.campo)
    except DatabaseError:
        logger.exception('ficha_pregunta_fail')


def despues_de_nat(
    telefono_usuario: str, from_number: str, respuesta: str, *, derivado: bool, secundario: str = '',
) -> None:
    """Lo que los demás asesores mandan con su respuesta; Nat responde por el bot comercial y va aparte."""
    from core.lineas.principal.ficha_negocio import deja_pregunta_abierta, remite_a_otro_asesor

    from_n = from_number or _menu().sandbox_number()
    if derivado:
        from core.lineas.principal.derivar_asesoria import cierre_derivacion

        cierre = cierre_derivacion(secundario, ya_pregunto=deja_pregunta_abierta(respuesta))
        _menu().enviar_texto_sandbox(telefono_usuario, from_n, cierre, agente='sandbox_asesoria_cierre')
    elif not deja_pregunta_abierta(respuesta) and not remite_a_otro_asesor(respuesta):
        preguntar_ficha_si_toca(telefono_usuario, from_n)


def responder_ficha(telefono_usuario: str, from_number: str, body: str) -> str | None:
    """'handled' si el mensaje era la respuesta a una pregunta de la ficha."""
    from core.lineas.principal.ficha_negocio import AGENTE_FICHA, responder

    texto = responder(telefono_usuario, body)
    if texto is None:
        return None
    _menu().enviar_texto_sandbox(telefono_usuario, from_number, texto, agente=AGENTE_FICHA)
    return 'handled'


def _guardar_pregunta_en_memoria(telefono: str, agente: str, body: str) -> None:
    """INCOMING con la etiqueta del agente; se guarda tras responder para no duplicar la pregunta en el prompt."""
    try:
        from core.models import WhatsappLog

        from core.lineas.sesion import phone_id_sesion

        WhatsappLog.objects.create(
            telefono=telefono,
            mensaje=(body or '').strip()[:4000],
            tipo='INCOMING',
            agente_usado=f'sandbox_{agente}',
            phone_id=phone_id_sesion(),
        )
    except Exception:
        logger.exception('sandbox_memoria_incoming_fail agente=%s', agente)


def _reaccion_espera(telefono: str, message_id: str) -> None:
    try:
        from core.sandbox_canal import poner_reaccion_espera

        poner_reaccion_espera(telefono, message_id)
    except Exception:
        logger.exception('sandbox_reaccion_espera_fail')


def _manejar_agente_extra(decision: SandboxRouteDecision, body: str, message_id: str = '') -> str:
    """Coach / Profe IA: reinicio, saludo de entrada o turno LLM. Returns 'handled'."""
    from core.sandbox_agentes import responder_agente_sandbox, saludo_agente

    if decision.action == 'coach':
        agente = 'coach'
    elif decision.action == 'ventas':
        agente = 'ventas'
    elif decision.action == 'finanzas':
        agente = 'finanzas'
    elif decision.action == 'cafe':
        agente = 'cafe'
    else:
        agente = 'ia_campo'
    from_n = decision.from_number or _menu().sandbox_number()
    respuesta_util = False

    if decision.reset_nat:
        _menu().marcar_corte_memoria_nat(decision.telefono_usuario)
        texto = saludo_agente(agente, reinicio=True)  # type: ignore[arg-type]
    elif decision.saludo_entrada:
        texto = saludo_agente(agente)  # type: ignore[arg-type]
    elif decision.es_toque:
        texto = _menu().TEXTO_TOQUE_NO_PREGUNTA
    elif not (body or '').strip():
        texto = (
            f"{saludo_agente(agente)}\n\n"  # type: ignore[arg-type]
            "_Si envió un *audio* y no lo entendí, pruebe otra vez o escriba el mensaje._"
        )
    else:
        from core.planes_linea import registrar_pregunta_asesor
        from core.sandbox_agentes import (
            _tope_asesor_mes,
            excedio_cupo_ia_linea,
            respuestas_asesor_en_el_mes,
            responder_agente_sandbox,
        )

        tope = _tope_asesor_mes(decision.telefono_usuario)
        if excedio_cupo_ia_linea(decision.telefono_usuario):
            texto = _menu().texto_cupo_ia(tope)
        else:
            _menu()._reaccion_espera(decision.telefono_usuario, message_id)
            sin_pregunta = (
                not decision.derivado
                and getattr(settings, 'EKI_ASESORIA_CONTEXTO', False)
                and toca_ficha(decision.telefono_usuario)
            )
            texto = responder_agente_sandbox(
                agente, body, telefono=decision.telefono_usuario, sin_pregunta_final=sin_pregunta,  # type: ignore[arg-type]
            )
            from core.lineas.principal.ficha_negocio import deja_pregunta_abierta, remite_a_otro_asesor

            ya_pregunto = deja_pregunta_abierta(texto)
            respuesta_util = not ya_pregunto and not remite_a_otro_asesor(texto)
            registrar_pregunta_asesor(decision.telefono_usuario)
            _guardar_pregunta_en_memoria(decision.telefono_usuario, agente, body)
            try:
                from core.conocimiento_agentes import capturar_sugerencia

                capturar_sugerencia(agente, body, texto)
            except Exception:
                logger.exception('sandbox_captura_sugerencia_fail agente=%s', agente)
            if decision.derivado and getattr(settings, 'EKI_ASESORIA_CONTEXTO', False):
                from core.lineas.principal.derivar_asesoria import cierre_derivacion

                cierre = cierre_derivacion(decision.agente_secundario, ya_pregunto=ya_pregunto)
                texto = f"{texto}\n\n{cierre}"
            quedan = tope - respuestas_asesor_en_el_mes(decision.telefono_usuario)
            if quedan == 2:
                texto = f"{texto}\n\nAviso: le quedan 2 preguntas este mes."
    try:
        _menu().enviar_texto_sandbox(
            decision.telefono_usuario,
            from_n,
            texto,
            agente=f'sandbox_{agente}',
        )
    except Exception:
        logger.exception('sandbox_agente_send_failed agente=%s', agente)
    if respuesta_util and not decision.derivado and getattr(settings, 'EKI_ASESORIA_CONTEXTO', False):
        preguntar_ficha_si_toca(decision.telefono_usuario, from_n)
    return 'handled'
