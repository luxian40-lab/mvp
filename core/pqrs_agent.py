"""Agente PQRS automático en primer nivel (WhatsApp educativo).

Lee el contexto del estudiante, ejecuta acciones seguras (datos, progreso,
reenvío de módulo) y lo devuelve al curso con *listo*. Solo escala a humano
lo que no pueda resolver.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

MENSAJE_FUERA_ALCANCE = (
    "Eso está fuera de lo que puedo gestionar por este canal. Por favor comuníquese con "
    "su facilitador o escriba a comunidad.educativa@eki.com.co para que le ayuden."
)

MENSAJE_CONTENIDO_CURSO = (
    "Esa consulta es sobre el contenido del curso. Continúe su lección escribiendo *listo* "
    "o consúltela con su facilitador."
)

CIERRE_PQRS = "Para seguir con el curso escriba *listo*."

PQRS_SYSTEM_PROMPT = f"""\
Usted es el asistente de soporte de eki para personas en formación por WhatsApp.

REGLAS DURAS:
- Tono: formal (usted), cálido y conciso. Máximo 3 párrafos cortos.
- Use el CONTEXTO DEL ESTUDIANTE (curso, módulo, avance, datos). No invente datos.
- Máximo 2 preguntas de clarificación por ticket.
- Categorías: acceso | contenido | tecnico | otro
- ACCIONES permitidas (campo "accion"):
  - ninguna: solo responder / orientar
  - corregir_datos: nombre, municipio o cédula (si conoce el valor use campo_correccion + valor_nuevo; si no, deje valor vacío para abrir menú)
  - explicar_progreso: el sistema enviará el avance real
  - reenviar_modulo: el sistema reenviará el material del módulo actual sin avanzar
  - escalar: no puede resolver; equipo humano
- PERMITIDO: corregir nombre/municipio/cédula, explicar progreso/drip, reenviar módulo, retomar con *listo*.
- PROHIBIDO (fuera_de_alcance=true): cambiar teléfono u organización; marcar progreso completado; saltar drip; dar respuestas de examen.
- Si pregunta CONTENIDO ACADÉMICO (agronomía, dosis, etc.) → consulta_contenido_curso=true (no enseñe la materia).
- Si puede resolver con una acción, escalar=false.
- Si es fallo del sistema desconocido o requiere humano → accion=escalar, escalar=true.
- En respuesta_whatsapp NO prometa tiempos de resolución. Si resolvió, mencione *listo*.
- Cierre orientado al curso: "{CIERRE_PQRS}"

