"""Identidad de Nati — bot comercial de eki con identidad colombiana.

Este módulo centraliza el system prompt del bot comercial. Permite:
1. Tener UNA fuente de verdad para la personalidad de Nati.
2. Concatenar instrucciones extra por cliente (campo `Cliente.system_prompt_extra`).
3. Mantener compatibilidad con el ajuste global vía `settings.BOT_COMERCIAL_SYSTEM_PROMPT_EXTRA`.

El nombre del bot también es configurable por cliente (`Cliente.nombre_bot`,
default `'Nati'`), de modo que el mismo motor pueda atender a varios clientes
con identidades diferentes (p. ej. `'Nati'` para Nitrofert, `'Aliada'` para
otro cliente) sin tocar código.
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings


NOMBRE_BOT_DEFAULT = "Nati"


NATI_SYSTEM_PROMPT_BASE = """\
Eres Nati, agrónoma virtual experta de eki para productores rurales colombianos.

IDENTIDAD:
- Eres agrónoma con profundo conocimiento de cultivos colombianos.
- Hablas colombiano: usas "usted" y conoces términos locales (arroba, bulto,
  costal, lote, rastrojo, jornal, beneficiadero, pulido, despulpado, voleo).
- Eres técnica pero accesible: cuando el productor no entiende algo técnico,
  lo explicas con analogías del campo.
- Nunca suenas como vendedora ni presionas. Si el productor pregunta por un
  curso, lo orientas con información. Si no pregunta, no lo mencionas.

CONOCIMIENTO TÉCNICO:
- Fertilización y nutrición de suelos
- Manejo integrado de plagas y enfermedades (MIP)
- Riego y drenaje
- Poscosecha y beneficio
- Variedades por región colombiana
- Buenas prácticas agrícolas (BPA)
- Huella de carbono y sostenibilidad agrícola
- Clima y siembra por regiones de Colombia
- Precios de referencia de insumos y productos
- Diagnóstico de síntomas de plantas (si describe o envía foto)

REGLAS DE RESPUESTA:
1. Si tienes información indexada oficial de eki: úsala primero.
2. Si no alcanza la información oficial: usa respaldo web priorizando Colombia.
3. Si preguntan precios actuales: aclara que son referencias sujetas a región.
4. Si envían foto: pide descripción de síntomas (color, textura, parte afectada).
5. Máximo 3 párrafos cortos por respuesta.
6. Termina siempre con una pregunta concreta o una acción sugerida.
7. Si no sabes algo: "No tengo esa información ahora, pero puedo ayudarle a buscarla. ¿Me puede dar más detalle?"
8. NUNCA menciones cursos, precios de eki o ventas salvo que el productor lo pida explícitamente.
9. Si el productor usa expresiones coloquiales, responde natural.
10. Recuerda lo conversado en esta sesión.

CONFIDENCIALIDAD TÉCNICA:
- NUNCA menciones al usuario términos internos como RAG, embeddings, vector,
  indexado, fragmentos, base interna o nombres de archivos.
- Si debes citar origen, di: "según la información oficial de eki".

SOBRE TI:
- Tu nombre es {nombre_bot}. Si te preguntan, dices que eres {nombre_bot},
  la agrónoma virtual de eki.
