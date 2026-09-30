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
MODO_CURSOS = 'cursos'
MODO_FORMACION = 'formacion'
MODO_ASESORIA = 'asesoria'

MODOS_AGENTE = (MODO_NAT, MODO_COACH, MODO_IA_CAMPO, MODO_VENTAS)
_ACCIONES_ASESOR = frozenset({'show_agentes', 'show_asesoria', 'nat', 'coach', 'ia_campo', 'ventas'})

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


TEXTO_ASESORIA = texto_asesoria(30)

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


TEXTO_CUPO_IA = texto_cupo_ia(30)

TEXTO_AGENTES = (
    "🤖 *Agentes IA*\n\n"
    "1️⃣ Agrónomo (Nat) — cultivo y campo\n"
    "2️⃣ Coach — hábitos y motivación\n"
    "3️⃣ Profe IA — IA fácil para el campo\n"
    "4️⃣ Ventas — clientes, precio y cierre\n\n"
    "Cada agente *recuerda* la conversación.\n"
    "Escribe *1*, *2*, *3* o *4*.\n"
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
    # show_menu | show_agentes | nat | coach | ia_campo | ventas | cursos | cursos_bootstrap
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
    from core.sandbox_canal import (
        es_inbound_twilio_http,
        phone_id_es_sandbox,
        sandbox_via_meta,
        to_es_sandbox,
    )

    if not sandbox_menu_enabled():
        return False
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
    return (
        normalizar_telefono_whatsapp(from_raw),
        normalizar_telefono_whatsapp(to_raw),
        body,
    )


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


def clasificar_asesoria(texto: str) -> str | None:
    """Lleva la pregunta libre al agente. None si no alcanza para decidir."""
    t = (texto or '').strip().lower()
    if not t or t in ('1', '2', '3', '4'):
        return None
    if any(w in t for w in ('venta', 'precio', 'cliente', 'cerrar', 'comercial', 'negocio')):
        return MODO_VENTAS
    if any(w in t for w in (
        'plaga', 'cultivo', 'suelo', 'cosecha', 'fertil', 'finca', 'café', 'cafe', 'agron',
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
    if t in ('curso', 'cursos', 'edu', 'riendas'):
        return MODO_CURSOS
    # Compat: atajos directos
    if t in ('nat', 'nati', 'agronomo', 'agrónomo'):
        return MODO_NAT
    if t in ('coach', 'entrenador'):
        return MODO_COACH
    if t in ('profe', 'profe ia', 'ia campo', 'ia_campo'):
        return MODO_IA_CAMPO
    if t in ('ventas', 'venta', 'comercial', 'comercializacion', 'comercialización'):
        return MODO_VENTAS
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
    if t in ('4', '4️⃣', 'cuatro', 'ventas', 'venta', 'comercial', 'comercializacion', 'comercialización'):
        return MODO_VENTAS
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
    body = _body_o_audio_transcrito(payload, body)
    decision = SandboxRouteDecision(
        action='show_menu',
        from_number=to_tel or sandbox_number(),
        telefono_usuario=from_tel,
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
        # Texto libre en submenú → re-mostrar opciones
        decision.action = 'show_agentes'
        return decision

    if sesion.modo == MODO_ASESORIA:
        agente = clasificar_asesoria(body)
        if agente:
            _set_modo(sesion, agente)
            decision.action = agente
            decision.saludo_entrada = True
            return decision
        _set_modo(sesion, MODO_AGENTES)
        decision.action = 'show_agentes'
        return decision

    from core.cursos_generales import payload_catalogo

    if sesion.modo in (MODO_MENU, MODO_FORMACION, MODO_CURSOS) and payload_catalogo(body):
        decision.action = 'catalogo_general'
        decision.texto_menu = (body or '').strip()
        return decision

    if sesion.modo == MODO_FORMACION and (body or '').strip():
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


def enviar_menu_sandbox(telefono_usuario: str, from_number: str) -> dict:
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    plan = resolver_plan(telefono_usuario)
    if not plan.activo:
        return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_SIN_PLAN, agente='sandbox_plan')
    botones = []
    if plan.incluye_cursos:
        botones.append(('formacion', 'Formación'))
    if plan.incluye_asesor:
        botones.append(('asesoria', 'Asesoría'))
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
    """Un carrusel con foto. Ver curso inscribe. Más información manda la ficha."""
    from core.cursos_generales import CATALOGO, tarjetas_catalogo
    from core.sandbox_canal import enviar_meta_carrusel, sandbox_via_meta

    cuerpo = (
        "Deslice los tres cursos de eki. "
        "*Ver curso* lo inscribe en ese programa. "
        "*Más información* le manda la ficha. "
        "Si ya va en un curso, escriba *listo*."
    )
    if sandbox_via_meta():
        resultado = enviar_meta_carrusel(
            telefono_usuario,
            cuerpo,
            tarjetas_catalogo(),
            agente_evento='sandbox_formacion',
        )
        if resultado.get('success'):
            return
        logger.warning('sandbox_carrusel_fallback %s', resultado.get('response'))
    lineas = [cuerpo, '']
    for item in CATALOGO:
        lineas.append(f"*{item['nombre']}*\n{item['url']}\nEscriba ver {item['clave']} para empezar.")
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
        enviar_catalogo_formacion(telefono_usuario, from_number)
        return
    if dato.get('accion') == 'info':
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"*{item['nombre']}*\n{item['resumen']}\n\n{item['url']}\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    resultado = inscribir_en_catalogo(telefono_usuario, item['clave'])
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
            "Escriba *listo* para seguir el que ya tiene.\n\n"
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
        "Escriba *listo* para empezar. No se borra el avance de sus otros cursos.\n\n"
        "_*menu* para volver._",
        agente='sandbox_formacion',
    )


def enviar_menu_agentes(telefono_usuario: str, from_number: str) -> dict:
    return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_AGENTES, agente='sandbox_agentes')


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
            enviar_texto_sandbox(
                telefono_usuario,
                from_number,
                TEXTO_CURSO_NO_INSCRITO,
                agente='sandbox_cursos',
            )
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
            "Escriba *listo* para continuar donde iba. "
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
            + "\n\nEscriba *listo* y elija cuál seguir. "
            "No se reinicia su avance.\n\n_*menu* para volver._"
        )
    with canal_sandbox_si_meta():
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            texto,
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

        WhatsappLog.objects.create(
            telefono=telefono,
            mensaje=(body or '').strip()[:4000],
            tipo='INCOMING',
            agente_usado=f'sandbox_{agente}',
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
    else:
        agente = 'ia_campo'
    from_n = decision.from_number or sandbox_number()

    if decision.reset_nat:
        marcar_corte_memoria_nat(decision.telefono_usuario)
        texto = saludo_agente(agente, reinicio=True)  # type: ignore[arg-type]
    elif decision.saludo_entrada:
        texto = saludo_agente(agente)  # type: ignore[arg-type]
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
    sesion = _get_or_create_sesion(telefono)
    if getattr(sesion, 'habeas_aceptado', False):
        return True
    from core.models import Estudiante

    est = Estudiante.objects.filter(telefono=telefono, acepto_terminos=True).first()
    if est is not None:
        sesion.habeas_aceptado = True
        sesion.save(update_fields=['habeas_aceptado', 'actualizado_en'])
        return True
    return False


def _responder_habeas(telefono: str, from_number: str, body: str) -> str | None:
    """None si ya puede ver el menú. 'handled' si esta vuelta fue solo habeas."""
    t = (body or '').strip().lower()
    if t in ('acepto', 'aceptó', 'si', 'sí', 'de acuerdo'):
        sesion = _get_or_create_sesion(telefono)
        sesion.habeas_aceptado = True
        sesion.modo = MODO_MENU
        sesion.save(update_fields=['habeas_aceptado', 'modo', 'actualizado_en'])
        enviar_menu_sandbox(telefono, from_number)
        return 'handled'
    if t in ('no_acepto', 'no acepto', 'no'):
        enviar_texto_sandbox(
            telefono,
            from_number,
            "Sin la autorización no podemos abrir la formación ni la asesoría.\n\n"
            "Cuando quiera, escriba *acepto*.",
            agente='sandbox_menu',
        )
        return 'handled'
    if _habeas_listo(telefono):
        return None
    from core.sandbox_canal import enviar_sandbox_habeas

    enviar_sandbox_habeas(telefono)
    return 'handled'


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
        corte = _responder_habeas(from_tel, sandbox_number(), body_habeas)
        if corte == 'handled':
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

    if decision.action in _ACCIONES_ASESOR or decision.action == 'show_formacion':
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
            from core.sandbox_agentes import _tope_asesor_mes

            enviar_texto_sandbox(
                decision.telefono_usuario,
                from_n,
                texto_asesoria(_tope_asesor_mes(decision.telefono_usuario)),
                agente='sandbox_asesoria',
            )
        except Exception:
            logger.exception('sandbox_asesoria_send_failed')
        return 'handled'

    if decision.action == 'nat':
        if decision.reset_nat:
            marcar_corte_memoria_nat(decision.telefono_usuario)
            try:
                enviar_texto_sandbox(
                    decision.telefono_usuario,
                    from_n,
                    "🌿 *Agrónomo Nat*\n\n"
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
                    "🌿 *Agrónomo Nat*\n\n"
                    "Seguimos donde íbamos (memoria larga).\n"
                    "Cuéntame la duda, o escribe *reiniciar* para empezar de cero.\n\n"
                    "_*menu* para volver._",
                    agente='sandbox_nat',
                )
            except Exception:
                logger.exception('sandbox_nat_saludo_entrada_fail')
            return 'handled'
        from core.planes_linea import registrar_pregunta_asesor
        from core.sandbox_agentes import _tope_asesor_mes, excedio_cupo_ia_linea

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

    if decision.action in ('coach', 'ia_campo', 'ventas'):
        return _manejar_agente_extra(decision, body, _message_id(payload))

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
