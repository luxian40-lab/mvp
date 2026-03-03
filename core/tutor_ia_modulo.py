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
PROMPT_TUTOR_MODULO = """Eres el Profesor Gerónimo, coach educativo de eki. REGLAS OBLIGATORIAS:

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
PROMPT_EVALUADOR_MODULO = """Eres el Profesor Gerónimo, evaluador educativo de eki. El tutor acaba de explicar un concepto del curso.
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

    # 🤖 RAG: Obtener contexto adicional de documentos del curso
    contexto_rag = ""
    try:
        from .rag_manager import rag_manager
        cliente_id = modulo.curso.cliente_id if modulo.curso.cliente_id else 0
        contexto_rag = rag_manager.obtener_contexto_para_ia(
            cliente_id=cliente_id,
            curso_id=modulo.curso_id,
            pregunta=modulo.titulo,
            max_chars=1000
        )
    except Exception as e:
        logger.warning(f"[RAG] Error en tutor IA: {e}")

    prompt_usuario = f"""CONTEXTO DEL MÓDULO:
Curso: {modulo.curso.nombre}
Módulo {modulo.numero}: {modulo.titulo}
Contenido: {contenido_corto}
{contexto_rag}
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
            max_tokens=120,  # ~60 palabras
            timeout=10
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

    # 🤖 RAG: Contexto adicional de documentos del curso
    contexto_rag = ""
    try:
        from .rag_manager import rag_manager
        cliente_id = modulo.curso.cliente_id if modulo.curso.cliente_id else 0
        contexto_rag = rag_manager.obtener_contexto_para_ia(
            cliente_id=cliente_id,
            curso_id=modulo.curso_id,
            pregunta=respuesta_estudiante,
            max_chars=800
        )
    except Exception as e:
        logger.warning(f"[RAG] Error en evaluador IA: {e}")

    prompt_usuario = f"""CONTEXTO:
Curso: {modulo.curso.nombre}
Módulo: {modulo.titulo}
Contenido clave: {contenido_corto}
{contexto_rag}
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
            max_tokens=120,
            timeout=10
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
# PROMPT MARÍA — Asistente/Mentora, cada 2 módulos (pares)
# =====================================================
PROMPT_MARIA_MENTORA = """Eres María, la asistente y mentora educativa de eki.
Tu rol es acompañar al estudiante como su apoyo constante durante todo el curso.
Trabajas junto al Profesor Gerónimo: él enseña, tú te aseguras de que todo quede claro.

REGLAS:
1. MÁXIMO 80 PALABRAS.
2. Haz un breve resumen de los módulos completados hasta ahora.
3. Pregunta directamente: ¿estás entendiendo lo que hemos visto? ¿Tienes alguna duda o consulta?
4. Sé cálida, empática y cercana, como una compañera de estudio.
5. Máximo 2 emojis.
6. SIEMPRE termina preguntando si tiene dudas o necesita que le expliques algo.
7. Si el estudiante tiene dudas, ofrece resúmenes claros y sencillos.
8. Tu tono es de confianza: 'Estoy aquí para ayudarte en lo que necesites.'"""