- NUNCA dices "soy el bot de eki".
- eki es la plataforma educativa. Tú eres {nombre_bot}.
"""


def armar_system_prompt(cliente=None, nombre_bot_override: Optional[str] = None) -> str:
    """Construye el system prompt completo para el bot comercial.

    Capas que se concatenan, en orden:
      1. NATI_SYSTEM_PROMPT_BASE (con `{nombre_bot}` interpolado).
      2. `cliente.system_prompt_extra` si se pasa un Cliente con ese campo.
      3. `settings.BOT_COMERCIAL_SYSTEM_PROMPT_EXTRA` (compat global).

    Args:
        cliente: instancia de `core.Cliente` o None. Si trae los campos
            `nombre_bot` y/o `system_prompt_extra`, se aplican.
        nombre_bot_override: nombre fijo a usar (gana sobre `cliente.nombre_bot`).

    Returns:
        El system prompt listo para inyectar como `{'role': 'system', 'content': ...}`.
    """
    nombre_bot = (
        (nombre_bot_override or '').strip()
        or (getattr(cliente, 'nombre_bot', '') or '').strip()
        or NOMBRE_BOT_DEFAULT
    )

    prompt = NATI_SYSTEM_PROMPT_BASE.format(nombre_bot=nombre_bot)

    extra_cliente = (getattr(cliente, 'system_prompt_extra', '') or '').strip()
    if extra_cliente:
        prompt = (
            f"{prompt}\n\n"
            f"Instrucciones específicas del cliente:\n{extra_cliente}"
        )

    extra_global = str(getattr(settings, 'BOT_COMERCIAL_SYSTEM_PROMPT_EXTRA', '') or '').strip()
    if extra_global:
        prompt = (
            f"{prompt}\n\n"
            f"Instrucciones adicionales del operador:\n{extra_global}"
        )

    return prompt


def obtener_nombre_bot(cliente=None) -> str:
    """Devuelve el nombre que debe usar el bot al firmar mensajes (default: Nati)."""
    return (getattr(cliente, 'nombre_bot', '') or '').strip() or NOMBRE_BOT_DEFAULT


def armar_saludo_inicial(cliente=None) -> str:
    """Saludo de bienvenida del bot comercial cuando el productor escribe por primera vez.

    Usa el `nombre_bot` del cliente si existe, de lo contrario "Nati".
    Reemplaza el saludo legacy "Hola, soy tu bot de EKI" para que la identidad
    coincida con el system prompt.
    """
    nombre = obtener_nombre_bot(cliente)
    return (
        f"¡Hola! Soy {nombre}, la asesora virtual de eki 🌱\n\n"
        "Le ayudo con consultas sobre su cultivo: nutrición, plagas, "
        "enfermedades, manejo y, si aplica, recomendaciones de catálogo.\n\n"
        "Cuénteme cuál es su cultivo y qué necesita resolver."
    )


def armar_saludo_menu(cliente=None) -> str:
    """Mensaje del bot comercial cuando el productor escribe 'menu' o 'listo'."""
    nombre = obtener_nombre_bot(cliente)
    return (
        f"👩‍🌾 *{nombre} — Asesora Técnica Agro IA*\n\n"
        "Le oriento primero en lo técnico de su cultivo y luego, si aplica, "
        "en opciones de catálogo.\n"
        "Cuénteme su cultivo y qué necesita resolver."
    )


def armar_messages_para_openai(
    sesion,
    nuevo_mensaje: str,
    cliente=None,
    max_pares: int = 10,
):
    """Construye `messages` para OpenAI con memoria de sesión deslizante."""
    messages = [{"role": "system", "content": armar_system_prompt(cliente=cliente)}]
    historial = list(getattr(sesion, "historial_mensajes", []) or [])
    ventana = historial[-(max_pares * 2):]
    for msg in ventana:
        if isinstance(msg, dict) and msg.get("role") in {"user", "assistant"}:
            messages.append({"role": msg["role"], "content": str(msg.get("content", ""))[:3000]})
    messages.append({"role": "user", "content": (nuevo_mensaje or "")[:5000]})
    return messages


def buscar_en_web_colombia(query: str, max_fuentes: int = 3) -> str:
    """
    Fallback web para Nati con prioridad Colombia.
    Usa OpenAI tools web_search cuando está disponible.
    """
    if not bool(getattr(settings, "BOT_COMERCIAL_WEB_FALLBACK_ENABLED", True)):
        return ""

    api_key = (getattr(settings, "OPENAI_API_KEY", None) or "").strip()
    if not api_key:
        return ""

    try:
        from openai import OpenAI
    except Exception:
        return ""

    consulta = (query or "").strip()
    if not consulta:
        return ""
    consulta = f"{consulta} Colombia agricultura ICA Agrosavia Cenicafe Cenicana MADR"

    client = OpenAI(api_key=api_key)
    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            tools=[{"type": "web_search_preview"}],
            input=(
                "Busque fuentes técnicas para productores colombianos y resuma máximo "
                f"{max_fuentes} referencias útiles. Priorice Colombia. "
                f"Consulta: {consulta}"
            ),
            temperature=0,
        )
        texto = (getattr(resp, "output_text", "") or "").strip()
        return texto[:1800]
    except Exception:
        return ""
