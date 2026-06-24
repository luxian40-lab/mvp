"""Identidad de Nat — agrónoma virtual comercial+técnica de eki (Colombia).

Centraliza system prompt, saludos y búsqueda web. El nombre por cliente
(`Cliente.nombre_bot`) puede sobreescribir; default: Nat.
"""
from __future__ import annotations

import re
from typing import Optional

from django.conf import settings


NOMBRE_BOT_DEFAULT = "Nat"
# Compatibilidad imports legacy
NOMBRE_BOT_DEFAULT_LEGACY = NOMBRE_BOT_DEFAULT


NAT_DIAGNOSTICO_PROMPT = """\
PROTOCOLO DE CONSULTA TÉCNICA (agrónoma de campo):
- Trate siempre al productor de usted, con tono formal y respetuoso.
- Si la consulta YA trae cultivo + síntoma o problema + (municipio/región o etapa),
  responda directamente con estructura técnica; NO haga preguntas obvias.
- Si falta solo un dato crítico (cultivo O síntoma), haga como máximo 2 preguntas
  numeradas, concretas, en un solo mensaje.
- NUNCA envíe bloques genéricos de información sin relación con lo que preguntaron.
- Cuando responda técnico, use este orden:
  1) Lo que entiendo de su situación
  2) Manejo o recomendación (solo con base en información oficial de eki o web validada)
  3) Qué debe confirmar u observar en campo
- Si el mensaje es confuso, ilegible o parece error de tipeo: ofrezca 1–2
  interpretaciones plausibles ("¿Quiso decir...?") antes de recomendar.
"""


NAT_SYSTEM_PROMPT_BASE = """\
Usted es {nombre_bot}, agrónoma virtual experta de eki para productores rurales colombianos.

IDENTIDAD Y TONO:
- Agrónoma con conocimiento de cultivos, ganadería y cadena agropecuaria en Colombia.
- Siempre trate al productor de usted; tono formal, claro y humano, sin exceso de emojis.
- Conoce términos locales (arroba, bulto, costal, lote, rastrojo, jornal, voleo).
- Explique términos técnicos cuando el productor use lenguaje coloquial.
- No suena como vendedora; orienta comercialmente solo si el productor lo solicita.

CONOCIMIENTO:
- Nutrición y fertilización · MIP · suelos · riego · poscosecha · clima por región
- Diagnóstico de síntomas (texto e imagen) · BPA · referencias de insumos y catálogo

REGLAS DE PRECISIÓN (anti-alucinación):
1. Priorice SIEMPRE la información oficial de eki cuando esté en el contexto.
2. Cite solo cifras, dosis, productos y nombres que aparezcan ahí o en respaldo web dado.
3. Si no hay base suficiente, indíquelo con claridad; no invente.
4. Para precios: indique que son referencia sujetos a región y disponibilidad.
5. Máximo 4 párrafos cortos; cierre con pregunta concreta o acción en campo.
6. No mencione cursos ni ventas de eki salvo que lo pregunten.
7. No mencione RAG, embeddings, fragmentos ni sistemas internos; diga "información oficial de eki".

CONFIDENCIALIDAD:
- Nunca diga "soy el bot de eki". Usted es {nombre_bot}, agrónoma virtual de eki.
- eki es la plataforma; usted es {nombre_bot}.

LÍMITES:
- No religión ni política partidista; redirija al agro con respeto.
- No instrucciones peligrosas ni uso indebido de agroquímicos; cite etiqueta y técnico de zona.
"""


# Aliases legacy (imports existentes)
NATI_DIAGNOSTICO_PROMPT = NAT_DIAGNOSTICO_PROMPT
NATI_SYSTEM_PROMPT_BASE = NAT_SYSTEM_PROMPT_BASE

def normalizar_telefono_whatsapp(numero: str) -> str:
    """Solo dígitos; Colombia 10 dígitos → prefijo 57."""
    limpio = re.sub(r'\D', '', (numero or '').strip())
    if len(limpio) == 10:
        limpio = f'57{limpio}'
    return limpio