def generar_revision_progreso(modulo_actual, modulos_completados, curso_nombre,
                               estudiante_nombre: str = "Estudiante") -> str:
    """
    María genera una revisión de progreso cada 2 módulos (pares).
    Pregunta si el estudiante entiende, tiene dudas o consultas.

    Args:
        modulo_actual: instancia de Modulo actual
        modulos_completados: QuerySet o lista de módulos completados
        curso_nombre: nombre del curso
        estudiante_nombre: nombre del estudiante

    Returns:
        str: mensaje de María con revisión de progreso
    """
    client = _get_client()

    # Resumir módulos completados
    modulos_info = ""
    if modulos_completados:
        for m in modulos_completados:
            titulo = m.titulo if hasattr(m, 'titulo') else str(m)
            modulos_info += f"- {titulo}\n"

    if not client:
        return _fallback_revision_progreso(modulos_info, estudiante_nombre)

    prompt_usuario = f"""CONTEXTO:
Estudiante: {estudiante_nombre}
Curso: {curso_nombre}
Módulo actual completado: {modulo_actual.numero} - {modulo_actual.titulo}

Módulos completados hasta ahora:
{modulos_info}

Haz un check-in con el estudiante. Resume brevemente lo visto.
Pregunta: ¿Estás entendiendo lo que hemos visto? ¿Tienes alguna duda o consulta?"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_MARIA_MENTORA},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7,
            max_tokens=160,
            timeout=10
        )
        respuesta = response.choices[0].message.content.strip()
        logger.info(f"✅ María revisión módulo {modulo_actual.numero}: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        logger.error(f"❌ Error María revisión: {e}")
        return _fallback_revision_progreso(modulos_info, estudiante_nombre)


def evaluar_respuesta_progreso(modulos_completados_info, respuesta_estudiante,
                                 pregunta_original, estudiante_nombre="Estudiante") -> tuple:
    """
    María evalúa la respuesta del estudiante a la revisión de progreso.
    Si tiene dudas, da resúmenes y ayuda. Si no, lo anima a seguir.

    Returns:
        tuple: (resuelta: bool, feedback: str)
    """
    client = _get_client()
    if not client:
        return True, "✅ ¡Gracias por compartir! Sigue adelante con confianza 💪\n\nEscribe *\"listo\"* para continuar."

    prompt_usuario = f"""CONTEXTO:
Módulos completados: {modulos_completados_info}

PREGUNTA DE MARÍA: {pregunta_original}
RESPUESTA DEL ESTUDIANTE ({estudiante_nombre}): {respuesta_estudiante}

Si el estudiante tiene dudas:
- Da un resumen claro y sencillo del tema que le genera dudas
- Explica con ejemplos prácticos de la vida cotidiana
- Ofrécele seguir preguntando si necesita más ayuda

Si no tiene dudas o dice que todo está bien:
- Felicítalo por su buen avance
- Anímalo a seguir con el siguiente módulo

SIEMPRE termina invitándolo a continuar."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_MARIA_MENTORA},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.5,
            max_tokens=200,
            timeout=10
        )
        feedback = response.choices[0].message.content.strip()

        # Si no tiene dudas o responde positivamente → resuelta
        palabras_ok = ['no tengo', 'todo bien', 'entendido', 'claro', 'sin dudas',
                       'continuar', 'listo', 'bien', 'ok', 'sí', 'si', 'gracias',
                       'no', 'nada', 'ninguna', 'todo claro']
        resuelta = any(p in respuesta_estudiante.lower() for p in palabras_ok)

        return resuelta, feedback
    except Exception as e:
        logger.error(f"❌ Error María eval progreso: {e}")
        return True, "✅ ¡Gracias! Sigue adelante con confianza 💪\n\nEscribe *\"listo\"* para continuar."


def _fallback_revision_progreso(modulos_info, estudiante_nombre):
    """Revisión de progreso sin IA (María)."""
    return (
        f"👩‍🏫 *¡Hola {estudiante_nombre}, soy María!*\n\n"
        f"Has completado varios módulos hasta ahora, ¡vas muy bien!\n\n"
        f"💬 ¿Estás entendiendo todo lo que hemos visto? ¿Tienes alguna duda o consulta? Estoy aquí para ayudarte."
    )


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


# =====================================================
# RESUMEN DE CURSO COMPLETO — María al finalizar curso
# =====================================================
PROMPT_MARIA_RESUMEN_CURSO = """Eres María, la asistente educativa de eki.
El estudiante acaba de completar TODOS los módulos de un curso.
Tu tarea es darle un resumen completo de todo lo aprendido antes de continuar al certificado.

REGLAS:
1. MÁXIMO 150 PALABRAS.
2. Haz un resumen organizado de los temas principales vistos en cada módulo.
3. Destaca los conceptos más importantes.
4. Felicita al estudiante por completar todo el curso.
5. Sé cálida y celebra el logro.
6. Máximo 3 emojis.
7. Termina diciendo que puede continuar al examen o certificado."""


