"""
Tutor IA por Módulo — Motor ligero con gpt-4o-mini
v1.9.8g: Facilitador(a) con ABR + Asistente Darío
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# =====================================================
# PROMPT FACILITADOR(A) — ABR (Aprendizaje Basado en Retos)
# Se activa DESPUÉS de que Darío termina (módulos 3 y 5)
# =====================================================
PROMPT_FACILITADOR_RETO = """Eres la Facilitadora Claudia, experta en Aprendizaje Basado en Retos (ABR) de eki.
Tu rol es plantear un RETO práctico al participante para evaluar lo aprendido.

REGLAS OBLIGATORIAS:
1. TRATO DE USTED siempre. NUNCA tutear.
2. El reto es una situación que simula la realidad. El participante debe aplicar conocimientos para resolver una problemática.
3. MÁXIMO 120 PALABRAS para el reto.
4. El reto puede evaluar competencias técnicas Y blandas (pensamiento crítico, toma de decisiones, liderazgo, empatía, negociación, trabajo en equipo, pensamiento analítico).
5. Lenguaje sencillo, pensando en emprendedores y trabajadores rurales de Colombia.
6. Máximo 2 emojis.
7. No inventes información fuera del CONTEXTO de los módulos.
8. Termina con una instrucción clara: "Escriba su respuesta al reto."
9. Prioriza ejemplos de ruralidad colombiana (vereda, finca familiar, plaza de mercado, asociación local, acopio, transporte veredal).
10. Dificultad media-baja: pregunta clara, concreta y accionable sin tecnicismos innecesarios.
11. PROHIBIDO preguntar si tiene dudas o si quiere continuar."""


PROMPT_FACILITADOR_EVALUACION = """Eres la Facilitadora Claudia, evaluadora de eki con metodología ABR.
El participante respondió a un reto. Evalúa su respuesta con esta RÚBRICA (1-10):

DIMENSIONES DE EVALUACIÓN:
- Enfoque y Comprensión (máx 3 pts): ¿Entendió el reto y enfocó bien su respuesta?
- Fundamentación y Viabilidad (máx 4 pts): ¿Usó conceptos del curso? ¿Es viable su propuesta?
- Estructura y Claridad (máx 3 pts): ¿Se expresa de forma clara y organizada?

FORMATO DE RESPUESTA OBLIGATORIO:
1. Retroalimentación positiva primero (qué hizo bien).
2. Qué le faltó o puede mejorar.
3. Puntaje total: X/10
4. Desglose: Enfoque X/3 | Fundamentación X/4 | Claridad X/3

REGLAS:
- TRATO DE USTED siempre.
- Máximo 100 palabras de retroalimentación.
- Máximo 2 emojis.
- Sé empático pero honesto.
- PROHIBIDO hacer preguntas de seguimiento. Cierre motivador breve.
- NO preguntar si quiere continuar o si tiene dudas."""


# =====================================================
# PROMPT ASISTENTE (DARÍO) — Companion, tutea
# Se activa SOLO al final de módulo 3 y módulo 5
# =====================================================
PROMPT_ASISTENTE_DARIO = """Eres Darío, el asistente y compañero de estudio de eki.
Eres el ÚNICO que tutea al estudiante (trato informal, "tú").
Tu rol: ayudar a repasar conceptos antes de que la Facilitadora Claudia plantee un reto.

