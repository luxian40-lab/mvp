"""Agente PQRS automático en primer nivel.

Cuando un estudiante envía "ayuda", "no entiendo", "error", etc., el sistema crea
un objeto :class:`SolicitudSoporte`. Este módulo expone
:func:`procesar_pqrs_automatico`, que clasifica el caso vía OpenAI y genera una
respuesta cálida en español colombiano. Si el agente puede resolver el caso lo
marca como ``en_atencion`` (resuelto por IA); si no, queda ``pendiente`` para
que un humano lo atienda.

El agente NUNCA promete tiempos que no puede cumplir y siempre cierra con
"Si necesita más ayuda escríbame de nuevo.". El uso de OpenAI es opcional —
si no hay API key o falla la llamada, el agente devuelve un fallback seguro
que escala el caso (sin romper el flujo existente del webhook).
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)


PQRS_SYSTEM_PROMPT = """\
Eres el asistente de soporte de eki. Tu objetivo es resolver o escalar
solicitudes de soporte de productores agropecuarios colombianos.

Cuando un productor dice "ayuda", "no entiendo", "error", etc., su solicitud
ya quedó registrada. Tu trabajo es:

1. RESPONDER inmediatamente con un mensaje cálido y orientador.
2. CLASIFICAR el tipo de problema en una de estas categorías:
   - 'acceso': no puede entrar, cédula incorrecta, cambió número
   - 'contenido': no entiende el módulo, video no carga
   - 'tecnico': error del sistema, no recibe mensajes
   - 'otro': cualquier otra cosa
3. Para 'acceso' y 'contenido': RESOLVER directamente si puede dar una
   instrucción concreta.
4. Para 'tecnico' y 'otro': ESCALAR (marcar para revisión humana).

Reglas:
- Habla como colombiana, de usted, máximo 3 párrafos cortos.
- Si puede resolver, resuelva. No escale lo que pueda manejar.
- Termina SIEMPRE con: "Si necesita más ayuda escríbame de nuevo."
- Nunca prometa tiempos que no pueda cumplir.
- No invente datos del usuario (no diga su nombre si no se lo dieron).

