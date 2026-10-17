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
_SI_CONFIRMA_DATOS = frozenset({
    'si', 'sí', 'todo bien', 'correcto', 'ok', 'yes', 'confirmo', 'confirmar',
})
_NO_CONFIRMA_DATOS = frozenset({
    'no', 'modificar', 'error', 'mal', 'incorrecto', 'cambiar',
})

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


def _abiertos_del_mes(telefono: str):
    from core.planes_linea import cursos_iniciados_en_el_mes

    return list(
        cursos_iniciados_en_el_mes(telefono).filter(completado=False).select_related('estudiante', 'curso')[:6]
    )


def _entrar_en_progreso(telefono: str, from_number: str, progreso) -> None:
    est = progreso.estudiante
    ctx = dict(est.contexto_temporal or {})
    ctx['curso_activo_id'] = progreso.curso_id
    est.contexto_temporal = ctx
    est.save(update_fields=['contexto_temporal'])
    _set_modo(_get_or_create_sesion(telefono), MODO_CURSOS)
    from core.lineas.variante import es_solo_cursos

    extra = ''
    if not es_solo_cursos() and resolver_plan(telefono).incluye_asesor:
        extra = "\nEscriba *asesoria* si quiere hablar con el asesor.\n"
    enviar_texto_sandbox(
        telefono,
        from_number,
        f"Seguimos *{progreso.curso.nombre}*.\n\n"
        "Pulse continuar, para seguir aprendiendo. No se reinicia su avance.\n"
        f"{extra}\n_*menu* para volver._\n\n[SEND_BUTTON:continuemos]",
        agente='sandbox_cursos',
    )


def _preguntar_cual_curso(telefono: str, from_number: str, abiertos) -> None:
    from core.sandbox_canal import enviar_meta_lista, sandbox_via_meta

    _set_modo(_get_or_create_sesion(telefono), MODO_FORMACION)
    lineas = [f"{i}. {p.curso.nombre}" for i, p in enumerate(abiertos, start=1)]
    texto = (
        "¿Cuál curso sigue?\n\n"
        + "\n".join(lineas)
        + "\n\nElija en la lista o escriba el número. No se reinicia su avance.\n\n"
        "_*menu* para volver._"
    )
    filas = [
        (f"seguir_{p.curso_id}", (p.curso.nombre or 'Curso')[:24], 'Continuar donde iba')
        for p in abiertos[:10]
    ]
    if sandbox_via_meta():
        enviar_meta_lista(
            telefono, texto, 'Sus cursos', filas, texto_respaldo=texto, agente_evento='sandbox_cursos'
        )
        return
    enviar_texto_sandbox(telefono, from_number, texto, agente='sandbox_cursos')


def ofrecer_cursos_en_curso(telefono: str, from_number: str) -> bool:
    """Si este mes ya va en uno o dos cursos, no abre el carrusel de cero."""
    abiertos = _abiertos_del_mes(telefono)
    if not abiertos:
        return False
    if len(abiertos) == 1:
        _entrar_en_progreso(telefono, from_number, abiertos[0])
    else:
        _preguntar_cual_curso(telefono, from_number, abiertos)
    return True


def enviar_menu_sandbox(telefono_usuario: str, from_number: str) -> dict:
    from core.lineas.variante import TEXTO_LINEA_MODO_TWILIO, es_modo_twilio
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    if es_modo_twilio():
        # Sin carrusel ni menú Meta: el curso sigue en el camino lineal.
        return enviar_texto_sandbox(
            telefono_usuario, from_number, TEXTO_LINEA_MODO_TWILIO, agente='sandbox_cursos',
        )
    plan = resolver_plan(telefono_usuario)
    if not plan.activo:
        return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_SIN_PLAN, agente='sandbox_plan')
    botones = []
    if plan.incluye_cursos:
        botones.append(('formacion', 'Formación'))
    if plan.incluye_asesor:
        from core.lineas.oferta import filas_agentes

        if filas_agentes(telefono_usuario):
            botones.append(('asesoria', 'Asesoría'))
    if not plan.incluye_cursos and _tiene_curso_abierto(telefono_usuario):
        botones.append(('seguir', 'Seguir mi curso'))
    texto = texto_menu_plan(plan)
    if sandbox_via_meta():
        return enviar_meta_botones(
            telefono_usuario,
            texto,
            botones,
            agente_evento='sandbox_menu',
        )
    palabras = ' o '.join(f"*{titulo.lower()}*" for _, titulo in botones)
    return enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        f"{texto}\n\nEscriba {palabras}.",
    )


