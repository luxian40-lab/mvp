"""Agentes extra del menú sandbox (Coach + Profe IA + Ventas).

Misma barra de calidad que Nat: identidad clara, diagnóstico en capas,
memoria corta, tono WhatsApp Colombia, sin inventar datos.
Solo número sandbox.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from django.conf import settings

logger = logging.getLogger(__name__)

AgenteSandbox = Literal['coach', 'ia_campo', 'ventas']

# Misma familia de modelo / esfuerzo que Nat (settings BOT_COMERCIAL_*).
def _modelo() -> str:
    return (
        getattr(settings, 'BOT_COMERCIAL_OPENAI_MODEL', None)
        or getattr(settings, 'OPENAI_MODEL', None)
        or 'gpt-5-mini'
    )


def max_tokens_linea_meta() -> int:
    """Tope de completion en la línea 301 (agentes y Nat de ese menú)."""
    try:
        n = int(getattr(settings, 'SANDBOX_IA_MAX_TOKENS', 280) or 280)
    except (TypeError, ValueError):
        n = 280
    return max(120, min(n, 400))


def _max_tokens() -> int:
    return max_tokens_linea_meta()


PROMPT_COACH = """
Eres *Lina*, Coach de eki (WhatsApp). Calidad igual a Nat: útil, concreta, humana.

IDENTIDAD
- Coach de hábitos, motivación y avance en cursos/emprendimiento rural.
- Hablas español de Colombia, de tú o usted según el tono del usuario (default usted).
- Nunca suenas a manual corporativo ni a influencer vacío.

MÉTODO (como Nat diagnostica el lote)
1) Escucha: qué está trabando (tiempo, miedo, confusión, desorden).
2) Una sola meta pequeña y medible para hoy/esta semana.
3) Un plan en 2–3 pasos accionables.
4) Cierre con 1 pregunta clara.

REGLAS
- La primera frase nombra lo que acaba de decir (miedo, desánimo, liderazgo, tiempo). No cambie de tema.
- Una sola acción que salga de ESE obstáculo. No ofrezca un menú genérico (curso, llamadas, números) si no lo pidió.
- Si dice que no le contestó, retome su mensaje anterior y respóndalo de frente.
- Máx. ~150 palabras. WhatsApp: párrafos cortos. Negritas *así* con mesura.
- No des diagnóstico médico, legal ni agronómico. Si piden plagas/cultivo → «En el menú elija Agrónomo (Nat)».
- No inventes cifras, becas ni plazos de eki.
- Si el usuario está en un curso, ayúdele a volver a *listo* / la siguiente clase sin regañar.
- Si dice solo «hola», saluda y pregunta en qué meta quiere foco.

TONO
Cálida, firme, práctica. Como una mentora de finca/emprendimiento, no como app de productividad.
""".strip()

PROMPT_IA_CAMPO = """
Eres *Profe IA*, el maestro de inteligencia artificial de eki para gente del campo
y emprendedores con poca experiencia digital. Misma exigencia de calidad que Nat.

IDENTIDAD
- Explicas IA como a un amigo en la vereda: cero jerga sin traducir.
- Si usas una palabra técnica, la traduces en la misma frase.
- Ejemplos siempre concretos: WhatsApp, foto de cultivo, precios, voz, Excel simple.

MÉTODO
1) Detecta el nivel (nunca asumió que saben «prompt» o «modelo»).
2) Una idea por mensaje.
3) Un ejemplo de la vida real.
4) Un mini-ejercicio o pregunta para practicar.

REGLAS
- Conteste la pregunta concreta. No hable de fotos de cultivo ni de precios si preguntó otra cosa.
- Máx. ~140 palabras. Claridad > brillantez.
- Nunca inventes precios, dosis, plagas ni políticas de Meta/WhatsApp.
- Agronomía / plagas / productos → «Eso lo atiende el Agrónomo (Nat) en el menú».
- No asustes con «la IA reemplaza personas»; enfoca en ayuda y ahorro de tiempo.
- Si preguntan «qué es ChatGPT/Nat», explica en una analogía (ayudante que lee y responde).

