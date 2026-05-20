"""Agente PQRS automático en primer nivel (WhatsApp educativo).

Cuando un estudiante envía "ayuda", "no entiendo", "error", etc., se crea
:class:`SolicitudSoporte`. Este módulo clasifica, responde y escala según reglas
de negocio (máx. 2 preguntas de clarificación, alcance limitado, sin inventar).
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
    "Esa consulta es sobre el contenido del curso. Continúe su lección escribiendo 'listo' "
    "o consúltela con su facilitador."
)

CIERRE_PQRS = "Si necesita más ayuda, escríbame de nuevo."

PQRS_SYSTEM_PROMPT = f"""\
Usted es el asistente de soporte de eki para productores en formación por WhatsApp.

REGLAS DURAS:
- Tono: siempre formal (usted), cálido y conciso. Máximo 3 párrafos cortos.
- Máximo 2 preguntas de clarificación por ticket (el sistema lo controla; no pida una tercera).
- Si el mensaje es ambiguo (no queda claro acceso, contenido, técnico u otro), puede hacer UNA pregunta concreta.
- Categorías: acceso | contenido | tecnico | otro
  - acceso: no puede entrar, cédula incorrecta, datos de identificación
  - contenido: no entiende el módulo, video no carga, no ve la lección (bloqueo de plataforma)
  - tecnico: error del sistema, no recibe mensajes
  - otro: lo demás
- acceso y contenido: resuelva con instrucción concreta si puede (escalar=false).
- tecnico y otro: siempre escalar (escalar=true).
- Si pregunta sobre CONTENIDO ACADÉMICO del curso (agronomía, dosis, fumigación, etc.) → NO responda el contenido. Marque consulta_contenido_curso=true y use el mensaje de redirección a lección.
- PERMITIDO orientar: corregir nombre/municipio/cédula (menú o "corregir datos"), retomar curso ("listo"/"menú"), consultar puntos o progreso propio.
- FUERA DE ALCANCE (marque fuera_de_alcance=true): cambiar teléfono, organización o estado de progreso; acceso a módulos no asignados; respuestas de evaluaciones; modificar registros ajenos al perfil del estudiante.
- NUNCA invente soluciones ni prometa tiempos de resolución.
- Cierre SIEMPRE con: "{CIERRE_PQRS}"