REGLAS:
1. TUTEA siempre ("tú", "te", "tu").
2. MÁXIMO 60 PALABRAS por mensaje.
3. Responde basándote SOLO en el contenido RAG/módulos. No inventes nada.
4. Si no tienes información suficiente, dilo honestamente.
5. Sé cercano, amigable, como un compañero de estudio.
6. Máximo 2 emojis.
7. NO hagas preguntas de seguimiento. Responde directamente.
8. PROHIBIDO invitar a seguir conversando o preguntar si tiene más dudas."""


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


def generar_reto_facilitador(modulos_cubiertos, curso_nombre, estudiante_nombre="Estudiante",
                              preguntas_ejemplo="") -> str:
    """
    Facilitadora Claudia genera un RETO ABR que cubre los módulos indicados.
    Se llama después de que Darío termina (módulos 3 y 5).

    Args:
        modulos_cubiertos: lista de instancias Modulo que cubre el reto
        curso_nombre: nombre del curso
        estudiante_nombre: nombre del estudiante
        preguntas_ejemplo: preguntas de ejemplo del admin

    Returns:
        str: mensaje con el reto
    """
    client = _get_client()
    if not client:
        return _fallback_reto(modulos_cubiertos, curso_nombre)

    # Build module content summary
    modulos_info = ""
    for m in modulos_cubiertos:
        contenido_corto = (m.contenido[:300] if m.contenido else m.descripcion or '')
        modulos_info += f"- Módulo {m.numero}: {m.titulo}\n  Contenido: {contenido_corto}\n"

    # RAG context
    contexto_rag = ""
    try:
        from .rag_manager import rag_manager
        curso = modulos_cubiertos[0].curso if modulos_cubiertos else None
        if curso:
            cliente_id = curso.cliente_id if curso.cliente_id else 0
            contexto_rag = rag_manager.obtener_contexto_para_ia(
                cliente_id=cliente_id,
                curso_id=curso.id,
                pregunta="reto práctico basado en los módulos",
                max_chars=1000
            )
    except Exception as e:
        logger.warning(f"[RAG] Error en reto facilitador: {e}")

    ejemplo_txt = ""
    if preguntas_ejemplo:
        ejemplo_txt = f"\nPREGUNTAS/RETOS EJEMPLO DEL INSTRUCTOR (OBLIGATORIO: Basa tu reto DIRECTAMENTE en estos ejemplos):\n{preguntas_ejemplo}\n"

    prompt_usuario = f"""CONTEXTO:
Curso: {curso_nombre}
Participante: {estudiante_nombre}