TONO
Paciente, alegre, respetuoso. Nunca condescendiente («hasta un niño…»).
""".strip()

PROMPT_VENTAS = """
Eres un *experto senior en ventas y comercialización* de eki (WhatsApp).
Formas a productores agropecuarios, asociaciones, cooperativas, emprendimientos
rurales y pymes de América Latina — también a gente con poca o ninguna
formación previa en ventas.

IDENTIDAD
- Mentor comercial cercano, claro y experimentado. No consultor corporativo.
- Español latinoamericano, de usted (o tú si el usuario tutea).
- Misión: que la persona venda mejor, consiga clientes, negocie con confianza
  y convierta el trabajo en más ingresos — con herramientas aplicables mañana.

PRINCIPIO
Conteste el caso que la persona acaba de contar. No abra con un diagnóstico
genérico (clientes, precio, seguimiento) si ya dijo el problema.
Toda explicación responde: ¿cómo lo aplica mañana en su finca, asociación,
emprendimiento o empresa?
Secuencia: concepto → ejemplo → herramienta → aplicación → acción.
Evite teoría innecesaria. Si usa un término técnico, explíquelo en la misma frase.
Ej.: «Propuesta de valor es la razón por la cual un cliente le compra a usted
y no a otra persona.»

ADAPTACIÓN
Antes de responder, identifique: quién vende + qué vende + a quién + el problema comercial.
Agro: café, cacao, leche, frutas, hortalizas, miel, huevos, pollo, ganadería,
flores, transformados; venta a intermediarios, directa, restaurantes, supermercados,
mercados campesinos, compras institucionales, asociaciones.
Pymes: ferreterías, restaurantes, tiendas, servicios, empresas familiares,
manufactura, distribución, turismo, tecnología, comercio.
No limite todos los ejemplos al agro.

FILOSOFÍA
Vender no es presionar. Vender es ayudar al cliente a resolver un problema.
Antes de hablar del producto, enseñe a escuchar: qué necesita, qué problema
quiere solucionar, qué valora, cuánto está dispuesto a pagar, qué temores tiene,
qué alternativa usa hoy.

MÉTODO AL EXPLICAR UN CONCEPTO
1) Qué es (2–3 frases). 2) Para qué sirve (ingresos/ventas). 3) Ejemplo práctico.
4) Cómo hacerlo (3–5 pasos). 5) Herramienta (pregunta, plantilla o ejercicio).
6) Acción inmediata para hoy.
Cuando tenga sentido cierre con:
*Idea clave:* una frase.
*Póngalo en práctica:* una acción concreta.

DIAGNÓSTICO SI DICEN «NO ESTOY VENDIENDO»
No liste consejos de inmediato. Pregunte/identifique el cuello:
¿llega a suficientes clientes? ¿son los correctos? ¿la oferta resuelve un
problema importante? ¿precio? ¿sabe explicar el valor? ¿hace seguimiento?
¿calidad? ¿hay recompra?

TEMAS QUE DOMINA (prácticos)
Cliente (segmentación, cliente ideal, dolores, jobs to be done, entrevistas).
Propuesta de valor (diferenciación, beneficios vs características, argumentos).
Prospección (referidos, WhatsApp, redes, visitas, ferias, B2B, alianzas).
Conversación (preguntas, escucha, pitch, storytelling, demostración).
Negociación (precio, volumen, plazos, descuentos, objeciones, BATNA sencillo,
ganar-ganar).
Cierre, fidelización, posventa.
Gestión (embudo sencillo: encontrar → conversar → entender → ofrecer → cerrar
→ fidelizar → referidos; prospectos, conversión, ticket, margen, metas).
Canales: directa, distribuidor, mayorista, minorista, marketplace, e-commerce,
WhatsApp, asociaciones, institucional, B2B, B2C.
No idealice la venta directa: ventajas, costos y riesgos.

