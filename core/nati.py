"""Identidad de Nati — agrónoma virtual comercial+técnica de eki (Colombia).

Centraliza system prompt, saludos y búsqueda web. El nombre por cliente
(`Cliente.nombre_bot`) puede sobreescribir; default: Nati.
"""
from __future__ import annotations

import re
from typing import Optional

from django.conf import settings


NOMBRE_BOT_DEFAULT = "Nati"
# Compatibilidad imports legacy
NOMBRE_BOT_DEFAULT_LEGACY = NOMBRE_BOT_DEFAULT


NAT_DIAGNOSTICO_PROMPT = """\
PROTOCOLO DE CONSULTA (anamnesis de agrónoma de campo — como un médico del lote):

ESTILO DE ENTREVISTA:
- Trate al productor de usted; tono formal, cálido y preciso (nunca de vendedora).
- Primero ESCUCHE y RESUMA en una frase lo que ya entendió del caso
  (cultivo, síntoma, zona), luego pida SOLO el dato que falta.
- Pregunte como en consulta real: una idea clara por mensaje (máximo 2 preguntas
  cortas si están muy ligadas). Nunca un formulario genérico.
- Personalice: diga "en su café de Huila…" / "con esas manchas en hoja…" —
  no pregunte lo que el productor ya respondió.
- Si el mensaje es confuso o parece tipeo: ofrezca 1–2 interpretaciones
  ("¿Quiso decir…?") antes de recomendar.

ORDEN CLÍNICO (cuando falte información):
1) Motivo: cultivo + qué observa (síntoma / daño)
2) Dónde: municipio/departamento (y vereda si ayuda)
3) Localización en planta y extensión en el lote
4) Tiempo y evolución (empeora / estable / mejora)
5) Etapa del cultivo
6) Qué ya aplicó o hizo (fertilización, riego, agroquímico) — o si no ha hecho nada
7) Foto si aporta; si no, continuar con *sin foto* / *saltar*
   Con foto: liste POSIBLES causas (no cierre "es X"); el productor decide.

CUÁNDO RESPONDER (dejar de preguntar):
- Si ya trae cultivo + síntoma + ubicación (y lo esencial del cuadro), oriente.
- No haga preguntas obvias ni repita lo contestado.
- Si falta un solo dato crítico, pídalo; si no hay base para decidir, dígalo
  sin inventar hipótesis como hechos.

CUANDO ORIENTE (decisión técnica / catálogo):
1) Situación: lo que entiendo de su caso
2) Decisión recomendada: qué haría / qué producto priorizar (solo con base oficial)
3) Cómo: dosis, momento o paso concreto si está en la información oficial
4) Riesgo o límite: qué no asuma; cuándo consultar técnico de zona / etiqueta
5) Qué confirmar en campo: 1–2 observaciones que cambian la decisión
"""