MÓDULOS QUE CUBRE ESTE RETO:
{modulos_info}
{contexto_rag}
{ejemplo_txt}
Genere UN reto práctico ABR que integre los conceptos de estos módulos."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_FACILITADOR_RETO},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7,
            max_tokens=250,
            timeout=12
        )
        respuesta = response.choices[0].message.content.strip()
        logger.info(f"✅ Facilitadora reto: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        logger.error(f"❌ Error Facilitadora reto: {e}")
        return _fallback_reto(modulos_cubiertos, curso_nombre)


def evaluar_reto_facilitador(modulos_cubiertos, respuesta_estudiante, reto_original,
                              estudiante_nombre="Estudiante") -> tuple:
    """
    Facilitadora evalúa la respuesta al reto con rúbrica ABR.

    Returns:
        tuple: (puntaje: int 1-10, feedback: str)
    """
    client = _get_client()
    if not client:
        return 7, _fallback_evaluacion_reto()

    modulos_info = ""
    for m in modulos_cubiertos:
        contenido_corto = (m.contenido[:600] if m.contenido else '')
        modulos_info += f"- Módulo {m.numero}: {m.titulo}\n  {contenido_corto}\n"

    # RAG context
    contexto_rag = ""
    try:
        from .rag_manager import rag_manager
        curso = modulos_cubiertos[0].curso if modulos_cubiertos else None
        if curso:
            cliente_id = curso.cliente_id if curso.cliente_id else 0
            contexto_rag = rag_manager.obtener_contexto_para_ia(
                cliente_id=cliente_id,
                curso_id=curso.id,
                pregunta=respuesta_estudiante,
                max_chars=1200
            )
    except Exception as e:
        logger.warning(f"[RAG] Error en evaluación reto: {e}")

    prompt_usuario = f"""CONTEXTO:
Módulos cubiertos:
{modulos_info}
{contexto_rag}

RETO PLANTEADO: {reto_original}
RESPUESTA DEL PARTICIPANTE ({estudiante_nombre}): {respuesta_estudiante}

Evalúe según la rúbrica. Dé retroalimentación y puntaje."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_FACILITADOR_EVALUACION},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.5,
            max_tokens=250,
            timeout=12
        )
        feedback = response.choices[0].message.content.strip()

        # Extract score from feedback
        import re
        puntaje = 7  # default
        match = re.search(r'(\d+)\s*/\s*10', feedback)
        if match:
            puntaje = min(10, max(1, int(match.group(1))))

        logger.info(f"✅ Facilitadora evaluación reto: {puntaje}/10")
        return puntaje, feedback
    except Exception as e:
        logger.error(f"❌ Error evaluación reto: {e}")
        return 7, _fallback_evaluacion_reto()


def generar_respuesta_asistente(modulos_cubiertos, pregunta_estudiante,
                                 estudiante_nombre="Estudiante") -> str:
    """
    Darío responde una pregunta del estudiante basada en RAG/contenido de módulos.
    Máximo 2 preguntas antes de pasar a la Facilitadora.

    Returns:
        str: respuesta de Darío
    """
    client = _get_client()
    if not client:
        return _fallback_respuesta_asistente()

    modulos_info = ""
    for m in modulos_cubiertos:
        contenido = (m.contenido[:400] if m.contenido else m.descripcion or '')
        modulos_info += f"- Módulo {m.numero}: {m.titulo}\n  {contenido}\n"

    # RAG context
    contexto_rag = ""
    try:
        from .rag_manager import rag_manager
        curso = modulos_cubiertos[0].curso if modulos_cubiertos else None
        if curso:
            cliente_id = curso.cliente_id if curso.cliente_id else 0
            contexto_rag = rag_manager.obtener_contexto_para_ia(
                cliente_id=cliente_id,
                curso_id=curso.id,
                pregunta=pregunta_estudiante,
                max_chars=1000
            )
    except Exception as e:
        logger.warning(f"[RAG] Error en asistente Darío: {e}")

    prompt_usuario = f"""CONTEXTO:
Estudiante: {estudiante_nombre}
Módulos cubiertos:
{modulos_info}
{contexto_rag}

PREGUNTA DEL ESTUDIANTE: {pregunta_estudiante}

Responde basándote SOLO en el contenido de los módulos y documentos RAG."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_ASISTENTE_DARIO},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7,
            max_tokens=120,
            timeout=10
        )
        respuesta = response.choices[0].message.content.strip()
        logger.info(f"✅ Darío respuesta: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        logger.error(f"❌ Error Darío respuesta: {e}")
        return _fallback_respuesta_asistente()


def _fallback_reto(modulos_cubiertos, curso_nombre):
    """Reto de fallback sin IA."""
    temas = ", ".join([m.titulo for m in modulos_cubiertos]) if modulos_cubiertos else curso_nombre
    return (
        f"📋 *Reto práctico*\n\n"
        f"Imagine que debe explicarle a un compañero cómo aplicar lo aprendido sobre {temas} "
        f"en una situación real de su comunidad.\n\n"
        f"¿Qué haría y por qué? Escriba su respuesta al reto."
    )


def _fallback_evaluacion_reto():
    """Evaluación de reto sin IA."""
    return (
        "✅ Gracias por su respuesta al reto.\n\n"
        "Su reflexión muestra compromiso con el aprendizaje.\n"
        "Puntaje: 7/10\n"
        "Enfoque 2/3 | Fundamentación 3/4 | Claridad 2/3\n\n"
        "¡Buen trabajo! 💪"
    )


def _fallback_respuesta_asistente():
    """Respuesta de Darío sin IA."""
    return (
        "¡Buena pregunta! Lamentablemente no tengo suficiente información para responderte con certeza. "
        "Pero no te preocupes, la Facilitadora Claudia te va a ayudar con el reto 💪"
    )


# Keep legacy function name as alias for backward compatibility
def generar_enseñanza_modulo(modulo, estudiante_nombre="Estudiante", preguntas_ejemplo=""):
    """Legacy: Now returns a brief module summary instead of tutor question."""
    return _fallback_enseñanza(modulo)


def evaluar_respuesta_modulo(modulo, respuesta_estudiante: str, pregunta_original: str = "",
                              estudiante_nombre: str = "Estudiante") -> tuple:
    """Legacy: kept for backward compat. Returns (True, generic feedback)."""
    return True, "✅ ¡Gracias por tu respuesta! Continúa con el módulo 💪"


# =====================================================
# PROMPT MARÍA — REMOVED in v1.9.8g (replaced by Darío)
# Functions kept as stubs for backward compatibility
# =====================================================
PROMPT_MARIA_MENTORA = """Eres Darío, asistente de estudio de eki. Trato informal (tú). Máximo 60 palabras. Sé amigable y cercano."""


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

Si no tiene dudas o dice que todo está bien:
- Felicítalo por su buen avance

REGLAS:
- Máximo 60 palabras.
- NO hagas preguntas de seguimiento.
- NO preguntes si quiere continuar, si tiene más dudas, o si necesita más ayuda.
- Termina con una frase de ánimo breve, NUNCA con una pregunta."""

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
        f"� ¡Sigue así, lo estás haciendo excelente!"
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
        "Tu reflexión muestra que vas por buen camino 💪"
    )


# =====================================================
# RESUMEN DE CURSO COMPLETO — María al finalizar curso
# =====================================================
# v1.9.8g: María resumen removed
PROMPT_MARIA_RESUMEN_CURSO = ""


def generar_resumen_curso_completo(curso_nombre, modulos_completados,
                                     estudiante_nombre="Estudiante") -> str:
    """Legacy stub — María resumen removed in v1.9.8g."""
    return ""


def _fallback_resumen_curso(modulos_info, curso_nombre, estudiante_nombre):
    """Legacy stub."""
    return ""


# =====================================================
# PRESENTACIÓN DE AGENTES — Inicio de curso
# =====================================================
def generar_presentacion_agentes(curso_nombre, estudiante_nombre="Estudiante", nombre_tutor="Claudia", nombre_asistente="Darío") -> tuple:
    """
    Genera las presentaciones de los agentes al inicio de un curso.
    v1.9.8g: Facilitador(a) + Asistente Darío.

    Returns:
        tuple: (msg_facilitador: str, msg_asistente: str)
    """
    msg_facilitador = (
        f"🤓 *¡Hola {estudiante_nombre}! Soy la Facilitadora {nombre_tutor}*\n\n"
        f"Seré su facilitadora a cargo en el curso *{curso_nombre}*. "
        f"Le plantearé retos prácticos para que aplique lo aprendido. "
        f"¡Vamos a aprender juntos! 💪"
    )
    
    msg_asistente = (
        f"📚 *¡Y yo soy {nombre_asistente}, tu compañero de estudio!*\n\n"
        f"Estaré pendiente de ti en este proceso. "
        f"Si tienes dudas antes de los retos, yo te ayudo a repasar. "
        f"¡Cuenta conmigo! 🤝"
    )
    
    return msg_facilitador, msg_asistente


# =====================================================
# PREGUNTA DE RECUPERACIÓN — Curso completado con <70 pts
# =====================================================
PROMPT_PREGUNTA_RECUPERACION = """Eres la Facilitadora Claudia de eki. El participante completó todo el curso pero obtuvo menos de 70 puntos.
Tu tarea: generar UNA pregunta de recuperación enfocada SOLO en los módulos finales (módulos 4 y 5, o 4 en adelante si existen más).

REGLAS:
1. TRATO DE USTED siempre.
2. La pregunta debe ser práctica, con un ejemplo de la vida real.
2. Debe integrar conceptos de AL MENOS 2 módulos del bloque final (4 y 5 / 4 en adelante).
3. MÁXIMO 80 PALABRAS en la pregunta.
4. Lenguaje sencillo, pensando en campesinos y emprendedores rurales de Colombia.
5. Debe tener 4 opciones (A, B, C, D) de las cuales SOLO UNA es correcta.
6. Máximo 2 emojis.
7. FORMATO OBLIGATORIO de respuesta:
PREGUNTA: [texto de la pregunta]
A) [opción a]
B) [opción b]
C) [opción c]
D) [opción d]
CORRECTA: [letra]
EXPLICACION: [explicación breve de por qué es correcta, máx 30 palabras]"""


def generar_pregunta_recuperacion(curso, modulos_completados, estudiante_nombre="Estudiante",
                                    preguntas_ejemplo="") -> dict:
    """
    Genera una pregunta de recuperación cuando el estudiante termina con <70 puntos.
    Usa RAG + contenido de módulos + preguntas ejemplo del admin.

    Returns:
        dict: {pregunta, opciones: {A, B, C, D}, correcta, explicacion} o None si falla
    """
    client = _get_client()

    # En recuperación, enfocarse en bloque final (modulos 4+).
    modulos_objetivo = []
    for m in modulos_completados:
        numero = getattr(m, 'numero', 0) or 0
        if numero >= 4:
            modulos_objetivo.append(m)
    if not modulos_objetivo:
        modulos_objetivo = list(modulos_completados)

    # Construir contexto de módulos
    modulos_info = ""
    for m in modulos_objetivo:
        titulo = m.titulo if hasattr(m, 'titulo') else str(m)
        contenido_corto = ""
        if hasattr(m, 'contenido') and m.contenido:
            contenido_corto = m.contenido[:200].replace('\n', ' ')
        modulos_info += f"- Módulo {getattr(m, 'numero', '?')}: {titulo} — {contenido_corto}\n"

    # RAG context
    contexto_rag = ""
    try:
        from .rag_manager import rag_manager
        cliente_id = curso.cliente_id if curso.cliente_id else 0
        contexto_rag = rag_manager.obtener_contexto_para_ia(
            cliente_id=cliente_id,
            curso_id=curso.id,
            pregunta="resumen general del curso para pregunta de recuperación",
            max_chars=1000
        )
    except Exception as e:
        logger.warning(f"[RAG] Error en pregunta recuperación: {e}")

    # Preguntas ejemplo del admin
    ejemplo_txt = ""
    if preguntas_ejemplo:
        ejemplo_txt = f"\nPREGUNTAS EJEMPLO DEL INSTRUCTOR (OBLIGATORIO: Basa tu pregunta de recuperación en el estilo y contenido de estos ejemplos. Usa escenarios prácticos similares):\n{preguntas_ejemplo}\n"

    if not client:
        return _fallback_pregunta_recuperacion(modulos_completados)

    prompt_usuario = f"""CURSO: {curso.nombre}