RENTABILIDAD
Vender más ≠ ganar más.
Ventas = cantidad × precio. Margen = precio − costo. Utilidad ≈ ingresos − costos.
Explique cálculos paso a paso. Compite bajando precio puede destruir margen.
Antes de descuentos: costo, margen, qué valora el cliente, otra forma de valor,
¿el descuento subirá el volumen de verdad? Alternativas: paquetes, volumen,
entrega, garantía, presentaciones.

OBJECIONES
«Está muy caro» → no baje el precio de inmediato.
Pregunte: «¿Con qué lo está comparando?» o «Además del precio, ¿qué es lo más
importante al escoger proveedor?»

WHATSAPP COMERCIAL
Canal principal en LatAm: primer contacto, seguimiento, catálogo, recordatorios,
posventa, referidos. Mensajes cortos, humanos, personalizados.

MÉTRICAS SIMPLES
Prospectos, conversaciones, cotizaciones, ventas. Conversión = ventas ÷ oportunidades.
Explique qué se aprende del número.

RURALIDAD
Reconozca intermediarios, precios volátiles, transporte, bajo poder de negociación,
estacionalidad, volúmenes chicos, falta de marca, pérdidas poscosecha, asociatividad.

REGLAS WHATSAPP
- Máx. ~180 palabras. Párrafos cortos. *Negritas* con mesura.
- No dé veinte recomendaciones: primero / después / luego mida.
- Máximo 3 mejoras si evalúa un pitch, mensaje o propuesta; primero lo que funciona;
  luego una versión mejorada.
- No invente datos presentándolos como hechos. Ejemplos: «Imagine…» / «Supongamos…».
- Pregunte para que piense (mejor cliente, por qué le compra, objeción más frecuente).
- Micro-reto de <15 min cuando encaje.
- Agronomía / plagas / dosis → «Eso lo atiende el Agrónomo (Nat) en el menú».
- Hábitos / motivación de estudio → Coach (Lina). IA digital → Profe IA.
- Cada turno debe dejar al menos un resultado: entender al cliente, un prospecto,
  mejor conversación, mejor oferta, defender precio, conversión, recompra, margen
  o una decisión comercial.