def enviar_catalogo_formacion(telefono_usuario: str, from_number: str) -> None:
    """De 2 a 10 cursos: carrusel. Más de 10: lista. Ver curso inscribe."""
    from core.cursos_generales import (
        filas_de_tarjetas,
        modo_catalogo,
        paginas_carrusel,
        paginas_lista,
        tarjetas_catalogo,
    )
    from core.sandbox_canal import (
        enviar_meta_botones,
        enviar_meta_carrusel,
        enviar_meta_lista,
        sandbox_via_meta,
    )

    tarjetas = tarjetas_catalogo(telefono_usuario)
    cuerpo = (
        "Deslice los cursos de eki. "
        "*Más información* abre la página del programa."
    )
    if not tarjetas:
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            "Aún no hay cursos de formación publicados.\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if sandbox_via_meta() and modo_catalogo(len(tarjetas)) == 'lista':
        aviso = "Elija el curso en la lista."
        for i, pagina in enumerate(paginas_lista(filas_de_tarjetas(tarjetas))):
            intro = aviso if i == 0 else "Siguen más cursos."
            enviar_meta_lista(
                telefono_usuario,
                intro,
                'Ver cursos',
                pagina,
                texto_respaldo=intro,
                agente_evento='sandbox_formacion',
            )
        return
    if sandbox_via_meta() and len(tarjetas) >= 2:
        fallo = None
        for i, pagina in enumerate(paginas_carrusel(tarjetas)):
            intro = cuerpo if i == 0 else "Siguen más cursos. Deslice."
            resultado = enviar_meta_carrusel(
                telefono_usuario,
                intro,
                pagina,
                agente_evento='sandbox_formacion',
            )
            if not resultado.get('success'):
                fallo = resultado.get('response')
                break
        if fallo is None:
            return
        logger.warning('sandbox_carrusel_fallback %s', fallo)
    if sandbox_via_meta() and len(tarjetas) == 1:
        tarjeta = tarjetas[0]
        enviar_meta_botones(
            telefono_usuario,
            tarjeta['body'],
            tarjeta['botones'],
            agente_evento='sandbox_formacion',
        )
        return
    lineas = [cuerpo, '']
    for tarjeta in tarjetas:
        ver = tarjeta['botones'][0][0]
        lineas.append(f"{tarjeta['body']}\nEscriba {ver} para empezar.")
    enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        '\n\n'.join(lineas),
        agente='sandbox_formacion',
    )