Devuelva SIEMPRE JSON válido:
{{
  "categoria": "acceso|contenido|tecnico|otro",
  "respuesta_whatsapp": "texto para el estudiante",
  "escalar": true|false,
  "accion": "ninguna|corregir_datos|explicar_progreso|reenviar_modulo|escalar",
  "campo_correccion": "nombre|municipio|cedula|",
  "valor_nuevo": "",
  "nota_interna": "resumen breve",
  "hacer_pregunta_clarificacion": true|false,
  "fuera_de_alcance": true|false,
  "consulta_contenido_curso": true|false
}}
"""

CATEGORIAS_VALIDAS = {"acceso", "contenido", "tecnico", "otro"}

_AYUDA_EXACTAS = frozenset({
    'ayuda', 'help', 'soporte', 'ticket', 'problema', 'pqrs', 'queja', 'reclamo', 'solicitud',
    'necesito ayuda', 'necesito soporte', 'ayudame', 'ayúdame',
})

_HORAS_TICKET_ABIERTO = 72

_PATRONES_FUERA_ALCANCE = [
    re.compile(r'cambiar\s+(?:el\s+|mi\s+|su\s+)?tel[eé]fono', re.I),
    re.compile(r'actualizar\s+tel[eé]fono', re.I),
    re.compile(r'otro\s+n[uú]mero', re.I),
    re.compile(r'cambiar\s+organizaci[oó]n', re.I),
    re.compile(r'empresa\s+distinta', re.I),
    re.compile(r'cambiar\s+progreso|modificar\s+progreso|marcar\s+completado', re.I),
    re.compile(r'acceso\s+a\s+m[oó]dulo|m[oó]dulo\s+que\s+no', re.I),
    re.compile(r'respuesta\s+de\s+(?:la\s+)?evaluaci[oó]n|respuestas\s+del\s+examen', re.I),
    re.compile(r'darme\s+la\s+respuesta', re.I),
]

_PATRON_CONTENIDO_ACADEMICO = re.compile(
    r'\b(fumig\w*|dosis|fertiliz\w*|abono|plaga|roya|broca|hect[aá]rea)\b|'
    r'cu[aá]ndo\s+se\s+\w+|qu[eé]\s+dosis\b|qu[eé]\s+es\s+el\s+\w+',
    re.I,
)

_PATRON_BLOQUEO_PLATAFORMA = re.compile(
    r'\b(no\s+entiendo\s+el\s+m[oó]dulo|video\s+no\s+carga|no\s+carga\s+el\s+video|'
    r'no\s+veo\s+la\s+lecci[oó]n|error\s+al\s+abrir|no\s+puedo\s+ver)\b',
    re.I,
)


def construir_contexto_estudiante(estudiante) -> str:
    """Resumen factual para el LLM (curso, módulo, avance, datos)."""
    from core.drip_schedule import drip_bloquea_siguiente_modulo
    from core.models import ProgresoEstudiante

    cliente = getattr(estudiante, 'cliente', None)
    lineas = [
        'CONTEXTO DEL ESTUDIANTE:',
        f"- Nombre: {estudiante.nombre or '—'}",
        f"- Cédula: {estudiante.cedula or '—'}",
        f"- Municipio: {getattr(estudiante, 'municipio', None) or '—'}",
        f"- Teléfono: {estudiante.telefono or '—'}",
        f"- Organización: {cliente.nombre if cliente else '—'}",
        f"- estado_chat: {estudiante.estado_chat}",
        f"- onboarding: {estudiante.estado_onboarding}",
    ]
    ctx = estudiante.contexto_temporal or {}
    if ctx.get('curso_activo_id'):
        lineas.append(f"- curso_activo_id (foco): {ctx.get('curso_activo_id')}")

    progresos = (
        ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            curso__activo=True,
        )
        .select_related('curso', 'modulo_actual')
        .order_by('-fecha_inicio')[:5]
    )
    if not progresos:
        lineas.append('- Progresos: ninguno')
    else:
        lineas.append('- Progresos:')
        for p in progresos:
            mod = p.modulo_actual
            drip = False
            if mod:
                try:
                    drip = drip_bloquea_siguiente_modulo(p, mod)
                except Exception:
                    drip = False
            lineas.append(
                f"  * curso={p.curso.nombre if p.curso else '?'} id={p.curso_id} "
                f"completado={p.completado} avance={p.porcentaje_avance()}% "
                f"mod={mod.numero if mod else '—'} "
                f"titulo={mod.titulo if mod else '—'} drip_bloquea={drip}"
            )
    return '\n'.join(lineas)


def _detectar_fuera_alcance(texto: str) -> bool:
    t = texto or ''
    return any(p.search(t) for p in _PATRONES_FUERA_ALCANCE)


def _detectar_consulta_contenido(texto: str) -> bool:
    if _PATRON_BLOQUEO_PLATAFORMA.search(texto or ''):
        return False
    return bool(_PATRON_CONTENIDO_ACADEMICO.search(texto or ''))


def _append_nota(solicitud, nota: str) -> None:
    prev = (solicitud.notas_internas or '').strip()
    linea = f"[Agente PQRS] {nota}"
    solicitud.notas_internas = f"{prev}\n{linea}".strip() if prev else linea


def _asegurar_cierre(respuesta: str) -> str:
    respuesta = (respuesta or '').strip()
    if not respuesta:
        return CIERRE_PQRS
    if CIERRE_PQRS.lower() in respuesta.lower() or 'listo' in respuesta.lower():
        return respuesta
    return respuesta.rstrip() + f"\n\n{CIERRE_PQRS}"


def _escalar_por_limite_preguntas(solicitud) -> dict[str, Any]:
    return {
        'categoria': 'otro',
        'respuesta_whatsapp': _asegurar_cierre(
            "Gracias por su paciencia. Para atenderle mejor, su caso fue enviado a nuestro equipo "
            "de facilitadores, quienes le contactarán por este mismo canal."
        ),
        'escalar': True,
        'accion': 'escalar',
        'nota_interna': 'Escalado por falta de claridad tras 2 intentos de clarificación.',
        'hacer_pregunta_clarificacion': False,
        'fuera_de_alcance': False,
        'consulta_contenido_curso': False,
    }


def _resultado_fuera_alcance() -> dict[str, Any]:
    return {
        'categoria': 'otro',
        'respuesta_whatsapp': _asegurar_cierre(MENSAJE_FUERA_ALCANCE),
        'escalar': True,
        'accion': 'escalar',
        'nota_interna': 'Solicitud fuera de alcance del agente — requiere facilitador.',
        'hacer_pregunta_clarificacion': False,
        'fuera_de_alcance': True,
        'consulta_contenido_curso': False,
    }


def _resultado_contenido_curso() -> dict[str, Any]:
    return {
        'categoria': 'contenido',
        'respuesta_whatsapp': _asegurar_cierre(MENSAJE_CONTENIDO_CURSO),
        'escalar': False,
        'accion': 'ninguna',
        'nota_interna': 'Consulta académica del curso — redirigido a lección/facilitador.',
        'hacer_pregunta_clarificacion': False,
        'fuera_de_alcance': False,
        'consulta_contenido_curso': True,
    }


def _historial_conversacion(solicitud) -> str:
    base = (getattr(solicitud, 'mensaje_original', '') or '').strip()
    notas = (getattr(solicitud, 'notas_internas', '') or '')
    seguimientos = []
    for linea in notas.splitlines():
        if '[Seguimiento estudiante]' in linea:
            seguimientos.append(linea.split(']', 1)[-1].strip())
    partes = [f"Mensaje inicial: {base}"]
    for i, s in enumerate(seguimientos, 1):
        partes.append(f"Respuesta estudiante {i}: {s}")
    return '\n'.join(partes)


def _registrar_seguimiento_estudiante(solicitud, mensaje: str) -> None:
    _append_nota(solicitud, f"[Seguimiento estudiante] {mensaje.strip()[:500]}")


def _normalizar_texto_whatsapp(mensaje: str) -> str:
    t = (mensaje or '').strip().lower()
    return re.sub(r'[*_]+', '', t).strip()


def mensaje_es_solo_ayuda(mensaje: str) -> bool:
    return _normalizar_texto_whatsapp(mensaje) in _AYUDA_EXACTAS


def mensaje_activa_soporte(mensaje: str) -> bool:
    """True si el mensaje debe abrir soporte o reforzar un ticket."""
    t = _normalizar_texto_whatsapp(mensaje)
    if not t:
        return False
    if t in _AYUDA_EXACTAS:
        return True
    if re.match(r'^ayuda\b', t):
        return True
    if re.match(r'^(?:necesito|quiero)\s+ayuda\b', t):
        return True
    return False


def obtener_ticket_pqrs_abierto(estudiante):
    """Ticket reciente pendiente o en atención (no resuelto por el agente)."""
    from datetime import timedelta

    from django.utils import timezone

    from core.models import SolicitudSoporte

    desde = timezone.now() - timedelta(hours=_HORAS_TICKET_ABIERTO)
    return (
        SolicitudSoporte.objects.filter(
            estudiante=estudiante,
            estado__in=('pendiente', 'en_atencion'),
            resuelto_por_agente=False,
            fecha_solicitud__gte=desde,
        )
        .order_by('-fecha_solicitud')
        .first()
    )


def respuesta_ayuda_con_ticket_abierto(estudiante, mensaje: str) -> Optional[str]:
    """Si ya hay ticket abierto y repiten «ayuda» sin detalle, no crear otro."""
    if not mensaje_es_solo_ayuda(mensaje):
        return None
    if not obtener_ticket_pqrs_abierto(estudiante):
        return None
    nombre = (estudiante.nombre or '').strip().split()
    saludo = f"Hola {nombre[0]}, " if nombre else ''
    return (
        f"{saludo}ya tenemos su solicitud en revisión.\n\n"
        "Cuéntenos qué pasa (por ejemplo: no carga el módulo, dato mal registrado) "
        "y lo atendemos aquí.\n\n"
        f"{CIERRE_PQRS}"
    )


def _contexto_completo(solicitud) -> str:
    est = getattr(solicitud, 'estudiante', None)
    partes = []
    if est:
        partes.append(construir_contexto_estudiante(est))
    partes.append(_historial_conversacion(solicitud))
    return '\n\n'.join(partes)


def _enriquecer_con_acciones(solicitud, resultado: dict[str, Any]) -> dict[str, Any]:
    from core.pqrs_acciones import ejecutar_accion_pqrs

    est = getattr(solicitud, 'estudiante', None)
    if not est:
        return resultado
    return ejecutar_accion_pqrs(est, resultado)


def procesar_pqrs_automatico(solicitud_soporte) -> dict[str, Any]:
    """Primera respuesta del agente tras crear la solicitud."""
    mensaje = (getattr(solicitud_soporte, 'mensaje_original', '') or '').strip()
    if not mensaje:
        return _fallback_escalar('Mensaje vacío en la solicitud')
    if _detectar_fuera_alcance(mensaje):
        return _resultado_fuera_alcance()
    if _detectar_consulta_contenido(mensaje):
        return _enriquecer_con_acciones(solicitud_soporte, _resultado_contenido_curso())

    # Heurística sin LLM: "progreso" / "avance" / reenviar
    t = _normalizar_texto_whatsapp(mensaje)
    if any(k in t for k in ('progreso', 'avance', 'cómo voy', 'como voy', 'mi avance')):
        resultado = {
            'categoria': 'contenido',
            'respuesta_whatsapp': '',
            'escalar': False,
            'accion': 'explicar_progreso',
            'nota_interna': 'Heurística: explicar_progreso',
            'hacer_pregunta_clarificacion': False,
            'fuera_de_alcance': False,
            'consulta_contenido_curso': False,
        }
        return _enriquecer_con_acciones(solicitud_soporte, resultado)
    if any(k in t for k in ('reenvia', 'reenvíe', 'reenvie', 'no me llegó', 'no me llego', 'mandar de nuevo', 'otra vez el módulo', 'otra vez el modulo')):
        resultado = {
            'categoria': 'contenido',
            'respuesta_whatsapp': '',
            'escalar': False,
            'accion': 'reenviar_modulo',
            'nota_interna': 'Heurística: reenviar_modulo',
            'hacer_pregunta_clarificacion': False,
            'fuera_de_alcance': False,
            'consulta_contenido_curso': False,
        }
        return _enriquecer_con_acciones(solicitud_soporte, resultado)
    if 'corregir' in t and any(k in t for k in ('nombre', 'municipio', 'cedula', 'cédula', 'dato')):
        resultado = {
            'categoria': 'acceso',
            'respuesta_whatsapp': '',
            'escalar': False,
            'accion': 'corregir_datos',
            'campo_correccion': '',
            'valor_nuevo': '',
            'nota_interna': 'Heurística: iniciar corregir_datos',
            'hacer_pregunta_clarificacion': False,
            'fuera_de_alcance': False,
            'consulta_contenido_curso': False,
        }
        return _enriquecer_con_acciones(solicitud_soporte, resultado)

    raw = _llamar_openai_pqrs(mensaje, contexto=_contexto_completo(solicitud_soporte))
    if raw is None:
        return _fallback_escalar('OpenAI no disponible o falló la respuesta')
    resultado = _parsear_respuesta_pqrs(raw, mensaje_usuario=mensaje)
    return _enriquecer_con_acciones(solicitud_soporte, resultado)


def procesar_seguimiento_pqrs(solicitud_soporte, mensaje_estudiante: str) -> dict[str, Any]:
    """Procesa un mensaje de seguimiento dentro del mismo ticket PQRS."""
    mensaje = (mensaje_estudiante or '').strip()
    if not mensaje:
        return _fallback_escalar('Mensaje vacío en seguimiento')

    preguntas = int(getattr(solicitud_soporte, 'preguntas_realizadas', 0) or 0)
    if preguntas >= 2:
        return _escalar_por_limite_preguntas(solicitud_soporte)

    _registrar_seguimiento_estudiante(solicitud_soporte, mensaje)
    solicitud_soporte.save(update_fields=['notas_internas'])

    if _detectar_fuera_alcance(mensaje):
        return _resultado_fuera_alcance()
    if _detectar_consulta_contenido(mensaje):
        return _enriquecer_con_acciones(solicitud_soporte, _resultado_contenido_curso())

    raw = _llamar_openai_pqrs(
        mensaje,
        contexto=_contexto_completo(solicitud_soporte),
        es_seguimiento=True,
    )
    if raw is None:
        return _fallback_escalar('OpenAI no disponible en seguimiento')

    resultado = _parsear_respuesta_pqrs(raw, mensaje_usuario=mensaje)
    if resultado.get('hacer_pregunta_clarificacion') and preguntas >= 1:
        resultado['hacer_pregunta_clarificacion'] = False
        if not resultado.get('escalar') and resultado.get('categoria') not in ('tecnico', 'otro'):
            resultado['escalar'] = True
            resultado['accion'] = 'escalar'
            resultado['nota_interna'] = (
                (resultado.get('nota_interna') or '')
                + ' | Límite de preguntas alcanzado en seguimiento.'
            ).strip(' |')
    return _enriquecer_con_acciones(solicitud_soporte, resultado)


def intentar_procesar_seguimiento_pqrs_whatsapp(estudiante, mensaje: str) -> Optional[str]:
    """Si hay ticket PQRS abierto, procesa el mensaje y devuelve texto de respuesta."""
    ticket = obtener_ticket_pqrs_abierto(estudiante)
    if not ticket:
        return None

    from core.intent_detector import mensaje_indica_listo

    if mensaje_indica_listo(mensaje):
        return None

    if mensaje_es_solo_ayuda(mensaje):
        return respuesta_ayuda_con_ticket_abierto(estudiante, mensaje)

    if mensaje_activa_soporte(mensaje):
        return None

    # Detalle del problema → agente con contexto (también si estaba pendiente)
    base = _normalizar_texto_whatsapp(ticket.mensaje_original or '')
    if base in _AYUDA_EXACTAS or not base:
        ticket.mensaje_original = (mensaje or '').strip()
        ticket.save(update_fields=['mensaje_original'])

    resultado = procesar_seguimiento_pqrs(ticket, mensaje)
    aplicar_resultado_pqrs(ticket, resultado)
    if resultado.get('escalar'):
        notificar_escalacion_humana(ticket, motivo='Seguimiento escalado por agente')
    return resultado.get('respuesta_whatsapp')


def notificar_escalacion_humana(solicitud, motivo: str = '') -> None:
    """Email al equipo solo cuando el caso escala."""
    from django.conf import settings
    from django.core.mail import send_mail

    try:
        est = solicitud.estudiante
        email_to = getattr(settings, 'EMAIL_SOPORTE', 'comunidad.educativa@eki.com.co')
        asunto = f"🆘 PQRS escalado — {est.nombre if est else 'estudiante'}"
        cuerpo = (
            f"Motivo: {motivo or 'Escalado por agente'}\n\n"
            f"Estudiante: {getattr(est, 'nombre', '')}\n"
            f"Teléfono: {getattr(est, 'telefono', '')}\n"
            f"Cédula: {getattr(est, 'cedula', '')}\n"
            f"Ticket ID: {solicitud.id}\n"
            f"Categoría: {solicitud.categoria}\n\n"
            f"Mensaje:\n{solicitud.mensaje_original}\n\n"
            f"Notas:\n{solicitud.notas_internas or '—'}\n"
        )
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', email_to),
            recipient_list=[email_to],
            fail_silently=True,
        )
        logger.info('[PQRS] Email escalación enviado ticket=%s', solicitud.id)
    except Exception:
        logger.exception('[PQRS] Error enviando email de escalación')


def aplicar_resultado_pqrs(solicitud_soporte, resultado: dict[str, Any]) -> None:
    """Persiste la decisión del agente en la solicitud."""
    from django.utils import timezone

    categoria = resultado.get('categoria', '')
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = 'otro'

    fuera = bool(resultado.get('fuera_de_alcance', False))
    consulta_curso = bool(resultado.get('consulta_contenido_curso', False))
    hacer_pregunta = bool(resultado.get('hacer_pregunta_clarificacion', False))
    escalar = bool(resultado.get('escalar', True))
    accion = (resultado.get('accion') or 'ninguna').strip().lower()
    nota = (resultado.get('nota_interna') or '').strip()

    # Acciones ejecutadas no deben forzar escalado por categoría tecnico/otro
    if accion in {'explicar_progreso', 'reenviar_modulo', 'corregir_datos'}:
        escalar = False
    elif categoria in {'tecnico', 'otro'} and accion in {'ninguna', 'escalar'}:
        escalar = True
    if fuera:
        escalar = True
    if consulta_curso:
        escalar = False
        categoria = 'contenido'

    preguntas = int(getattr(solicitud_soporte, 'preguntas_realizadas', 0) or 0)
    if hacer_pregunta and not escalar and preguntas < 2:
        preguntas += 1
        solicitud_soporte.preguntas_realizadas = preguntas
        solicitud_soporte.estado = 'en_atencion'
        solicitud_soporte.resuelto_por_agente = False
    elif escalar:
        solicitud_soporte.estado = 'pendiente'
        solicitud_soporte.resuelto_por_agente = False
    else:
        solicitud_soporte.estado = 'resuelta'
        solicitud_soporte.resuelto_por_agente = True
        solicitud_soporte.fecha_atencion = timezone.now()
        solicitud_soporte.atendido_por = 'Agente PQRS (IA)'

    solicitud_soporte.categoria = categoria
    if nota:
        _append_nota(solicitud_soporte, nota)

    update_fields = [
        'categoria',
        'resuelto_por_agente',
        'estado',
        'notas_internas',
        'preguntas_realizadas',
    ]
    if solicitud_soporte.resuelto_por_agente:
        update_fields.extend(['fecha_atencion', 'atendido_por'])
    solicitud_soporte.save(update_fields=update_fields)


def disparar_agente_pqrs_async(solicitud_soporte, callback_envio_whatsapp=None) -> None:
    """Lanza el agente PQRS en un hilo aparte para no bloquear el webhook."""

    def _worker():
        try:
            resultado = procesar_pqrs_automatico(solicitud_soporte)
            aplicar_resultado_pqrs(solicitud_soporte, resultado)
            if resultado.get('escalar'):
                notificar_escalacion_humana(
                    solicitud_soporte,
                    motivo=resultado.get('nota_interna') or 'Escalado automático',
                )
            if callback_envio_whatsapp and resultado.get('respuesta_whatsapp'):
                try:
                    callback_envio_whatsapp(
                        solicitud_soporte.estudiante,
                        resultado['respuesta_whatsapp'],
                    )
                except Exception as e:
                    logger.exception('[PQRS Agent] Error enviando respuesta WhatsApp: %s', e)
        except Exception as e:
            logger.exception('[PQRS Agent] Error procesando solicitud: %s', e)

    t = threading.Thread(target=_worker, name='pqrs-agent', daemon=True)
    t.start()


def _llamar_openai_pqrs(
    mensaje_usuario: str,
    *,
    contexto: str = '',
    es_seguimiento: bool = False,
) -> Optional[str]:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning('[PQRS Agent] OPENAI_API_KEY no configurada; fallback escalar.')
        return None
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_content = mensaje_usuario
        if contexto:
            user_content = f"{contexto}\n\nÚltimo mensaje del estudiante:\n{mensaje_usuario}"
        if es_seguimiento:
            user_content += (
                "\n\n(Es seguimiento de un ticket abierto. Respete máximo 2 preguntas de clarificación.)"
            )

        response = client.chat.completions.create(
            model=os.getenv('PQRS_MODEL', 'gpt-4o-mini'),
            messages=[
                {'role': 'system', 'content': PQRS_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_content[:6000]},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={'type': 'json_object'},
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning('[PQRS Agent] Error llamando OpenAI: %s', e)
        return None


def _parsear_respuesta_pqrs(raw: str, *, mensaje_usuario: str = '') -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return _fallback_escalar('Respuesta del modelo no es JSON válido')

    if _detectar_fuera_alcance(mensaje_usuario) or bool(data.get('fuera_de_alcance')):
        return _resultado_fuera_alcance()
    if _detectar_consulta_contenido(mensaje_usuario) or bool(data.get('consulta_contenido_curso')):
        return _resultado_contenido_curso()

    categoria = (data.get('categoria') or 'otro').strip().lower()
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = 'otro'

    accion = (data.get('accion') or 'ninguna').strip().lower()
    if accion not in {
        'ninguna', 'corregir_datos', 'explicar_progreso', 'reenviar_modulo', 'escalar',
    }:
        accion = 'ninguna'

    respuesta = (data.get('respuesta_whatsapp') or '').strip()
    if not respuesta and accion == 'ninguna':
        return _fallback_escalar('Respuesta vacía del modelo')
    if respuesta:
        respuesta = _asegurar_cierre(respuesta)

    escalar_raw = data.get('escalar', True)
    if isinstance(escalar_raw, str):
        escalar = escalar_raw.strip().lower() in {'true', '1', 'si', 'sí', 'yes'}
    else:
        escalar = bool(escalar_raw)

    if accion == 'escalar':
        escalar = True
    elif accion in {'explicar_progreso', 'reenviar_modulo', 'corregir_datos'}:
        escalar = False
    elif categoria in {'tecnico', 'otro'} and accion == 'ninguna':
        escalar = True

    hacer_pregunta = bool(data.get('hacer_pregunta_clarificacion', False))
    if hacer_pregunta and escalar:
        hacer_pregunta = False

    nota = (data.get('nota_interna') or '').strip()
    campo = (data.get('campo_correccion') or '').strip().lower()
    valor = (data.get('valor_nuevo') or '').strip()

    return {
        'categoria': categoria,
        'respuesta_whatsapp': respuesta,
        'escalar': escalar,
        'accion': accion,
        'campo_correccion': campo,
        'valor_nuevo': valor,
        'nota_interna': nota,
        'hacer_pregunta_clarificacion': hacer_pregunta,
        'fuera_de_alcance': False,
        'consulta_contenido_curso': False,
    }


def _fallback_escalar(motivo: str) -> dict[str, Any]:
    return {
        'categoria': 'otro',
        'respuesta_whatsapp': _asegurar_cierre(
            'Recibí su solicitud y la pasé a nuestro equipo. Le responderemos por este canal.'
        ),
        'escalar': True,
        'accion': 'escalar',
        'nota_interna': f'[Fallback] {motivo}',
        'hacer_pregunta_clarificacion': False,
        'fuera_de_alcance': False,
        'consulta_contenido_curso': False,
    }