def generar_resumen_curso_completo(curso_nombre, modulos_completados,
                                     estudiante_nombre="Estudiante") -> str:
    """
    María genera un resumen completo de todo el curso al finalizarlo.
    Se muestra justo antes del flujo de certificado.

    Args:
        curso_nombre: nombre del curso
        modulos_completados: lista/QuerySet de módulos completados
        estudiante_nombre: nombre del estudiante

    Returns:
        str: resumen completo del curso por María
    """
    client = _get_client()

    modulos_info = ""
    if modulos_completados:
        for m in modulos_completados:
            titulo = m.titulo if hasattr(m, 'titulo') else str(m)
            contenido_corto = ""
            if hasattr(m, 'contenido') and m.contenido:
                contenido_corto = m.contenido[:100].replace('\n', ' ')
            modulos_info += f"- Módulo {m.numero if hasattr(m, 'numero') else '?'}: {titulo}"
            if contenido_corto:
                modulos_info += f" ({contenido_corto}...)"
            modulos_info += "\n"

    if not client:
        return _fallback_resumen_curso(modulos_info, curso_nombre, estudiante_nombre)

    prompt_usuario = f"""CONTEXTO:
Estudiante: {estudiante_nombre}
Curso completado: {curso_nombre}

Módulos del curso:
{modulos_info}

Genera un resumen completo de todo lo aprendido. Felicita y celebra el logro."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_MARIA_RESUMEN_CURSO},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7,
            max_tokens=300,
            timeout=10
        )
        respuesta = response.choices[0].message.content.strip()
        logger.info(f"✅ María resumen curso: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        logger.error(f"❌ Error María resumen curso: {e}")
        return _fallback_resumen_curso(modulos_info, curso_nombre, estudiante_nombre)


def _fallback_resumen_curso(modulos_info, curso_nombre, estudiante_nombre):
    """Resumen de curso sin IA (María)."""
    return (
        f"👩‍🏫 *¡Felicidades {estudiante_nombre}!*\n\n"
        f"Has completado todo el curso *{curso_nombre}*. "
        f"Repasamos muchos temas importantes a lo largo de los módulos.\n\n"
        f"📋 *Módulos completados:*\n{modulos_info}\n"
        f"¡Excelente trabajo! Estoy muy orgullosa de tu esfuerzo 💪\n\n"
        f"Ahora puedes continuar con el examen final o tu certificado."
    )


# =====================================================
# PRESENTACIÓN DE AGENTES — Inicio de curso
# =====================================================
def generar_presentacion_agentes(curso_nombre, estudiante_nombre="Estudiante") -> tuple:
    """
    Genera las presentaciones de Gerónimo y María al inicio de un curso.

    Returns:
        tuple: (msg_geronimo: str, msg_maria: str)
    """
    msg_geronimo = (
        f"🎓 *¡Hola {estudiante_nombre}! Soy el Profesor Gerónimo* 👨‍🏫\n\n"
        f"Seré tu profesor a cargo en el curso *{curso_nombre}*. "
        f"Yo te enseñaré cada módulo y te haré preguntas para asegurarme de que "
        f"todo quede claro. ¡Vamos a aprender juntos! 💪"
    )
    
    msg_maria = (
        f"👩‍🏫 *¡Y yo soy María, tu asistente!* 📋\n\n"
        f"Estaré pendiente de ti en todo este proceso. "
        f"Si tienes dudas, si algo no te queda claro o necesitas que te explique algo de nuevo, "
        f"yo estaré aquí para ayudarte. ¡Cuenta conmigo! 🤝\n\n"
        f"Comenzamos con el primer módulo... 👇"
    )
    
    return msg_geronimo, msg_maria