def responder_catalogo_general(telefono_usuario: str, from_number: str, body: str) -> None:
    from core.cursos_generales import inscribir_en_catalogo, item_catalogo, payload_catalogo

    dato = payload_catalogo(body) or {}
    item = item_catalogo(dato.get('clave') or '')
    if item is None:
        from core.cursos_generales import resolver_curso_menu

        curso_linea = resolver_curso_menu(dato.get('clave') or '', telefono_usuario)
        if curso_linea is not None:
            item = {
                'clave': dato.get('clave') or '',
                'nombre': curso_linea.nombre,
                'url': '',
            }
    if item is None:
        enviar_catalogo_formacion(telefono_usuario, from_number)
        return
    if dato.get('accion') == 'info':
        from core.cursos_generales import _url_de_curso
        from core.sandbox_canal import enviar_meta_url, sandbox_via_meta

        destino = str(item.get('url') or '') or _url_de_curso(item.get('nombre') or '')
        if sandbox_via_meta() and destino.startswith('https://'):
            enviar_meta_url(
                telefono_usuario,
                item['nombre'],
                destino,
                boton='Más información',
                agente_evento='sandbox_formacion',
            )
            return
        if destino.startswith('https://'):
            enviar_texto_sandbox(
                telefono_usuario,
                from_number,
                destino,
                agente='sandbox_formacion',
            )
            return
        logger.warning('sandbox_formacion_sin_url clave=%s nombre=%s', item.get('clave'), item.get('nombre'))
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            (item.get('nombre') or 'Este programa') + '.\n\n_*menu* para volver._',
            agente='sandbox_formacion',
        )
        return
    resultado = inscribir_en_catalogo(telefono_usuario, item['clave'])
    if resultado.get('error') == 'otra_empresa':
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"*{resultado.get('nombre') or 'Ese curso'}* no está en esta línea.\n\n"
            "Escriba *formacion* para ver los cursos de su empresa.\n\n"
            "_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if resultado.get('error') == 'sin_plan_cursos':
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            TEXTO_PLAN_SIN_CURSOS if resolver_plan(telefono_usuario).activo else TEXTO_SIN_PLAN,
            agente='sandbox_plan',
        )
        return
    if resultado.get('error') == 'cupo_mes':
        cupo = resultado.get('cursos_mes') or 1
        cuantos = 'uno por mes' if cupo == 1 else f'{cupo} por mes'
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"Este mes ya eligió *{resultado.get('nombre_activo') or 'un curso'}*.\n\n"
            f"Su plan incluye cursos {cuantos} (de eki o de su organización). "
            "El próximo mes puede escoger otro.\n\n"
            "Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]\n\n"
            "_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if not resultado.get('ok'):
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"*{item['nombre']}* todavía no está publicado en esta línea.\n\n"
            f"Puede ver la ficha:\n{item['url']}\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    sesion = _get_or_create_sesion(telefono_usuario)
    _set_modo(sesion, MODO_CURSOS)
    enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        f"Quedó en *{resultado['nombre']}*.\n\n"
        "Pulse continuar, para seguir aprendiendo. No se borra el avance de sus otros cursos.\n\n[SEND_BUTTON:continuemos]\n\n"
        "_*menu* para volver._",
        agente='sandbox_formacion',
    )


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
        return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_AGENTES, agente='sandbox_agentes')
    from core.lineas.oferta import filas_agentes

    filas = filas_agentes(telefono_usuario)
    if not filas:
        return enviar_texto_sandbox(
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
        texto_respaldo=TEXTO_AGENTES,
        agente_evento='sandbox_agentes',
    )


def _tiene_curso_abierto(telefono: str) -> bool:
    """Curso ya empezado y sin completar. No abre el catálogo."""
    _est, progresos = _progresos_del_telefono(telefono)
    return any(not p.completado for p in progresos)


def _progresos_del_telefono(telefono: str):
    from core.models import Estudiante, ProgresoEstudiante

    tel = normalizar_telefono_whatsapp(telefono)
    est = Estudiante.objects.filter(telefono=tel).first()
    if est is None:
        return None, []
    progresos = list(
        ProgresoEstudiante.objects.filter(estudiante=est, curso__activo=True)
        .select_related('curso')
        .order_by('curso__orden', 'curso__nombre', 'id')
    )
    return est, progresos


def entrar_cursos_inscrito(telefono_usuario: str, from_number: str) -> bool:
    """Continúa cursos ya inscritos. No abre demo Riendas ni crea estudiantes."""
    from core.sandbox_canal import canal_sandbox_si_meta

    est, progresos = _progresos_del_telefono(telefono_usuario)
    abiertos = [p for p in progresos if not p.completado]
    sesion = _get_or_create_sesion(telefono_usuario)

    if not progresos:
        _set_modo(sesion, MODO_MENU)
        with canal_sandbox_si_meta():
            enviar_menu_sandbox(telefono_usuario, from_number)
        return True

    if not abiertos:
        _set_modo(sesion, MODO_MENU)
        nombres = ', '.join((p.curso.nombre or 'Curso')[:60] for p in progresos[:4])
        with canal_sandbox_si_meta():
            enviar_texto_sandbox(
                telefono_usuario,
                from_number,
                f"Ya completó su curso en eki ({nombres}).\n\n"
                "Si necesita reactivar avance, pida a su coordinador.\n\n"
                "_*menu* para volver._",
                agente='sandbox_cursos',
            )
        return True

    _set_modo(sesion, MODO_CURSOS)
    if len(abiertos) == 1:
        p = abiertos[0]
        ctx = dict(est.contexto_temporal or {})
        ctx['curso_activo_id'] = p.curso_id
        est.contexto_temporal = ctx
        est.save(update_fields=['contexto_temporal'])
        texto = (
            f"Seguimos *{p.curso.nombre}*.\n\n"
            "Pulse continuar, para seguir aprendiendo. "
            "No se reinicia su avance.\n\n"
            "_*menu* para volver._"
        )
    else:
        lineas = []
        for i, p in enumerate(abiertos[:6], start=1):
            lineas.append(f"{i}. {p.curso.nombre}")
        texto = (
            "Tiene más de un curso activo:\n"
            + "\n".join(lineas)
            + "\n\nPulse continuar, para seguir aprendiendo, y elija cuál seguir. "
            "No se reinicia su avance.\n\n_*menu* para volver._"
        )
    with canal_sandbox_si_meta():
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            texto + "\n\n[SEND_BUTTON:continuemos]",
            agente='sandbox_cursos',
        )
    return True