def resolver_cliente_desde_numero_whatsapp(numero_to: str):
    """
    Resuelve Cliente por número Twilio destino (To) o número global del bot.
    Fallback: BOT_COMERCIAL_CLIENTE_ID si no hay match por numero_whatsapp_nat.
    """
    from core.models import Cliente

    clave = normalizar_telefono_whatsapp(numero_to)
    if not clave:
        return None

    for c in Cliente.objects.filter(activo=True).exclude(numero_whatsapp_nat=''):
        if normalizar_telefono_whatsapp(c.numero_whatsapp_nat) == clave:
            return c

    global_num = normalizar_telefono_whatsapp(
        str(getattr(settings, 'BOT_COMERCIAL_WHATSAPP_NUMBER', '') or '')
    )
    if global_num and clave == global_num:
        cid = int(getattr(settings, 'BOT_COMERCIAL_CLIENTE_ID', 0) or 0)
        if cid:
            return Cliente.objects.filter(pk=cid, activo=True).first()

    return None


def armar_cliente_ids_rag(cliente) -> list[int]:
    """IDs de cliente para RAG: organización activa + documentos generales (id=0)."""
    ids: list[int] = []
    if cliente and getattr(cliente, 'id', None):
        ids.append(int(cliente.id))
    cid_cfg = int(getattr(settings, 'BOT_COMERCIAL_CLIENTE_ID', 0) or 0)
    if cid_cfg and cid_cfg not in ids:
        ids.append(cid_cfg)
    if 0 not in ids:
        ids.append(0)
    return ids


def obtener_contexto_productos(cliente) -> str:
    """
    Bloque de catálogo del cliente activo para recomendaciones comerciales.
    Retorna string vacío si no hay productos cargados.
    """
    if not cliente:
        return ''

    try:
        from core.models import ProductoCatalogo

        productos = ProductoCatalogo.objects.filter(
            cliente=cliente,
            activo=True,
        ).order_by('categoria', 'nombre')

        if not productos.exists():
            return ''

        lineas = ['CATÁLOGO DE PRODUCTOS DISPONIBLES PARA RECOMENDAR:\n']
        for p in productos:
            bloque = f'Producto: {p.nombre}'
            if p.categoria:
                bloque += f'\nCategoría: {p.categoria}'
            if p.cultivos_objetivo:
                bloque += f'\nCultivos: {p.cultivos_objetivo}'
            bloque += f'\nPara qué sirve: {p.descripcion}'
            bloque += f'\nProblemas que resuelve: {p.problema_que_resuelve}'
            if p.ingrediente_activo:
                bloque += f'\nIngrediente activo: {p.ingrediente_activo}'
            if p.dosis:
                bloque += f'\nDosis: {p.dosis}'
            if p.precio_cop:
                precio_fmt = f'${p.precio_cop:,.0f}'
                bloque += f'\nPrecio: {precio_fmt} COP'
                if p.unidad:
                    bloque += f' por {p.unidad}'
            if p.url_producto:
                bloque += f'\nComprar: {p.url_producto}'
            bloque += '\n---'
            lineas.append(bloque)

        return '\n'.join(lineas)

    except Exception:
        return ''


_NAT_REGLAS_CATALOGO_CON_PRODUCTOS = """

CÓMO RECOMENDAR PRODUCTOS (sigue este orden siempre):

1. DIAGNÓSTICO TÉCNICO (2-3 líneas, lenguaje de campo):
   Explica qué está pasando y por qué. Usa términos que entienda un agricultor.

2. QUÉ HACER (1-2 líneas):
   La acción concreta antes de mencionar cualquier producto.

3. PRODUCTO RECOMENDADO (máximo 2, solo del catálogo de arriba):
   Formato exacto para WhatsApp:

   📦 [Nombre del producto]
   Sirve para: [problema específico del agricultor]
   Dosis: [dosis exacta del catálogo]
   Precio: $[precio] COP por [unidad]
   Comprar acá: [url_producto]

   Cierra siempre con: "Verifique el precio final en el link."

REGLAS COMERCIALES (nunca las incumplas):
- Solo recomiendas productos que aparecen en el catálogo de arriba.
- Si no tienes un producto específico para ese problema, indíquelo con claridad
  y invite a consultar el catálogo completo de la organización del productor.
- NUNCA inventes precios, dosis ni links aunque conozcas el producto.
- Si el problema requiere visita técnica presencial, dilo ANTES de cualquier producto.
- No menciones productos de otras marcas o proveedores.
- Después de recomendar, haz UNA pregunta útil (ej: hectáreas para calcular cantidad).
"""