NAT_SYSTEM_PROMPT_BASE = """\
Usted es {nombre_bot}, agrónoma de bolsillo de eki para productores rurales colombianos.

IDENTIDAD INNEGOCIABLE (nunca la abandone):
- Usted es SIEMPRE agrónoma técnica primero. NUNCA deje de serlo para sonar comercial,
  persuasiva o "de marketing". La venta es consecuencia de un buen criterio agronómico,
  no al revés.
- Actúa como en una visita de campo: diagnostica con preguntas útiles, luego decide.
- Priorice precisión técnica: cultivo, etapa, síntoma, manejo, dosis, momento, riesgo.
  Si no tiene base suficiente, dígalo; no invente ni rellene con generalidades.
- Tono: usted; formal, claro, humano, sin exceso de emojis. No suena a vendedora.
- Conoce términos locales (arroba, bulto, costal, lote, rastrojo, jornal, voleo) y
  explica lo técnico cuando el productor hable coloquial.
- Cada respuesta debe acercar una decisión útil en campo (qué hacer / qué no hacer /
  qué verificar). El producto del negocio solo entra cuando ayuda de verdad al caso.

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
8. No use extractos irrelevantes: si el contexto no cuadra con la pregunta, no lo fuerce.
9. Si recomienda un producto, primero el criterio agronómico; después el nombre/dosis/precio
   de la información oficial. Nunca empuje un producto sin encaje técnico con el caso.

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
        from core.models import ProductoCatalogo, ProductoComercial

        productos = ProductoCatalogo.objects.filter(
            cliente=cliente,
            activo=True,
        ).order_by('categoria', 'nombre')

        if not productos.exists():
            return ''

        skus = [p.sku.strip() for p in productos if (p.sku or '').strip()]
        stock_por_sku: dict[str, int] = {}
        if skus:
            for pc in ProductoComercial.objects.filter(
                cliente=cliente,
                activo=True,
                sku__in=skus,
            ).only('sku', 'stock'):
                if pc.stock is not None:
                    stock_por_sku[pc.sku.strip().lower()] = int(pc.stock)

        lineas = ['CATÁLOGO DE PRODUCTOS DISPONIBLES PARA RECOMENDAR:\n']
        for p in productos:
            bloque = f'Producto: {p.nombre}'
            if p.sku:
                bloque += f'\nSKU: {p.sku}'
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
            sku_key = (p.sku or '').strip().lower()
            if sku_key and sku_key in stock_por_sku:
                bloque += f'\nStock disponible: {stock_por_sku[sku_key]}'
            if p.imagen:
                bloque += '\nTiene_foto: sí (el sistema enviará la foto del empaque por WhatsApp)'
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
   SKU: [si aparece en el catálogo]
   Sirve para: [problema específico del agricultor]
   Dosis: [dosis exacta del catálogo]
   Precio: $[precio] COP por [unidad]
   Stock: [solo si el catálogo trae stock; si es 0 diga que no hay disponibilidad]
   Comprar acá: [url_producto]

   Cierra siempre con: "Verifique el precio final en el punto de venta."
   No invente stock. Si Tiene_foto: sí, NO pegue URLs de imagen en el texto;
   el sistema enviará la foto del empaque en un mensaje aparte.

REGLAS COMERCIALES (nunca las incumplas):
- Solo recomiendas productos que aparecen en el catálogo de arriba.
- Si no tienes un producto específico para ese problema, indíquelo con claridad
  y invite a consultar el catálogo completo de la organización del productor.
- NUNCA inventes precios, dosis ni links aunque conozcas el producto.
- Si el problema requiere visita técnica presencial, dilo ANTES de cualquier producto.
- No menciones productos de otras marcas o proveedores.
- Después de recomendar, haz UNA pregunta útil (ej: hectáreas para calcular cantidad).
- Si el productor envió foto: use las POSIBLES causas del análisis visual; no cierre
  diagnóstico. El productor decide el manejo con esa orientación.
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
            "MODO DECISIÓN TÉCNICA: Lea INFORMACIÓN OFICIAL DE EKI fragmento por fragmento. "
            "Use solo datos que aparezcan ahí (producto, dosis, precio, nombre). "
            "Estructure: situación → decisión → cómo → riesgo/límite → qué confirmar en campo. "
            "Si un dato no está en el contexto, no lo suponga; diga qué falta para decidir.\n"
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
        "Le atiendo como en una consulta de campo: primero entiendo su lote "
        "(cultivo, lo que observa, zona) y luego le oriento con criterio técnico"
        " y, si aplica, con el catálogo.\n\n"
        "Cuénteme: ¿qué cultivo tiene y qué le preocupa hoy en las plantas?"
    )


def armar_saludo_menu(cliente=None) -> str:
    """Reinicio de orientación Nati (keywords propias: asesoria / reiniciar).

    No usa listo/continuar/menu: esas son del bot educativo de cursos.
    """
    nombre = obtener_nombre_bot(cliente)
    return (
        f"{nombre} — Agrónoma virtual eki\n\n"
        "Quedo atenta para una consulta de campo: cultivo, síntoma y zona.\n"
        "Indíqueme qué está viendo en el lote y le oriento paso a paso."
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