def bootstrap_cursos_sandbox(telefono_usuario: str, from_number: str) -> bool:
    """Alias: continuar inscritos (ya no arranca demo Riendas)."""
    return entrar_cursos_inscrito(telefono_usuario, from_number)


def _sticky_cursos_solo_si_inscrito_demo(telefono: str, curso) -> None:
    """Compat tests antiguos: no dejar modo cursos sin progreso real."""
    _est, progresos = _progresos_del_telefono(telefono)
    sesion = _get_or_create_sesion(telefono)
    if not any(not p.completado for p in progresos):
        _set_modo(sesion, MODO_MENU)


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
    from_n = decision.from_number or sandbox_number()

    if decision.reset_nat:
        marcar_corte_memoria_nat(decision.telefono_usuario)
        texto = saludo_agente(agente, reinicio=True)  # type: ignore[arg-type]
    elif decision.saludo_entrada:
        texto = saludo_agente(agente)  # type: ignore[arg-type]
    elif decision.es_toque:
        texto = TEXTO_TOQUE_NO_PREGUNTA
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
            texto = texto_cupo_ia(tope)
        else:
            _reaccion_espera(decision.telefono_usuario, message_id)
            texto = responder_agente_sandbox(agente, body, telefono=decision.telefono_usuario)  # type: ignore[arg-type]
            registrar_pregunta_asesor(decision.telefono_usuario)
            _guardar_pregunta_en_memoria(decision.telefono_usuario, agente, body)
            try:
                from core.conocimiento_agentes import capturar_sugerencia

                capturar_sugerencia(agente, body, texto)
            except Exception:
                logger.exception('sandbox_captura_sugerencia_fail agente=%s', agente)
            quedan = tope - respuestas_asesor_en_el_mes(decision.telefono_usuario)
            if quedan == 2:
                texto = f"{texto}\n\nAviso: le quedan 2 preguntas este mes."
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


def _habeas_listo(telefono: str) -> bool:
    from core.utils_telefono import estudiante_por_telefono

    sesion = _get_or_create_sesion(telefono)
    if getattr(sesion, 'habeas_aceptado', False):
        return True
    est = estudiante_por_telefono(telefono)
    if est is not None and est.acepto_terminos:
        sesion.habeas_aceptado = True
        sesion.save(update_fields=['habeas_aceptado', 'actualizado_en'])
        return True
    return False


def alinear_ficha_con_sesion_habeas(telefono: str) -> None:
    """Si la línea ya aceptó, la ficha no se queda en habeas.

    No toca ESPERANDO_CEDULA ni CONFIRMANDO_DATOS: esa identidad sigue.
    """
    if not telefono or not _habeas_listo(telefono):
        return
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(telefono)
    if est is None:
        return
    campos = []
    if not est.acepto_terminos:
        from core.consentimiento_wa import registrar_optin

        est.acepto_terminos = True
        est.fecha_aceptacion_terminos = timezone.now()
        campos.extend(['acepto_terminos', 'fecha_aceptacion_terminos'])
        registrar_optin(est, 'sesion_linea')
    if (est.estado_chat or '') == 'ESPERANDO_HABEAS_DATA':
        est.estado_chat = 'ACTIVO'
        campos.append('estado_chat')
    if campos:
        est.save(update_fields=campos)


