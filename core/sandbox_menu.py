"""Menú sandbox: Agentes (submenú) | Cursos — línea Meta Cloud API.

No afecta WABA de cursos en Twilio ni `numero_whatsapp_nat` de orgs.
Activar/desactivar: SANDBOX_MENU_ENABLED (default True).
Transporte: SANDBOX_PROVEEDOR=meta (default).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.utils import timezone

from core.conversacion.puertas import (  # noqa: F401
    _NO_CONFIRMA_DATOS,
    _SI_CONFIRMA_DATOS,
    _aceptar_habeas_y_abrir_menu,
    _aceptar_habeas_y_pedir_cedula,
    _avisar_aula_es_twilio,
    _enviar_confirma_numero,
    _habeas_listo,
    _responder_cedula,
    _responder_confirmacion,
    _responder_habeas,
    _responder_optout,
    abrir_tras_confirmar,
    alinear_ficha_con_sesion_habeas,
    correr_puertas,
)
from core.lineas.principal.asesores import (  # noqa: F401
    FILAS_AGENTES,
    _guardar_pregunta_en_memoria,
    _manejar_agente_extra,
    _reaccion_espera,
    enviar_menu_agentes,
    texto_lista_agentes,
)
from core.lineas.principal.cursos import (  # noqa: F401
    _abiertos_del_mes,
    _entrar_en_progreso,
    _preguntar_cual_curso,
    _progresos_del_telefono,
    _sticky_cursos_solo_si_inscrito_demo,
    _tiene_curso_abierto,
    bootstrap_cursos_sandbox,
    entrar_cursos_inscrito,
    ofrecer_cursos_en_curso,
)
from core.lineas.principal.menu import (  # noqa: F401
    enviar_catalogo_formacion,
    enviar_menu_sandbox,
    responder_catalogo_general,
)
from core.nati import normalizar_telefono_whatsapp
from core.planes_linea import (
    PLAN_CURSO_ASESOR,
    TEXTO_PLAN_SIN_ASESOR,
    TEXTO_PLAN_SIN_CURSOS,
    TEXTO_SIN_PLAN,
    plan_por_clave,
    resolver_plan,
    texto_menu_plan,
)

logger = logging.getLogger(__name__)

MODO_MENU = 'menu'
MODO_AGENTES = 'agentes'
MODO_NAT = 'nat'
MODO_COACH = 'coach'
MODO_IA_CAMPO = 'ia_campo'
MODO_VENTAS = 'ventas'
MODO_FINANZAS = 'finanzas'
MODO_CAFE = 'cafe'
MODO_CURSOS = 'cursos'
MODO_FORMACION = 'formacion'
MODO_ASESORIA = 'asesoria'

MODOS_AGENTE = (MODO_NAT, MODO_COACH, MODO_IA_CAMPO, MODO_VENTAS, MODO_FINANZAS, MODO_CAFE)
_ACCIONES_ASESOR = frozenset({
    'show_agentes', 'show_asesoria', 'nat', 'coach', 'ia_campo', 'ventas', 'finanzas', 'cafe',
})

TEXTO_MENU = texto_menu_plan(plan_por_clave(PLAN_CURSO_ASESOR))

TEXTO_FORMACION = (
    "¿Qué le gustaría aprender para tomar mejores decisiones?\n\n"
    "Escríbalo en un mensaje. Si ya está inscrito en un curso eki, "
    "seguimos ese curso en esta misma línea, sin reiniciar el avance.\n\n"
    "_*menu* para volver._"
)

def texto_asesoria(tope: int) -> str:
    return (
        "Si usted tuviera la oportunidad de preguntarle a un experto sobre cómo "
        "mejorar su productividad, la de su negocio, o quiere tomar mejores "
        "decisiones, ¿qué preguntaría?\n\n"
        "Escríbala y lo llevamos al agente que corresponde. "
        f"Tiene hasta {tope} preguntas este mes.\n\n"
        "_*menu* para volver._"
    )


TEXTO_ASESORIA = texto_asesoria(60)

TEXTO_CURSO_NO_INSCRITO = (
    "Esta línea no abre cursos nuevos.\n\n"
    "Si su organización ya lo inscribió en eki, escriba *2* desde el WhatsApp "
    "registrado. Si aún no está en un curso, pida a su coordinador que lo inscriba "
    "en el admin.\n\n"
    "_*menu* para volver._"
)

def texto_cupo_ia(tope: int) -> str:
    if tope <= 0:
        return TEXTO_PLAN_SIN_ASESOR
    return (
        f"Este mes ya usó las {tope} preguntas del asesor.\n\n"
        "Puede seguir su curso de formación, o escribir *menu*. "
        "El cupo se reinicia el próximo mes."
    )


TEXTO_CUPO_IA = texto_cupo_ia(60)

TEXTO_TOQUE_NO_PREGUNTA = (
    "Escriba su pregunta con sus palabras. "
    "Un botón no cuenta como pregunta.\n\n"
    "_*menu* para volver._"
)


def _es_toque(payload: Any) -> bool:
    """True si el mensaje es un botón o una lista, no un texto escrito."""
    if not isinstance(payload, dict):
        return False
    tipo = str(payload.get('_eki_tipo') or '').strip().lower()
    if tipo in ('interactive', 'button'):
        return True
    for clave in ('ButtonPayload', 'ButtonText', 'ListId', 'ListTitle'):
        if str(payload.get(clave) or '').strip():
            return True
    return False

TEXTO_AGENTES = (
    "🤖 *Asesoría*\n\n"
    "1️⃣ *Agrónomo* — Experto en café\n"
    "2️⃣ *Coach* — Motivación y metas diarias\n"
    "3️⃣ *Innovación e IA* — Mejor apropiación tecnológica\n"
    "4️⃣ *Ventas* — Aumenta tus ingresos\n"
    "5️⃣ *Finanzas* — Educación financiera a tu alcance\n\n"
    "Escribe *1*, *2*, *3*, *4* o *5*.\n"
    "*reiniciar* = memoria nueva · *menu* = menú principal."
)

# Quick reply de la campaña o de las plantillas de bienvenida.
_BOTONES_INICIO_PLANTILLA = frozenset({'iniciar', 'empezar', 'listo'})

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
    # show_menu | show_agentes | nat | coach | ia_campo | ventas | cursos | cursos_bootstrap
    from_number: str = ''
    telefono_usuario: str = ''
    texto_menu: str = TEXTO_MENU
    reset_nat: bool = False  # True = comando *reiniciar* (corte de memoria)
    saludo_entrada: bool = False  # Entró por menú; no pasar "1"/"2" al LLM
    es_toque: bool = False  # Botón o lista: no es una pregunta escrita


def sandbox_menu_enabled() -> bool:
    return bool(getattr(settings, 'SANDBOX_MENU_ENABLED', True))


def sandbox_number() -> str:
    return normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_SANDBOX_NUMBER', '14155238886') or '14155238886'
    )


def es_destino_sandbox(to_or_payload: Any) -> bool:
    from core.sandbox_canal import (
        es_inbound_twilio_http,
        inbound_es_meta,
        phone_id_es_sandbox,
        sandbox_via_meta,
        to_es_sandbox,
    )

    if not sandbox_menu_enabled():
        return False
    if sandbox_via_meta() and inbound_es_meta(to_or_payload):
        return True
    if phone_id_es_sandbox(to_or_payload):
        return True
    if not to_es_sandbox(to_or_payload):
        return False
    if sandbox_via_meta() and es_inbound_twilio_http(to_or_payload):
        return False
    return True


def _extract_from_body(payload: Any) -> tuple[str, str, str]:
    if isinstance(payload, str) or payload is None:
        return '', '', ''
    try:
        from_raw = payload.get('From', '')  # type: ignore[union-attr]
        to_raw = payload.get('To', '')  # type: ignore[union-attr]
        body = (payload.get('Body', '') or '').strip()  # type: ignore[union-attr]
    except Exception:
        return '', '', ''
    if not body:
        try:
            from core.habeas_respuestas import texto_desde_webhook_twilio

            body = (texto_desde_webhook_twilio(payload, '') or '').strip()
        except Exception:
            body = ''
    return (
        normalizar_telefono_whatsapp(from_raw),
        normalizar_telefono_whatsapp(to_raw),
        body,
    )


def _es_boton_inicio_flujo(body: str) -> bool:
    """Listo / Iniciar / Empezar, o el mismo botón citado debajo del texto de la plantilla."""
    t = (body or '').strip().lower()
    if not t:
        return False
    if t in _BOTONES_INICIO_PLANTILLA:
        return True
    return t.splitlines()[-1].strip() in _BOTONES_INICIO_PLANTILLA


def _body_o_audio_transcrito(payload: Any, body: str) -> str:
    """Si Body vacío y hay audio, transcribe (Coach/Profe/comandos)."""
    if (body or '').strip():
        return body
    if payload is None or isinstance(payload, str):
        return body
    try:
        num_media = int(payload.get('NumMedia', 0) or 0)  # type: ignore[union-attr]
    except (TypeError, ValueError):
        num_media = 0
    if num_media < 1:
        return body
    try:
        media_url = (payload.get('MediaUrl0') or '').strip()  # type: ignore[union-attr]
        media_type = (payload.get('MediaContentType0') or '').strip()  # type: ignore[union-attr]
    except Exception:
        return body
    if not media_url:
        return body
    mt = media_type.lower()
    if mt and not any(x in mt for x in ('audio', 'ogg', 'opus', 'mpeg', 'mp4', 'amr', 'wav')):
        return body
    try:
        from core.sandbox_canal import inbound_es_meta, transcribir_audio_meta

        if inbound_es_meta(payload) or not media_url.startswith(('http://', 'https://')):
            texto = (transcribir_audio_meta(media_url, media_type or 'audio/ogg') or '').strip()
        else:
            from core.views import _transcribir_audio_twilio

            texto = (_transcribir_audio_twilio(media_url, media_type=media_type or 'audio/ogg') or '').strip()
        if texto:
            logger.info('sandbox_audio_transcrito chars=%s', len(texto))
            return texto
    except Exception:
        logger.exception('sandbox_audio_transcribe_fail')
    return body


def _get_or_create_sesion(telefono: str):
    from core.lineas.sesion import sesion_de

    return sesion_de(telefono)


def _set_modo(sesion, modo: str, *, reset_nat: bool = False) -> None:
    sesion.modo = modo
    fields = ['modo', 'actualizado_en']
    if reset_nat:
        sesion.memoria_corte_en = timezone.now()
        fields.append('memoria_corte_en')
    sesion.save(update_fields=fields)


def clasificar_asesoria(texto: str) -> str | None:
    """Lleva la pregunta libre al agente. None si no alcanza para decidir."""
    t = (texto or '').strip().lower()
    if not t or t in ('1', '2', '3', '4', '5', '6'):
        return None
    if any(w in t for w in (
        'finanza', 'gasto', 'deuda', 'préstamo', 'prestamo', 'crédito', 'credito',
        'ahorro', 'presupuesto', 'utilidad',
    )):
        return MODO_FINANZAS
    if any(w in t for w in ('venta', 'precio', 'cliente', 'cerrar', 'comercial', 'negocio')):
        return MODO_VENTAS
    if any(w in t for w in ('café', 'cafe', 'cafetal', 'cafeto', 'caficult', 'broca', 'cenicaf')):
        return MODO_NAT
    if any(w in t for w in (
        'plaga', 'cultivo', 'suelo', 'cosecha', 'fertil', 'finca', 'agron',
    )):
        return MODO_NAT
    if any(w in t for w in ('hábit', 'habit', 'motiv', 'constancia', 'ánimo', 'animo')):
        return MODO_COACH
    if any(w in t for w in (
        'inteligencia artificial', 'chatgpt', 'tecnolog', 'whatsapp', 'profe',
    )):
        return MODO_IA_CAMPO
    return None


def _normalizar_eleccion_raiz(body: str) -> str | None:
    t = (body or '').strip().lower()
    if t in ('menu', 'menú', 'inicio', 'start'):
        return 'menu'
    if t in ('hola', 'hi', 'hey', 'buenas', 'buen día', 'buenos días'):
        return 'saludo'
    if t in ('1', '1️⃣', 'uno', 'formacion', 'formación', 'aprender'):
        return MODO_FORMACION
    if t in ('2', '2️⃣', 'dos', 'asesoria', 'asesoría', 'asesor'):
        return MODO_ASESORIA
    if t in ('agentes', 'agente ia', 'agentes ia'):
        return MODO_AGENTES
    if t in ('seguir', 'seguir_curso'):
        return 'seguir'
    if t in ('curso', 'cursos', 'edu', 'riendas'):
        return MODO_CURSOS
    # Compat: atajos directos
    if t in ('nat', 'nati', 'agronomo', 'agrónomo'):
        return MODO_NAT
    if t in ('coach', 'entrenador'):
        return MODO_COACH
    if t in ('profe', 'profe ia', 'ia campo', 'ia_campo', 'innovacion', 'innovación', 'innovacion e ia', 'innovación e ia'):
        return MODO_IA_CAMPO
    if t in ('ventas', 'venta', 'comercial', 'comercializacion', 'comercialización'):
        return MODO_VENTAS
    if t in ('finanzas', 'finanza', 'experto en finanzas'):
        return MODO_FINANZAS
    if t in ('cafe', 'café', 'experto en cafe', 'experto en café'):
        return MODO_NAT
    return None


def _normalizar_eleccion_agentes(body: str) -> str | None:
    t = (body or '').strip().lower()
    if t in ('menu', 'menú', 'inicio', 'atras', 'atrás', 'volver'):
        return 'menu'
    if t in ('1', '1️⃣', 'uno', 'nat', 'nati', 'agronomo', 'agrónomo'):
        return MODO_NAT
    if t in ('2', '2️⃣', 'dos', 'coach', 'entrenador'):
        return MODO_COACH
    if t in ('3', '3️⃣', 'tres', 'profe', 'profe ia', 'ia', 'ia campo', 'innovacion', 'innovación', 'innovacion e ia', 'innovación e ia'):
        return MODO_IA_CAMPO
    if t in ('4', '4️⃣', 'cuatro', 'ventas', 'venta', 'comercial', 'comercializacion', 'comercialización'):
        return MODO_VENTAS
    if t in ('5', '5️⃣', 'cinco', 'finanzas', 'finanza', 'experto en finanzas'):
        return MODO_FINANZAS
    if t in ('6', '6️⃣', 'seis', 'cafe', 'café', 'experto en cafe', 'experto en café'):
        return MODO_NAT
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
    if not telefono:
        return None
    from core.lineas.sesion import sesion_de

    try:
        return sesion_de(telefono).memoria_corte_en
    except ValueError:
        return None


def resolver_ruta_sandbox(payload: Any) -> SandboxRouteDecision:
    from_tel, to_tel, body = _extract_from_body(payload)
    body = _body_o_audio_transcrito(payload, body)
    decision = SandboxRouteDecision(
        action='show_menu',
        from_number=to_tel or sandbox_number(),
        telefono_usuario=from_tel,
        es_toque=_es_toque(payload),
    )
    if not from_tel:
        return decision

    sesion = _get_or_create_sesion(from_tel)

    # *hola* / *menu* siempre vuelven al menú (evita atascarse en cursos/agentes)
    t_low = (body or '').strip().lower()
    if t_low in ('menu', 'menú', 'inicio', 'start', 'hola', 'hi', 'hey', 'buenas', 'buen día', 'buenos días'):
        _set_modo(sesion, MODO_MENU)
        decision.action = 'show_menu'
        return decision

    # Plantilla inicial: habeas ya se cortó arriba. Aquí no abrir "sin curso".
    if _es_boton_inicio_flujo(body):
        from core.utils_telefono import estudiante_por_telefono

        persona = estudiante_por_telefono(from_tel)
        estado = getattr(persona, 'estado_chat', '') if persona is not None else ''
        if estado == 'ESPERANDO_CEDULA':
            _set_modo(sesion, MODO_CURSOS)
            decision.action = 'pedir_cedula'
            return decision
        if estado == 'CONFIRMANDO_DATOS':
            _set_modo(sesion, MODO_CURSOS)
            decision.action = 'confirmar_datos'
            return decision
        if estado == 'ESPERANDO_HABEAS_DATA' or (
            persona is not None and not persona.acepto_terminos
        ):
            decision.action = 'pedir_habeas'
            return decision
        t_btn = (body or '').strip().lower().splitlines()[-1].strip()
        if t_btn == 'listo' and sesion.modo == MODO_CURSOS:
            pass
        else:
            _set_modo(sesion, MODO_MENU)
            decision.action = 'show_menu'
            return decision

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
        if eleccion_ag == MODO_VENTAS:
            _set_modo(sesion, MODO_VENTAS)
            decision.action = 'ventas'
            decision.saludo_entrada = True
            return decision
        if eleccion_ag == MODO_FINANZAS:
            _set_modo(sesion, MODO_FINANZAS)
            decision.action = 'finanzas'
            decision.saludo_entrada = True
            return decision
        if eleccion_ag == MODO_CAFE:
            _set_modo(sesion, MODO_CAFE)
            decision.action = 'cafe'
            decision.saludo_entrada = True
            return decision
        # Texto libre en submenú → re-mostrar opciones
        decision.action = 'show_agentes'
        return decision

    if sesion.modo == MODO_ASESORIA:
        eleccion_ag = _normalizar_eleccion_agentes(body)
        if eleccion_ag == 'menu':
            _set_modo(sesion, MODO_MENU)
            decision.action = 'show_menu'
            return decision
        agente = eleccion_ag or clasificar_asesoria(body)
        if agente:
            _set_modo(sesion, agente)
            decision.action = agente
            decision.saludo_entrada = True
            return decision
        _set_modo(sesion, MODO_AGENTES)
        decision.action = 'show_agentes'
        return decision

    import re

    from core.cursos_generales import payload_catalogo

    seguido = re.fullmatch(r'seguir_(\d+)', (body or '').strip())
    if seguido:
        curso_id = int(seguido.group(1))
        if any(p.curso_id == curso_id for p in _abiertos_del_mes(from_tel)):
            decision.action = 'continuar_curso'
            decision.texto_menu = str(curso_id)
            return decision

    if sesion.modo in (MODO_MENU, MODO_FORMACION, MODO_CURSOS) and payload_catalogo(body):
        decision.action = 'catalogo_general'
        decision.texto_menu = (body or '').strip()
        return decision

    if (body or '').strip().lower() in ('continuemos', 'continuar'):
        from core.utils_telefono import estudiante_por_telefono

        persona = estudiante_por_telefono(from_tel)
        if persona is not None and persona.estado_chat in (
            'ESPERANDO_CEDULA', 'CONFIRMANDO_DATOS',
        ):
            decision.action = 'cursos'
            return decision
        if _abiertos_del_mes(from_tel):
            _set_modo(sesion, MODO_CURSOS)
            decision.action = 'cursos'
            return decision

    if sesion.modo == MODO_FORMACION and (body or '').strip():
        abiertos = _abiertos_del_mes(from_tel)
        numero = (body or '').strip()
        if len(abiertos) >= 2 and numero.isdigit() and 1 <= int(numero) <= len(abiertos):
            decision.action = 'continuar_curso'
            decision.texto_menu = str(abiertos[int(numero) - 1].curso_id)
            return decision
        decision.action = 'cursos_bootstrap'
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

    if eleccion == MODO_VENTAS:
        _set_modo(sesion, MODO_VENTAS)
        decision.action = 'ventas'
        decision.saludo_entrada = True
        return decision

    if eleccion == MODO_FINANZAS:
        _set_modo(sesion, MODO_FINANZAS)
        decision.action = 'finanzas'
        decision.saludo_entrada = True
        return decision

    if eleccion == MODO_CAFE:
        _set_modo(sesion, MODO_CAFE)
        decision.action = 'cafe'
        decision.saludo_entrada = True
        return decision

    if eleccion == 'seguir':
        decision.action = 'seguir_curso'
        return decision

    if eleccion == MODO_FORMACION:
        _set_modo(sesion, MODO_FORMACION)
        decision.action = 'show_formacion'
        return decision

    if eleccion == MODO_ASESORIA:
        _set_modo(sesion, MODO_ASESORIA)
        decision.action = 'show_asesoria'
        return decision

    if eleccion == MODO_CURSOS:
        # Modo cursos solo si entrar_cursos_inscrito confirma progreso.
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

    if sesion.modo == MODO_VENTAS:
        decision.action = 'ventas'
        return decision

    if sesion.modo == MODO_FINANZAS:
        decision.action = 'finanzas'
        return decision

    if sesion.modo == MODO_CAFE:
        decision.action = 'cafe'
        return decision

    if sesion.modo == MODO_CURSOS:
        decision.action = 'cursos'
        return decision

    decision.action = 'show_menu'
    return decision


def enviar_texto_sandbox(telefono_usuario: str, from_number: str, texto: str, *, agente: str = 'sandbox_menu') -> dict:
    from core.sandbox_canal import enviar_sandbox

    return enviar_sandbox(
        telefono_usuario,
        texto,
        from_number=from_number,
        canal_evento='whatsapp_sandbox',
        agente_evento=agente,
    )


def _message_id(payload: Any) -> str:
    try:
        return str(payload.get('MessageSid') or '')
    except Exception:
        return ''


def dispatch_sandbox_menu(payload: Any) -> str | None:
    """
    Intercepta el sandbox (Meta) cuando SANDBOX_MENU_ENABLED.

    Returns:
      None — no aplica
      'handled' — respuesta enviada
      'nat' — enrutar a Nat
      'cursos' — enrutar a edu
    """
    if not es_destino_sandbox(payload):
        return None
    from_tel, _, body_habeas = _extract_from_body(payload)
    body_habeas = _body_o_audio_transcrito(payload, body_habeas)
    if from_tel:
        if correr_puertas(from_tel, body_habeas) == 'handled':
            return 'handled'
        try:
            from core.rachas_linea import registrar_actividad_linea

            registrar_actividad_linea(from_tel)
        except Exception:
            logger.exception('sandbox_racha_fail tel=%s', from_tel)
    decision = resolver_ruta_sandbox(payload)
    from_n = decision.from_number or sandbox_number()
    _, _, body = _extract_from_body(payload)
    body = _body_o_audio_transcrito(payload, body)

    from core.lineas.variante import TEXTO_LINEA_MODO_TWILIO, perfil_de

    if perfil_de().curso_directo:
        # Modo Twilio: sin carrusel ni agentes. Todo el cuerpo va al curso.
        if decision.action in _ACCIONES_ASESOR or decision.action in (
            'nat', 'coach', 'ia_campo', 'ventas', 'finanzas', 'cafe',
        ):
            _set_modo(_get_or_create_sesion(decision.telefono_usuario), MODO_MENU)
            try:
                enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    TEXTO_LINEA_MODO_TWILIO,
                    agente='sandbox_cursos',
                )
            except Exception:
                logger.exception('sandbox_linea_twilio_fail tel=%s', decision.telefono_usuario)
            return 'handled'
        return 'cursos'

    if decision.action in ('nat', 'coach', 'ia_campo', 'ventas', 'finanzas', 'cafe'):
        from core.lineas.oferta import agente_permitido

        if not agente_permitido(decision.telefono_usuario, decision.action):
            _set_modo(_get_or_create_sesion(decision.telefono_usuario), MODO_MENU)
            try:
                enviar_menu_agentes(decision.telefono_usuario, from_n)
            except Exception:
                logger.exception('sandbox_agente_no_permitido tel=%s', decision.telefono_usuario)
            return 'handled'

    if (
        decision.action in _ACCIONES_ASESOR or decision.action == 'show_formacion'
    ):
        plan = resolver_plan(decision.telefono_usuario)
        bloqueo = ''
        if not plan.activo:
            bloqueo = TEXTO_SIN_PLAN
        elif decision.action == 'show_formacion' and not plan.incluye_cursos:
            bloqueo = TEXTO_PLAN_SIN_CURSOS
        elif decision.action in _ACCIONES_ASESOR and not plan.incluye_asesor:
            bloqueo = TEXTO_PLAN_SIN_ASESOR
        if bloqueo:
            _set_modo(_get_or_create_sesion(decision.telefono_usuario), MODO_MENU)
            try:
                enviar_texto_sandbox(decision.telefono_usuario, from_n, bloqueo, agente='sandbox_plan')
            except Exception:
                logger.exception('sandbox_plan_send_failed tel=%s', decision.telefono_usuario)
            return 'handled'

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
            enviar_texto_sandbox(
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
                _enviar_confirma_numero(decision.telefono_usuario, from_n, est)
            except Exception:
                logger.exception('sandbox_confirmar_datos_fail tel=%s', decision.telefono_usuario)
        return 'handled'

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

    if decision.action == 'continuar_curso':
        try:
            curso_id = int(decision.texto_menu)
            progreso = next(p for p in _abiertos_del_mes(decision.telefono_usuario) if p.curso_id == curso_id)
            _entrar_en_progreso(decision.telefono_usuario, from_n, progreso)
        except StopIteration:
            enviar_menu_sandbox(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_continuar_curso_fail')
        return 'handled'

    if decision.action == 'seguir_curso':
        try:
            entrar_cursos_inscrito(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_seguir_curso_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'show_formacion':
        try:
            enviar_catalogo_formacion(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_formacion_send_failed')
        return 'handled'

    if decision.action == 'catalogo_general':
        try:
            responder_catalogo_general(decision.telefono_usuario, from_n, decision.texto_menu)
        except Exception:
            logger.exception('sandbox_catalogo_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'show_asesoria':
        try:
            enviar_menu_agentes(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_asesoria_send_failed')
        return 'handled'

    if decision.action == 'nat':
        if decision.reset_nat:
            marcar_corte_memoria_nat(decision.telefono_usuario)
            try:
                from core.sandbox_agentes import presentacion_agente

                enviar_texto_sandbox(
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

                enviar_texto_sandbox(
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
                enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    TEXTO_TOQUE_NO_PREGUNTA,
                    agente='sandbox_plan',
                )
            except Exception:
                logger.exception('sandbox_nat_toque_fail')
            return 'handled'
        if excedio_cupo_ia_linea(decision.telefono_usuario):
            try:
                enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    texto_cupo_ia(_tope_asesor_mes(decision.telefono_usuario)),
                    agente='sandbox_plan',
                )
            except Exception:
                logger.exception('sandbox_nat_cupo_fail')
            return 'handled'
        registrar_pregunta_asesor(decision.telefono_usuario)
        _reaccion_espera(decision.telefono_usuario, _message_id(payload))
        return 'nat'

    if decision.action in ('coach', 'ia_campo', 'ventas', 'finanzas', 'cafe'):
        return _manejar_agente_extra(decision, body, _message_id(payload))

    if decision.action == 'cursos_bootstrap':
        try:
            bootstrap_cursos_sandbox(decision.telefono_usuario, from_n)
        except Exception:
            logger.exception('sandbox_cursos_bootstrap_fail tel=%s', decision.telefono_usuario)
        return 'handled'

    if decision.action == 'cursos':
        _reaccion_espera(decision.telefono_usuario, _message_id(payload))
        return 'cursos'

    try:
        enviar_menu_sandbox(decision.telefono_usuario, from_n)
    except Exception:
        logger.exception('sandbox_menu_send_failed tel=%s', decision.telefono_usuario)
    return 'handled'