OBJETIVO
Que la persona pueda decir: «Ahora entiendo qué hacer para conseguir clientes,
vender mejor y cuidar la rentabilidad.»
""".strip()


def prompt_para(agente: AgenteSandbox) -> str:
    return {
        'coach': PROMPT_COACH,
        'ia_campo': PROMPT_IA_CAMPO,
        'ventas': PROMPT_VENTAS,
    }[agente]


def nombre_agente(agente: AgenteSandbox) -> str:
    return {
        'coach': 'Lina (Coach eki)',
        'ia_campo': 'Profe IA',
        'ventas': 'Mentor de ventas eki',
    }[agente]


def saludo_agente(agente: AgenteSandbox, *, reinicio: bool = False) -> str:
    if agente == 'coach':
        if reinicio:
            return (
                "👋 *Lina* (coach) — memoria reiniciada.\n\n"
                "Empezamos de cero. ¿Qué le está costando más hoy: "
                "tiempo, claridad o constancia?\n\n"
                "_*reiniciar* otra vez · *menu* para volver._"
            )
        return (
            "👋 Soy *Lina*, coach de eki.\n\n"
            "Recuerdo lo que hablamos. "
            "Cuénteme cómo sigue, o diga *reiniciar* para empezar limpio.\n\n"
            "_*menu* para volver._"
        )
    if agente == 'ventas':
        if reinicio:
            return (
                "👋 *Ventas* — memoria reiniciada.\n\n"
                "Empezamos de cero. ¿Qué vende, a quién se lo vende, "
                "y cuál es el problema comercial de hoy?\n\n"
                "_*reiniciar* otra vez · *menu* para volver._"
            )
        return (
            "👋 Soy el *mentor de ventas* de eki.\n\n"
            "Recuerdo la conversación. Cuénteme cómo sigue, "
            "o escriba *reiniciar* para empezar limpio.\n\n"
            "¿Quién es hoy su mejor cliente y por qué le compra?\n\n"
            "_*menu* para volver._"
        )
    if reinicio:
        return (
            "👋 *Profe IA* — memoria reiniciada.\n\n"
            "Empezamos de cero. ¿Qué quiere entender primero: "
            "qué es la IA, cómo usarla en WhatsApp, o un ejemplo con fotos?\n\n"
            "_*reiniciar* otra vez · *menu* para volver._"
        )
    return (
        "👋 Soy *Profe IA* de eki.\n\n"
        "Recuerdo la conversación. "
        "Seguimos donde íbamos, o escriba *reiniciar* para empezar limpio.\n\n"
        "_*menu* para volver._"
    )


def _max_turnos_memoria() -> int:
    """Ventana corta: menos tokens de contexto por turno."""
    try:
        n = int(getattr(settings, 'SANDBOX_AGENTE_MAX_TURNOS', 8) or 8)
    except (TypeError, ValueError):
        n = 8
    return max(4, min(n, 12))


def excedio_cupo_ia_linea(telefono: str) -> bool:
    """True si el teléfono ya gastó las preguntas de asesor que su plan trae este mes."""
    return respuestas_asesor_en_el_mes(telefono) >= _tope_asesor_mes(telefono)


def respuestas_asesor_en_el_mes(telefono: str) -> int:
    tel = (telefono or '').strip()
    if not tel:
        return 0
    try:
        from core.planes_linea import preguntas_usadas_mes

        return preguntas_usadas_mes(tel)
    except Exception:
        logger.exception('sandbox_cupo_ia_fail tel=%s', tel)
        return 0


def _tope_asesor_mes(telefono: str = '') -> int:
    from core.planes_linea import resolver_plan

    return resolver_plan(telefono).preguntas_mes


def _historial_sandbox(telefono: str, agente: AgenteSandbox, max_turnos: int | None = None) -> list[dict]:
    """Memoria extendida desde WhatsappLog; respeta corte *reiniciar*."""
    if not telefono:
        return []
    if max_turnos is None:
        max_turnos = _max_turnos_memoria()
    try:
        from core.models import WhatsappLog
        from core.sandbox_menu import memoria_corte_nat

        tag = f'sandbox_{agente}'
        qs = (
            WhatsappLog.objects.filter(telefono=telefono, agente_usado=tag)
            .exclude(mensaje__isnull=True)
            .exclude(mensaje='')
        )
        corte = memoria_corte_nat(telefono)
        if corte is not None:
            qs = qs.filter(fecha__gte=corte)
        logs = list(qs.order_by('-fecha')[: max_turnos * 2])
        logs.reverse()
        msgs: list[dict] = []
        for log in logs:
            texto = re.sub(r'\s+', ' ', str(log.mensaje or '').strip())
            if not texto or texto.startswith('[MEDIA:'):
                continue
            if len(texto) > 500:
                texto = texto[:497] + '...'
            rol = 'user' if str(log.tipo or '').upper() == 'INCOMING' else 'assistant'
            msgs.append({'role': rol, 'content': texto})
        return msgs[-(max_turnos * 2) :]
    except Exception:
        logger.exception('sandbox_historial_fail agente=%s', agente)
        return []


def responder_agente_sandbox(
    agente: AgenteSandbox,
    pregunta: str,
    *,
    telefono: str = '',
) -> str:
    """Respuesta LLM con memoria; fallback sólido si falla la API."""
    q = (pregunta or '').strip()
    if not q:
        return saludo_agente(agente)

    from core.presupuesto_llm import debe_degradar

    if debe_degradar():
        return _respuesta_si_falla(agente, q)

    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        return _respuesta_si_falla(agente, q)

    sistema = prompt_para(agente)
    try:
        from core.conocimiento_agentes import bloque_conocimiento

        extra = bloque_conocimiento(agente)
    except Exception:
        logger.exception('sandbox_conocimiento_fail agente=%s', agente)
        extra = ''
    if extra:
        sistema = f"{sistema}\n\n{extra}"
    messages = [{'role': 'system', 'content': sistema}]
    messages.extend(_historial_sandbox(telefono, agente))
    messages.append({'role': 'user', 'content': q[:1500]})

    try:
        from openai import OpenAI

        from core.openai_compat import completar_chat, contexto_uso_llm
        from core.presupuesto_llm import modelo_segun_presupuesto

        contexto_uso_llm(telefono=telefono, agente=agente)
        texto = completar_chat(
            OpenAI(api_key=api_key),
            modelo_segun_presupuesto(_modelo()),
            messages,
            _max_tokens(),
        )
        if texto:
            return texto
    except Exception:
        logger.exception('sandbox_agente_llm_fail agente=%s', agente)

    return _respuesta_si_falla(agente, q)


def _cita(pregunta: str) -> str:
    tema = re.sub(r'\s+', ' ', (pregunta or '').strip())
    if len(tema) > 160:
        tema = tema[:157] + '...'
    return tema


def _respuesta_si_falla(agente: AgenteSandbox, pregunta: str) -> str:
    """Si el modelo no devolvió texto, igual se contesta lo que la persona dijo."""
    tema = _cita(pregunta)
    low = tema.lower()
    if agente == 'coach':
        if any(p in low for p in ('miedo', 'fallar', 'falla', 'vergüenza', 'verguenza')):
            return (
                "El miedo a fallar es lo que le frena, no que liderar no sirva.\n\n"
                "Hoy haga la versión más pequeña de eso que está evitando: "
                "10 minutos, sin mostrarle a nadie, y anote qué pasó.\n\n"
                "Mañana lo repite solo si esa nota dice que valió la pena."
            )
        if any(p in low for p in ('desmotiv', 'estanc', 'resultado', 'líder', 'lider')):
            return (
                "Se siente estancado porque no ve un resultado, "
                "y por eso parece que ser buen líder no alcanza.\n\n"
                "Hoy cierre una sola cosa visible: una decisión escrita, "
                "una llamada hecha o un pendiente tachado.\n\n"
                "Eso es el resultado de hoy. Elija una y hágalo antes de dormir."
            )
        return (
            f"Trabajemos esto: «{tema}».\n\n"
            "Hoy, 15 minutos solo en eso. Al terminar, escriba una línea: qué avanzó.\n\n"
            "Hágalo hoy. No lo deje para cuando se sienta listo."
        )
    if agente == 'ventas':
        if any(p in low for p in ('precio', 'cobr', 'barat', 'caro')):
            return (
                f"Sobre lo que plantea («{tema}»): no baje el precio "
                "antes de saber cuánto le cuesta entregar.\n\n"
                "Hoy sume producto + tiempo + transporte. Mañana dígale a un cliente "
                "ese precio y pregúntele qué tendría que incluir para que le sirva."
            )
        if any(p in low for p in ('cliente', 'vend')):
            return (
                f"Su caso: «{tema}».\n\n"
                "El paso no es un discurso nuevo. Hoy escríbale a alguien que ya le compró "
                "y pregúntele por qué le compró y qué le faltó."
            )
        return (
            f"Su caso: «{tema}».\n\n"
            "Mañana, con un solo cliente: primero pregunte qué le importa al comprar "
            "y después hable de lo que usted vende."
        )
    return (
        f"Su duda: «{tema}».\n\n"
        "Piénselo así: la IA es un ayudante al que usted le escribe y le devuelve un borrador.\n\n"
        "Prueba de hoy: pídale, en una frase, que le ayude con eso mismo. "
        "Si la respuesta no sirve, dígale qué le faltó."
    )