def _aceptar_habeas_y_abrir_menu(telefono: str, from_number: str, est) -> str:
    """Sin ficha no hay cédula que verificar: abre el menú."""
    sesion = _get_or_create_sesion(telefono)
    sesion.habeas_aceptado = True
    sesion.modo = MODO_MENU
    sesion.save(update_fields=['habeas_aceptado', 'modo', 'actualizado_en'])
    enviar_menu_sandbox(telefono, from_number)
    return 'handled'


def _aceptar_habeas_y_pedir_cedula(telefono: str, from_number: str, est) -> str:
    """Aceptó: pide la cédula. El menú sale cuando confirme los datos."""
    from core.consentimiento_wa import registrar_optin
    from core.habeas_respuestas import MSG_ACEPTO_CEDULA

    registrar_optin(est, 'habeas')
    est.acepto_terminos = True
    est.fecha_aceptacion_terminos = timezone.now()
    est.estado_chat = 'ESPERANDO_CEDULA'
    est.save(update_fields=['acepto_terminos', 'fecha_aceptacion_terminos', 'estado_chat'])
    sesion = _get_or_create_sesion(telefono)
    sesion.habeas_aceptado = True
    sesion.modo = MODO_CURSOS
    sesion.save(update_fields=['habeas_aceptado', 'modo', 'actualizado_en'])
    enviar_texto_sandbox(telefono, from_number, MSG_ACEPTO_CEDULA, agente='habeas_meta')
    return 'handled'


def _enviar_confirma_numero(telefono: str, from_number: str, est) -> None:
    from core.habeas_respuestas import texto_confirma_numero
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    texto = texto_confirma_numero(est, telefono)
    if sandbox_via_meta():
        enviar_meta_botones(
            telefono,
            texto,
            [('si', 'Sí'), ('no', 'No')],
            agente_evento='habeas_meta',
        )
        return
    enviar_texto_sandbox(
        telefono, from_number,
        f"{texto}\n\nEscriba *sí* o *no*.",
        agente='habeas_meta',
    )


def _responder_cedula(telefono: str, from_number: str, body: str) -> str | None:
    """None si no está en cédula. 'handled' si esta vuelta fue la cédula."""
    import re

    from core.habeas_respuestas import MSG_ACEPTO_CEDULA, MSG_CEDULA_NO_COINCIDE
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(telefono)
    if est is None or (est.estado_chat or '') != 'ESPERANDO_CEDULA':
        return None
    t = (body or '').strip().lower()
    if _es_boton_inicio_flujo(body) or t in ('continuemos', 'continuar'):
        enviar_texto_sandbox(telefono, from_number, MSG_ACEPTO_CEDULA, agente='habeas_meta')
        return 'handled'
    cedula_input = re.sub(r'[\s.\-]', '', (body or '').strip())
    if cedula_input and cedula_input == (est.cedula or ''):
        est.estado_chat = 'CONFIRMANDO_DATOS'
        est.save(update_fields=['estado_chat'])
        _set_modo(_get_or_create_sesion(telefono), MODO_CURSOS)
        _enviar_confirma_numero(telefono, from_number, est)
        return 'handled'
    enviar_texto_sandbox(telefono, from_number, MSG_CEDULA_NO_COINCIDE, agente='habeas_meta')
    return 'handled'


def _responder_confirmacion(telefono: str, from_number: str, body: str) -> str | None:
    """None si no está confirmando. 'handled' si esta vuelta fue la verificación."""
    from core.habeas_respuestas import MSG_DATOS_NO
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(telefono)
    if est is None or (est.estado_chat or '') != 'CONFIRMANDO_DATOS':
        return None
    t = (body or '').strip().lower()
    if t in _SI_CONFIRMA_DATOS:
        est.estado_chat = 'ACTIVO'
        est.estado_onboarding = 'completado'
        est.save(update_fields=['estado_chat', 'estado_onboarding'])
        sesion = _get_or_create_sesion(telefono)
        sesion.habeas_aceptado = True
        sesion.save(update_fields=['habeas_aceptado', 'actualizado_en'])
        _set_modo(sesion, MODO_MENU)
        enviar_menu_sandbox(telefono, from_number)
        return 'handled'
    if t in _NO_CONFIRMA_DATOS:
        enviar_texto_sandbox(telefono, from_number, MSG_DATOS_NO, agente='habeas_meta')
        return 'handled'
    _enviar_confirma_numero(telefono, from_number, est)
    return 'handled'