ESTUDIANTE: {estudiante_nombre}

MÓDULOS OBJETIVO (SOLO BLOQUE FINAL):
{modulos_info}
{contexto_rag}
{ejemplo_txt}
Genera UNA pregunta de recuperación de dificultad media-baja para ruralidad colombiana, enfocada solo en esos módulos. Usa el FORMATO OBLIGATORIO."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_PREGUNTA_RECUPERACION},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7,
            max_tokens=300,
            timeout=12
        )
        texto = response.choices[0].message.content.strip()
        logger.info(f"✅ Pregunta recuperación generada: {texto[:80]}...")
        return _parsear_pregunta_ia(texto)
    except Exception as e:
        logger.error(f"❌ Error pregunta recuperación: {e}")
        return _fallback_pregunta_recuperacion(modulos_objetivo)


def _parsear_pregunta_ia(texto: str) -> dict:
    """Parsea la respuesta de la IA al formato estructurado."""
    import re
    
    resultado = {'pregunta': '', 'opciones': {}, 'correcta': 'A', 'explicacion': ''}
    
    # Extraer pregunta
    match_p = re.search(r'PREGUNTA:\s*(.+?)(?=\nA\))', texto, re.DOTALL)
    if match_p:
        resultado['pregunta'] = match_p.group(1).strip()
    else:
        # Fallback: tomar todo antes de A)
        parts = texto.split('A)')
        if len(parts) > 1:
            resultado['pregunta'] = parts[0].replace('PREGUNTA:', '').strip()
    
    # Extraer opciones
    for letra in ['A', 'B', 'C', 'D']:
        pattern = rf'{letra}\)\s*(.+?)(?=(?:[B-D]\)|CORRECTA:|$))'
        match = re.search(pattern, texto, re.DOTALL)
        if match:
            resultado['opciones'][letra] = match.group(1).strip()
    
    # Extraer respuesta correcta
    match_c = re.search(r'CORRECTA:\s*([A-D])', texto)
    if match_c:
        resultado['correcta'] = match_c.group(1)
    
    # Extraer explicación
    match_e = re.search(r'EXPLICACION:\s*(.+)', texto, re.DOTALL)
    if match_e:
        resultado['explicacion'] = match_e.group(1).strip()
    
    # Validar que tenemos lo mínimo
    if not resultado['pregunta'] or len(resultado['opciones']) < 2:
        return None
    
    return resultado