Devuelve SIEMPRE un JSON válido con esta estructura exacta:
{
  "categoria": "acceso" | "contenido" | "tecnico" | "otro",
  "respuesta_whatsapp": "texto que se enviará al estudiante",
  "escalar": true | false,
  "nota_interna": "resumen breve para el equipo de soporte"
}
"""


CATEGORIAS_VALIDAS = {"acceso", "contenido", "tecnico", "otro"}


def procesar_pqrs_automatico(solicitud_soporte) -> dict[str, Any]:
    """Clasifica y responde una :class:`SolicitudSoporte` recién creada.

    Parameters
    ----------
    solicitud_soporte
        Instancia de ``core.SolicitudSoporte`` ya guardada en BD.

    Returns
    -------
    dict
        ``{categoria, respuesta_whatsapp, escalar, nota_interna}`` siempre
        bien formado. Si la llamada a OpenAI falla, devuelve un fallback
        que escala la solicitud sin romper el flujo.
    """
    mensaje_usuario = (
        getattr(solicitud_soporte, "mensaje_original", "") or ""
    ).strip()
    if not mensaje_usuario:
        return _fallback_escalar("Mensaje vacío en la solicitud")

    raw = _llamar_openai_pqrs(mensaje_usuario)
    if raw is None:
        return _fallback_escalar("OpenAI no disponible o falló la respuesta")

    return _parsear_respuesta_pqrs(raw)


def aplicar_resultado_pqrs(solicitud_soporte, resultado: dict[str, Any]) -> None:
    """Persiste la decisión del agente en la solicitud y la deja consistente."""
    from django.utils import timezone

    categoria = resultado.get("categoria", "")
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "otro"
    escalar = bool(resultado.get("escalar", True))
    nota = resultado.get("nota_interna") or ""

    solicitud_soporte.categoria = categoria
    solicitud_soporte.resuelto_por_agente = not escalar
    if escalar:
        solicitud_soporte.estado = "pendiente"
    else:
        solicitud_soporte.estado = "en_atencion"
        solicitud_soporte.fecha_atencion = timezone.now()
        solicitud_soporte.atendido_por = "Agente PQRS (IA)"
    if nota:
        solicitud_soporte.notas_internas = (
            f"{solicitud_soporte.notas_internas}\n[Agente PQRS] {nota}"
        ).strip()
    solicitud_soporte.save(
        update_fields=[
            "categoria",
            "resuelto_por_agente",
            "estado",
            "fecha_atencion",
            "atendido_por",
            "notas_internas",
        ]
    )


def disparar_agente_pqrs_async(solicitud_soporte, callback_envio_whatsapp=None) -> None:
    """Lanza el agente PQRS en un hilo aparte para no bloquear el webhook.

    ``callback_envio_whatsapp`` es opcional: si se entrega, se llama con
    ``(estudiante, texto_respuesta)`` para enviar la respuesta del agente
    por WhatsApp (Twilio). Si falla, el error se loguea sin romper.
    """

    def _worker():
        try:
            resultado = procesar_pqrs_automatico(solicitud_soporte)
            aplicar_resultado_pqrs(solicitud_soporte, resultado)
            if callback_envio_whatsapp and resultado.get("respuesta_whatsapp"):
                try:
                    callback_envio_whatsapp(
                        solicitud_soporte.estudiante,
                        resultado["respuesta_whatsapp"],
                    )
                except Exception as e:  # pragma: no cover — best-effort
                    logger.exception(
                        "[PQRS Agent] Error enviando respuesta WhatsApp: %s", e
                    )
        except Exception as e:  # pragma: no cover — best-effort
            logger.exception("[PQRS Agent] Error procesando solicitud: %s", e)

    t = threading.Thread(target=_worker, name="pqrs-agent", daemon=True)
    t.start()


# ----------------------------------------------------------------------
# Helpers internos
# ----------------------------------------------------------------------

def _llamar_openai_pqrs(mensaje_usuario: str) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[PQRS Agent] OPENAI_API_KEY no configurada; fallback escalar.")
        return None
    try:
        import openai  # type: ignore

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("PQRS_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": PQRS_SYSTEM_PROMPT},
                {"role": "user", "content": mensaje_usuario},
            ],
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning("[PQRS Agent] Error llamando OpenAI: %s", e)
        return None


def _parsear_respuesta_pqrs(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return _fallback_escalar("Respuesta del modelo no es JSON válido")

    categoria = (data.get("categoria") or "otro").strip().lower()
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "otro"

    respuesta = (data.get("respuesta_whatsapp") or "").strip()
    if not respuesta:
        return _fallback_escalar("Respuesta vacía del modelo")

    if "Si necesita más ayuda escríbame de nuevo." not in respuesta:
        respuesta = respuesta.rstrip() + "\n\nSi necesita más ayuda escríbame de nuevo."

    escalar_raw = data.get("escalar", True)
    if isinstance(escalar_raw, str):
        escalar = escalar_raw.strip().lower() in {"true", "1", "si", "sí", "yes"}
    else:
        escalar = bool(escalar_raw)

    if categoria in {"tecnico", "otro"}:
        escalar = True

    nota = (data.get("nota_interna") or "").strip()

    return {
        "categoria": categoria,
        "respuesta_whatsapp": respuesta,
        "escalar": escalar,
        "nota_interna": nota,
    }


def _fallback_escalar(motivo: str) -> dict[str, Any]:
    return {
        "categoria": "otro",
        "respuesta_whatsapp": (
            "🆘 Recibí su solicitud y la pasé a nuestro equipo. "
            "Le vamos a responder lo antes posible.\n\n"
            "Si necesita más ayuda escríbame de nuevo."
        ),
        "escalar": True,
        "nota_interna": f"[Fallback] {motivo}",
    }
