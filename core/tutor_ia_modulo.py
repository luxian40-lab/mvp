"""
Tutor IA por Módulo — Motor ligero con gpt-4o-mini
Usa método sandwich: concepto → ejemplo → pregunta.
Máximo 60 palabras, cero cátedras.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# =====================================================
# PROMPT TUTOR — Método Sandwich, máx 60 palabras
# =====================================================
PROMPT_TUTOR_MODULO = """Eres un coach educativo de Eki. REGLAS OBLIGATORIAS:

1. MÁXIMO 60 PALABRAS por mensaje. Sin cátedras.
2. MÉTODO SANDWICH en cada mensaje:
   - 1 frase clara con el concepto.
   - 1 ejemplo práctico de la vida cotidiana.
   - 1 pregunta directa para validar comprensión.
3. PERSONALIDAD: Coach cercano, respetuoso, motivador.
4. Máximo 2 emojis por mensaje.
5. Lenguaje sencillo, cero tecnicismos complejos.
6. NO saludes si la conversación ya inició.
7. SIEMPRE termina con una pregunta.
8. No inventes información fuera del CONTEXTO del módulo.
9. Si el usuario dice "No sé" o "Me rindo", explícale la respuesta y pídele que la diga con sus palabras."""


# =====================================================
# PROMPT EVALUADOR — Evalúa comprensión del módulo
# =====================================================
PROMPT_EVALUADOR_MODULO = """Eres un evaluador educativo de Eki. El tutor acaba de explicar un concepto del curso.
El estudiante respondió. Tu tarea: evaluar si demuestra comprensión del módulo.

ESCENARIOS:

1. RESPUESTA CORRECTA:
- Felicita brevemente (ej: "¡Muy bien! 💪").
- Refuerza en 1 frase por qué está correcta.
- Pregunta si quiere continuar.

2. RESPUESTA INCORRECTA O INCOMPLETA:
- NUNCA digas "estás mal".
- Sé empático: "Vas bien, pero mira esto…"
- Da una pista nueva o ejemplo distinto.
- Reformula la pregunta más simple.

3. RESPUESTA FUERA DE TEMA:
- Redirige amablemente al tema actual.

REGLAS:
- Máximo 60 palabras.
- Máximo 2 emojis.
- Lenguaje sencillo.
- SIEMPRE termina con una pregunta o invitación a continuar."""


def _get_client():
    """Obtiene cliente OpenAI de forma segura."""
    try:
        from openai import OpenAI
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except Exception as e:
        logger.warning(f"⚠️ OpenAI no disponible: {e}")
        return None


def generar_enseñanza_modulo(modulo, estudiante_nombre: str = "Estudiante") -> str:
    """
    Genera una micro-enseñanza del módulo con método sandwich.
    Se llama al avanzar de módulo para que el tutor IA explique el contenido.

    Args:
        modulo: instancia de Modulo (tiene .titulo, .contenido, .curso.nombre)
        estudiante_nombre: nombre del estudiante

    Returns:
        str: mensaje del tutor (máx 60 palabras) con concepto + ejemplo + pregunta
    """
    client = _get_client()
    if not client:
        # Fallback sin IA
        return _fallback_enseñanza(modulo)

    # Tomar solo los primeros 1500 chars del contenido para ahorrar tokens
    contenido_corto = modulo.contenido[:1500] if modulo.contenido else modulo.descripcion

    prompt_usuario = f"""CONTEXTO DEL MÓDULO:
Curso: {modulo.curso.nombre}
Módulo {modulo.numero}: {modulo.titulo}
Contenido: {contenido_corto}

Estudiante: {estudiante_nombre}

Genera UNA micro-enseñanza con método sandwich sobre el concepto principal de este módulo."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_TUTOR_MODULO},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7,
            max_tokens=120  # ~60 palabras
        )
        respuesta = response.choices[0].message.content.strip()
        logger.info(f"✅ TutorIA módulo {modulo.numero}: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        logger.error(f"❌ Error TutorIA: {e}")
        return _fallback_enseñanza(modulo)


def evaluar_respuesta_modulo(modulo, respuesta_estudiante: str, pregunta_original: str = "",
                              estudiante_nombre: str = "Estudiante") -> tuple:
    """
    Evalúa la respuesta del estudiante al tutor IA con empatía.

    Args:
        modulo: instancia de Modulo
        respuesta_estudiante: texto libre del estudiante
        pregunta_original: la pregunta que hizo el tutor
        estudiante_nombre: nombre del estudiante

    Returns:
        tuple: (aprobado: bool, feedback: str)
    """
    client = _get_client()
    if not client:
        return True, _fallback_evaluacion()

    contenido_corto = modulo.contenido[:1000] if modulo.contenido else modulo.descripcion

    prompt_usuario = f"""CONTEXTO:
Curso: {modulo.curso.nombre}
Módulo: {modulo.titulo}
Contenido clave: {contenido_corto}

PREGUNTA DEL TUTOR: {pregunta_original}
RESPUESTA DEL ESTUDIANTE ({estudiante_nombre}): {respuesta_estudiante}

Evalúa si demuestra comprensión. Sigue los escenarios del prompt."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_EVALUADOR_MODULO},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.5,
            max_tokens=120
        )
        feedback = response.choices[0].message.content.strip()

        # Heurística simple: si tiene felicitación → aprobado
        palabras_aprobacion = ['muy bien', 'correcto', 'excelente', 'perfecto',
                               'bien hecho', '💪', '👏', '✅', 'exacto']
        aprobado = any(p in feedback.lower() for p in palabras_aprobacion)

        logger.info(f"✅ EvaluadorIA: {'aprobado' if aprobado else 'necesita refuerzo'}")
        return aprobado, feedback
    except Exception as e:
        logger.error(f"❌ Error EvaluadorIA: {e}")
        return True, _fallback_evaluacion()


# =====================================================
# Fallbacks sin IA (cero costo)
# =====================================================
def _fallback_enseñanza(modulo):
    """Micro-enseñanza sin IA basada en el contenido."""
    titulo = modulo.titulo
    # Tomar primera oración del contenido
    contenido = modulo.contenido or modulo.descripcion or ""
    primera_oracion = contenido.split('.')[0].strip() if contenido else titulo

    return (
        f"📚 *{titulo}*\n\n"
        f"{primera_oracion}.\n\n"
        f"💡 ¿Puedes darme un ejemplo de cómo aplicarías esto en tu vida diaria?"
    )


def _fallback_evaluacion():
    """Evaluación genérica sin IA."""
    return (
        "✅ ¡Gracias por tu respuesta!\n\n"
        "Tu reflexión muestra que vas por buen camino 💪\n\n"
        "¿Quieres continuar al siguiente tema?"
    )