Devuelva SIEMPRE JSON válido:
{{
  "categoria": "acceso|contenido|tecnico|otro",
  "respuesta_whatsapp": "texto para el estudiante",
  "escalar": true|false,
  "nota_interna": "resumen breve para el equipo",
  "hacer_pregunta_clarificacion": true|false,
  "fuera_de_alcance": true|false,
  "consulta_contenido_curso": true|false
}}
"""

CATEGORIAS_VALIDAS = {"acceso", "contenido", "tecnico", "otro"}

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
    if CIERRE_PQRS not in respuesta:
        respuesta = respuesta.rstrip() + f"\n\n{CIERRE_PQRS}"
    return respuesta


def _escalar_por_limite_preguntas(solicitud) -> dict[str, Any]:
    return {
        'categoria': 'otro',
        'respuesta_whatsapp': _asegurar_cierre(
            "Gracias por su paciencia. Para atenderle mejor, su caso fue enviado a nuestro equipo "
            "de facilitadores, quienes le contactarán por este mismo canal."
        ),
        'escalar': True,
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


def procesar_pqrs_automatico(solicitud_soporte) -> dict[str, Any]:
    """Primera respuesta del agente tras crear la solicitud."""
    mensaje = (getattr(solicitud_soporte, 'mensaje_original', '') or '').strip()
    if not mensaje:
        return _fallback_escalar('Mensaje vacío en la solicitud')
    if _detectar_fuera_alcance(mensaje):
        return _resultado_fuera_alcance()
    if _detectar_consulta_contenido(mensaje):
        return _resultado_contenido_curso()
    raw = _llamar_openai_pqrs(mensaje, contexto='')
    if raw is None:
        return _fallback_escalar('OpenAI no disponible o falló la respuesta')
    return _parsear_respuesta_pqrs(raw, mensaje_usuario=mensaje)


def procesar_seguimiento_pqrs(solicitud_soporte, mensaje_estudiante: str) -> dict[str, Any]:
    """Procesa un mensaje de seguimiento dentro del mismo ticket PQRS."""
    mensaje = (mensaje_estudiante or '').strip()
    if not mensaje:
        return _fallback_escalar('Mensaje vacío en seguimiento')

    preguntas = int(getattr(solicitud_soporte, 'preguntas_realizadas', 0) or 0)
    if preguntas >= 2:
        return _escalar_por_limite_preguntas(solicitud_soporte)

    _registrar_seguimiento_estudiante(solicitud_soporte, mensaje)

    if _detectar_fuera_alcance(mensaje):
        return _resultado_fuera_alcance()
    if _detectar_consulta_contenido(mensaje):
        return _resultado_contenido_curso()

    contexto = _historial_conversacion(solicitud_soporte)
    raw = _llamar_openai_pqrs(mensaje, contexto=contexto, es_seguimiento=True)
    if raw is None:
        return _fallback_escalar('OpenAI no disponible en seguimiento')

    resultado = _parsear_respuesta_pqrs(raw, mensaje_usuario=mensaje)
    if resultado.get('hacer_pregunta_clarificacion') and preguntas >= 1:
        resultado['hacer_pregunta_clarificacion'] = False
        if not resultado.get('escalar') and resultado.get('categoria') not in ('tecnico', 'otro'):
            resultado['escalar'] = True
            resultado['nota_interna'] = (
                (resultado.get('nota_interna') or '')
                + ' | Límite de preguntas alcanzado en seguimiento.'
            ).strip(' |')
    return resultado


def intentar_procesar_seguimiento_pqrs_whatsapp(estudiante, mensaje: str) -> Optional[str]:
    """Si hay ticket PQRS abierto, procesa el mensaje y devuelve texto de respuesta."""
    from core.models import SolicitudSoporte

    ticket = (
        SolicitudSoporte.objects.filter(
            estudiante=estudiante,
            estado='en_atencion',
            resuelto_por_agente=False,
        )
        .order_by('-fecha_solicitud')
        .first()
    )
    if not ticket:
        return None

    resultado = procesar_seguimiento_pqrs(ticket, mensaje)
    aplicar_resultado_pqrs(ticket, resultado)
    return resultado.get('respuesta_whatsapp')


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
    nota = (resultado.get('nota_interna') or '').strip()

    if categoria in {'tecnico', 'otro'}:
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
        solicitud_soporte.estado = 'en_atencion'
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
                {'role': 'user', 'content': user_content[:4000]},
            ],
            temperature=0.3,
            max_tokens=450,
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

    respuesta = (data.get('respuesta_whatsapp') or '').strip()
    if not respuesta:
        return _fallback_escalar('Respuesta vacía del modelo')
    respuesta = _asegurar_cierre(respuesta)

    escalar_raw = data.get('escalar', True)
    if isinstance(escalar_raw, str):
        escalar = escalar_raw.strip().lower() in {'true', '1', 'si', 'sí', 'yes'}
    else:
        escalar = bool(escalar_raw)

    if categoria in {'tecnico', 'otro'}:
        escalar = True

    hacer_pregunta = bool(data.get('hacer_pregunta_clarificacion', False))
    if hacer_pregunta and escalar:
        hacer_pregunta = False

    nota = (data.get('nota_interna') or '').strip()

    return {
        'categoria': categoria,
        'respuesta_whatsapp': respuesta,
        'escalar': escalar,
        'nota_interna': nota,
        'hacer_pregunta_clarificacion': hacer_pregunta,
        'fuera_de_alcance': False,
        'consulta_contenido_curso': False,
    }


def _fallback_escalar(motivo: str) -> dict[str, Any]:
    return {
        'categoria': 'otro',
        'respuesta_whatsapp': _asegurar_cierre(
            '🆘 Recibí su solicitud y la pasé a nuestro equipo. Le vamos a responder lo antes posible.'
        ),
        'escalar': True,
        'nota_interna': f'[Fallback] {motivo}',
        'hacer_pregunta_clarificacion': False,
        'fuera_de_alcance': False,
        'consulta_contenido_curso': False,
    }