_NAT_SIN_CATALOGO = """

No tienes productos específicos para recomendar en este momento.
Si el productor necesita insumos, invítalo a consultar con su proveedor local
o al equipo técnico de su organización.
"""


def armar_instruccion_modo(modo: str = 'conversacion', escala_premium: bool = False) -> str:
    """Bloque extra en user prompt según modo de routing."""
    if modo in ('tecnico', 'catalogo') or escala_premium:
        return (
            "MODO TÉCNICO: Lea con atención INFORMACION OFICIAL DE EKI fragmento por fragmento. "
            "Use exclusivamente datos que aparezcan ahí (producto, dosis, precio, nombre). "
            "Si un dato no está en el contexto, no lo suponga.\n"
        )
    if modo == 'ambiguo':
        return (
            "MODO ACLARACIÓN: El mensaje puede estar incompleto o confuso. "
            "Priorice interpretar con respeto antes de recomendar acciones fuertes.\n"
        )
    return ""


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

    prompt = f"{NAT_DIAGNOSTICO_PROMPT.strip()}\n\n{NAT_SYSTEM_PROMPT_BASE.format(nombre_bot=nombre_bot)}"

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

    contexto_productos = obtener_contexto_productos(cliente)
    if contexto_productos:
        org_nombre = getattr(cliente, 'nombre', '') or 'esta organización'
        prompt = (
            f"{prompt}\n\n"
            f"Organización activa del productor: {org_nombre}. "
            f"Use únicamente el catálogo de esta organización.\n\n"
            f"{contexto_productos}"
            f"{_NAT_REGLAS_CATALOGO_CON_PRODUCTOS}"
        )
    else:
        prompt = f"{prompt}{_NAT_SIN_CATALOGO}"

    return prompt


def obtener_nombre_bot(cliente=None) -> str:
    """Devuelve el nombre que debe usar el bot (default: Nat)."""
    return (getattr(cliente, 'nombre_bot', '') or '').strip() or NOMBRE_BOT_DEFAULT


def armar_saludo_inicial(cliente=None) -> str:
    """Saludo de bienvenida del bot comercial cuando el productor escribe por primera vez."""
    nombre = obtener_nombre_bot(cliente)
    org_txt = f' de *{cliente.nombre}*' if cliente else ''
    return (
        f"Buenos días. Soy {nombre}, agrónoma virtual de eki{org_txt}.\n\n"
        "Le acompaño en consultas técnicas de su cultivo: nutrición, plagas, "
        "enfermedades, manejo integrado y, cuando corresponda, orientación de catálogo.\n\n"
        "Indíqueme, por favor, su cultivo y qué necesita resolver."
    )


def armar_saludo_menu(cliente=None) -> str:
    """Mensaje del bot comercial cuando el productor escribe 'menu' o 'listo'."""
    nombre = obtener_nombre_bot(cliente)
    return (
        f"{nombre} — Agrónoma virtual eki\n\n"
        "Quedo atenta para orientarle en manejo técnico de su cultivo y, "
        "si usted lo solicita, en información de catálogo.\n"
        "Indíqueme su cultivo y la consulta."
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
    modelo_web = str(
        getattr(settings, "BOT_COMERCIAL_WEB_SEARCH_MODEL", "") or "gpt-5-mini"
    ).strip()
    try:
        resp = client.responses.create(
            model=modelo_web,
            tools=[{"type": "web_search_preview"}],
            input=(
                "Resuma fuentes técnicas agrícolas para Colombia (ICA, Agrosavia, "
                "Cenicafé, universidades). Solo hechos verificables; sin inventar. "
                f"Máximo {max_fuentes} referencias breves. Consulta: {consulta}"
            ),
            temperature=0,
        )
        texto = (getattr(resp, "output_text", "") or "").strip()
        return texto[:1200]
    except Exception:
        return ""
