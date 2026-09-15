"""Agentes extra del menú sandbox (Coach + Profe IA).

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

AgenteSandbox = Literal['coach', 'ia_campo']

# Misma familia de modelo / esfuerzo que Nat (settings BOT_COMERCIAL_*).
def _modelo() -> str:
    return (
        getattr(settings, 'BOT_COMERCIAL_OPENAI_MODEL', None)
        or getattr(settings, 'OPENAI_MODEL', None)
        or 'gpt-5-mini'
    )


def _max_tokens() -> int:
    try:
        return max(320, int(getattr(settings, 'BOT_COMERCIAL_OPENAI_MAX_TOKENS', 420) or 420))
    except (TypeError, ValueError):
        return 420


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
- Máx. ~140 palabras. Claridad > brillantez.
- Nunca inventes precios, dosis, plagas ni políticas de Meta/WhatsApp.
- Agronomía / plagas / productos → «Eso lo atiende el Agrónomo (Nat) en el menú».
- No asustes con «la IA reemplaza personas»; enfoca en ayuda y ahorro de tiempo.
- Si preguntan «qué es ChatGPT/Nat», explica en una analogía (ayudante que lee y responde).

TONO
Paciente, alegre, respetuoso. Nunca condescendiente («hasta un niño…»).
""".strip()


def prompt_para(agente: AgenteSandbox) -> str:
    return PROMPT_COACH if agente == 'coach' else PROMPT_IA_CAMPO


def nombre_agente(agente: AgenteSandbox) -> str:
    return 'Lina (Coach eki)' if agente == 'coach' else 'Profe IA'


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
            "Recuerdo lo que hablamos en este sandbox. "
            "Cuénteme cómo sigue, o diga *reiniciar* para empezar limpio.\n\n"
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
        "Recuerdo la conversación en este sandbox. "
        "Seguimos donde íbamos, o escriba *reiniciar* para empezar limpio.\n\n"
        "_*menu* para volver._"
    )


def _max_turnos_memoria() -> int:
    """Ventana larga (pares user+assistant). Tope duro por costo/contexto."""
    try:
        n = int(getattr(settings, 'SANDBOX_AGENTE_MAX_TURNOS', 28) or 28)
    except (TypeError, ValueError):
        n = 28
    return max(8, min(n, 40))


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

    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        return (
            f"{nombre_agente(agente)}: el sandbox no tiene API de IA configurada. "
            "Escriba *menu* y pruebe Agrónomo (Nat) o Cursos."
        )

    messages = [{'role': 'system', 'content': prompt_para(agente)}]
    messages.extend(_historial_sandbox(telefono, agente))
    messages.append({'role': 'user', 'content': q[:4000]})

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        kwargs = {
            'model': _modelo(),
            'messages': messages,
            'max_completion_tokens': _max_tokens(),
        }
        effort = (getattr(settings, 'BOT_COMERCIAL_REASONING_EFFORT', 'low') or 'low').strip()
        # gpt-5* acepta reasoning en algunos clientes; si falla, reintento sin él
        try:
            resp = client.chat.completions.create(
                **kwargs,
                reasoning_effort=effort if effort in ('minimal', 'low', 'medium', 'high') else 'low',
            )
        except TypeError:
            resp = client.chat.completions.create(**kwargs)
        texto = (resp.choices[0].message.content or '').strip()
        if texto:
            return texto
    except Exception:
        logger.exception('sandbox_agente_llm_fail agente=%s', agente)

    if agente == 'coach':
        return (
            "Entiendo. Propongo *una* meta de 20 minutos hoy "
            "(curso, llamadas o ordenar números). "
            "¿Cuál elige y a qué hora la hace?"
        )
    return (
        "La IA es como un ayudante que lee lo que usted escribe y responde. "
        "En eki la usamos para dudas del campo y del curso por WhatsApp. "
        "¿Quiere un ejemplo con una *foto de cultivo* o con una *pregunta de precios*?"
    )