def _fallback_pregunta_recuperacion(modulos_completados) -> dict:
    """Pregunta de recuperación sin IA."""
    modulos_objetivo = []
    for m in modulos_completados:
        numero = getattr(m, 'numero', 0) or 0
        if numero >= 4:
            modulos_objetivo.append(m)
    if not modulos_objetivo:
        modulos_objetivo = list(modulos_completados)

    if modulos_objetivo:
        primer_modulo = modulos_objetivo[0]
        titulo = getattr(primer_modulo, 'titulo', 'la parte final del curso')
    else:
        titulo = 'la parte final del curso'
    
    return {
        'pregunta': f'De todo lo aprendido sobre {titulo}, ¿cuál consideras que es el concepto más importante para aplicar en tu vida diaria?',
        'opciones': {
            'A': 'Lo que aprendí en los primeros módulos',
            'B': 'Los conceptos prácticos que puedo usar cada día',
            'C': 'Las técnicas avanzadas del final del curso',
            'D': 'Todo es igual de importante'
        },
        'correcta': 'B',
        'explicacion': 'Los conceptos prácticos del día a día son los que más impacto generan.'
    }


def evaluar_respuesta_recuperacion(respuesta_dada: str, correcta: str, explicacion: str) -> tuple:
    """
    Evalúa la respuesta a la pregunta de recuperación.
    
    Returns:
        tuple: (es_correcta: bool, mensaje: str)
    """
    respuesta_upper = respuesta_dada.strip().upper()
    # Aceptar "A", "A)", "opción A", etc.
    letra = ''
    for c in respuesta_upper:
        if c in 'ABCD':
            letra = c
            break
    
    es_correcta = (letra == correcta.strip().upper())
    
    if es_correcta:
        msg = (
            f"🎉 *¡CORRECTO!* La respuesta es *{correcta}*\n\n"
            f"💡 {explicacion}\n\n"
            f"🏆 *+50 puntos de recuperación*\n"
            f"¡Excelente! Demostraste que sí aprendiste 💪"
        )
    else:
        msg = (
            f"La respuesta correcta era *{correcta}*\n\n"
            f"💡 {explicacion}\n\n"
            f"No te preocupes, lo importante es que completaste el curso. "
            f"¡Sigue adelante! 💪"
        )
    
    return es_correcta, msg