def _responder_habeas(telefono: str, from_number: str, body: str) -> str | None:
    """None si ya puede ver el menú. 'handled' si esta vuelta fue solo habeas."""
    from core.utils_telefono import estudiante_por_telefono

    t = (body or '').strip().lower()
    est = estudiante_por_telefono(telefono)
    if t in ('continuemos', 'continuar') and est is not None and not est.acepto_terminos:
        from core.sandbox_canal import enviar_sandbox_habeas

        enviar_sandbox_habeas(telefono)
        return 'handled'
    if t in ('acepto', 'aceptó', 'si', 'sí', 'de acuerdo') and (
        est is None or not est.acepto_terminos
    ):
        if est is None:
            return _aceptar_habeas_y_abrir_menu(telefono, from_number, est)
        return _aceptar_habeas_y_pedir_cedula(telefono, from_number, est)
    if _habeas_listo(telefono):
        return None
    if t in ('acepto', 'aceptó', 'si', 'sí', 'de acuerdo'):
        if est is None:
            return _aceptar_habeas_y_abrir_menu(telefono, from_number, est)
        return _aceptar_habeas_y_pedir_cedula(telefono, from_number, est)
    if t in ('no_acepto', 'no acepto', 'no'):
        enviar_texto_sandbox(
            telefono,
            from_number,
            "Sin la autorización no podemos abrir la formación ni la asesoría.\n\n"
            "Cuando quiera, escriba *acepto*.",
            agente='sandbox_menu',
        )
        return 'handled'
    from core.sandbox_canal import enviar_sandbox_habeas

    enviar_sandbox_habeas(telefono)
    return 'handled'


def _avisar_aula_es_twilio(telefono: str, from_number: str, body: str) -> bool:
    """*aula* en Meta no emite código: el aula vive en la línea Twilio."""
    from aprende.acceso_whatsapp import mensaje_pide_acceso_aula

    if not mensaje_pide_acceso_aula(body):
        return False
    from core.lineas.variante import es_modo_twilio

    if es_modo_twilio():
        aviso = (
            'El *aula* se pide por la otra línea. Escriba *aula* allá para recibir el código. '
            'Esta línea es solo del curso (Formador y Compañero). '
            'Escriba *continuar* si ya está inscrito.'
        )
    else:
        aviso = (
            'El *aula* (eki Aprende) se pide por la línea de cursos. '
            'Escriba *aula* allá para recibir el código. '
            'En esta línea están *Formación* y *Asesoría*.'
        )
    try:
        enviar_texto_sandbox(
            telefono,
            from_number,
            aviso,
            agente='sandbox_menu',
        )
    except Exception:
        logger.exception('sandbox_aula_aviso_fail')
    return True


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
        from core.consentimiento_wa import es_optout, registrar_optout
        from core.utils_telefono import estudiante_por_telefono

        if es_optout(body_habeas):
            est = estudiante_por_telefono(from_tel)
            if est is not None and not getattr(est, 'wa_optout_fecha', None):
                registrar_optout(est)
                try:
                    enviar_texto_sandbox(
                        from_tel,
                        sandbox_number(),
                        'Listo. No le enviaremos más recordatorios ni plantillas por esta línea.',
                        agente='optout',
                    )
                except Exception:
                    logger.exception('sandbox_optout_fail')
            return 'handled'
        corte = _responder_habeas(from_tel, sandbox_number(), body_habeas)
        if corte == 'handled':
            return 'handled'
        corte = _responder_cedula(from_tel, sandbox_number(), body_habeas)
        if corte == 'handled':
            return 'handled'
        corte = _responder_confirmacion(from_tel, sandbox_number(), body_habeas)
        if corte == 'handled':
            return 'handled'
        if _avisar_aula_es_twilio(from_tel, sandbox_number(), body_habeas):
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

    from core.lineas.variante import TEXTO_LINEA_MODO_TWILIO, es_modo_twilio

    if es_modo_twilio():
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
