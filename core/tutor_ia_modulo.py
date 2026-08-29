"""
Tutor IA por Módulo — Motor ligero con gpt-4o-mini
v1.9.8g: Facilitador(a) con ABR + Asistente Darío
"""

import logging
import re
from django.conf import settings

logger = logging.getLogger(__name__)


# =====================================================
# PROMPT FACILITADOR(A) — ABR (Aprendizaje Basado en Retos)
# Se activa DESPUÉS de que Darío termina (módulos 3 y 5)
# =====================================================
PROMPT_FACILITADOR_RETO = """Eres la Facilitadora de eki. Tu rol es plantear un reto conversacional al participante.

FORMATO DEL RETO:
- Describe una situación real en 2-3 oraciones alineada SOLO al tema de los módulos y al nombre del curso recibidos en el mensaje (finanzas del hogar, emprendimiento rural, agricultura, otro — según ese contexto, sin inventar otro dominio).
- En seguida, UNA SOLA pregunta integrada (puede incluir qué revisaría o priorizaría y qué haría en la práctica), coherente con ese mismo tema. Sin títulos ni líneas intermedias tipo encabezado.
- PROHIBIDO listas numeradas tipo "1), 2), 3)" o varias preguntas sueltas.

REGLAS OBLIGATORIAS:
1. TRATO DE USTED. NUNCA tutear.
2. MÁXIMO 80 PALABRAS en total.
3. Lenguaje sencillo, cercano al contexto rural/urbano que corresponda al curso.
4. El reto debe plantearse de forma clara y fácil de comprender (situación concreta, sin ambigüedades).
5. Máximo 2 emojis al final.
6. CERO alucinación: solo temas que aparezcan en MÓDULOS / RAG / nombre del curso / GUÍA DEL MÓDULO. PROHIBIDO mezclar plagas, cultivos o finanzas si los módulos no hablan de eso.
7. Si hay GUÍA DEL MÓDULO, obedezca esa guía antes que ejemplos genéricos o de otros programas.
8. Termina con: "Escriba o envíe un audio con su respuesta."
9. Sin tecnicismos innecesarios ni tono de examen.
10. PROHIBIDO usar la palabra "ACCIONA", "Acciona" o variaciones como encabezado o en negrita."""


PROMPT_FACILITADOR_EVALUACION = """Eres la Facilitadora Claudia, evaluadora de eki con metodología ABR.
El participante respondió a un reto. Evalúa su respuesta con esta RÚBRICA (1-10):

DIMENSIONES DE EVALUACIÓN:
- Enfoque y Comprensión (máx 3 pts): ¿Entendió el reto y enfocó bien su respuesta?
- Fundamentación y Viabilidad (máx 4 pts): ¿Usó conceptos del curso? ¿Es viable su propuesta?
- Estructura y Claridad (máx 3 pts): ¿Se expresa de forma clara y organizada?

FORMATO DE RESPUESTA OBLIGATORIO:
1. Retroalimentación positiva primero (qué hizo bien).
2. Qué le faltó o puede mejorar, de forma objetiva y concreta.
3. Puntaje total: X/10
4. Desglose: Enfoque X/3 | Fundamentación X/4 | Claridad X/3
5. Veredicto por componente:
   - Diagnóstico: logrado/parcial/no logrado + evidencia breve.
   - Acción/Control: logrado/parcial/no logrado + evidencia breve.

REGLAS:
- TRATO DE USTED siempre.
- Máximo 120 palabras de retroalimentación.
- Máximo 2 emojis.
- Sé empático pero honesto.
- Ayude al participante a resolver el reto de una manera clara y fácil de comprender: use pasos simples, ejemplos concretos y lenguaje directo.
- PROHIBIDO hacer preguntas de seguimiento. Cierre motivador breve.
- NO preguntar si quiere continuar o si tiene dudas.
- Evita frases generales ("muy bien", "buen trabajo") sin evidencia concreta.
- Diga explícitamente qué parte respondió bien y qué parte faltó.
- Debe citar evidencia de la respuesta del participante (palabras/acciones mencionadas por él/ella).
- Si la respuesta es general, dígalo literalmente y pida precisión concreta en "qué, cuánto, cuándo, con qué".
- Evalúe según el dominio de los módulos (presupuesto, ahorro, metas, campo, u otro): no exija conceptos que no estén en el material.

ESCALA OBLIGATORIA (no regalar puntos; varíe según evidencia real):
- "no sé", vacío, "bueno", "ok", "sí" sin contenido técnico: máximo 2/10 total.
- 1–2 frases vagas sin diagnóstico ni acción concreta: máximo 4/10.
- Respuesta parcial (solo diagnóstico o solo acción): 5–7/10 según calidad.
- Respuesta completa con qué/cuánto/cuándo anclada al curso: 7–10/10.
- Nunca repita la misma retroalimentación genérica si la evidencia cambió."""


PROMPT_FACILITADOR_EVALUACION_NOTAS = """Eres la Facilitadora Claudia, evaluadora de eki con metodología ABR.
El participante respondió a un reto. Asigne una NOTA de 1 a 5 (puede usar un decimal, ej. 3.5).

DIMENSIONES (referencia interna, no liste todo al estudiante):
- Enfoque y comprensión del reto
- Fundamentación con el curso y viabilidad
- Claridad de la respuesta

FORMATO DE RESPUESTA OBLIGATORIO:
1. Retroalimentación positiva primero (qué hizo bien).
2. Qué puede mejorar, de forma concreta.
3. Nota final: X/5 (use un solo número; decimal con punto, ej. 3.5/5)
4. Cierre motivador breve.

REGLAS:
- TRATO DE USTED siempre.
- Máximo 120 palabras.
- Máximo 2 emojis.
- Sea empático y honesto; cite evidencia de la respuesta del participante.
- Ayude al participante a resolver el reto de una manera clara y fácil de comprender: use pasos simples, ejemplos concretos y lenguaje directo.
- PROHIBIDO hacer preguntas de seguimiento.
- NO mencione puntos ni ranking.

ESCALA OBLIGATORIA (nota 1–5; no regalar):
- "no sé", vacío, "bueno", "ok" sin sustancia: nota máxima 1.5/5.
- Vago sin qué/cuánto/cuándo: máximo 2.5/5.
- Parcial: 3–3.5/5. Completa y anclada al curso: 4–5/5."""


# =====================================================
# PROMPT ASISTENTE — Companion, tutea (nombre según cliente/curso)
# Se activa SOLO al final de módulo 3 y módulo 5
# =====================================================
def _prompt_sistema_asistente(nombre_asistente: str) -> str:
    na = (nombre_asistente or "Darío").strip() or "Darío"
    return f"""Eres {na}, el asistente y compañero de estudio de eki.
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
8. PROHIBIDO invitar a seguir conversando o preguntar si tiene más dudas.
9. Tu nombre es {na}; no uses otro nombre propio ni te presentes con otro alias."""


def _quitar_encabezado_acciona(texto: str) -> str:
    """Quita ACCIONA/Acciona en líneas sueltas o entre asteriscos (mensajes al usuario)."""
    import re
    if not (texto or "").strip():
        return texto or ""
    out_lines = []
    for line in texto.splitlines():
        s = line.strip()
        if re.match(r"^\*{0,3}\s*acciona\s*\*{0,3}\s*:?\s*$", s, flags=re.IGNORECASE):
            continue
        if re.match(r"^#{1,6}\s*acciona\s*:?\s*$", s, flags=re.IGNORECASE):
            continue
        out_lines.append(line)
    t = "\n".join(out_lines)
    t = re.sub(r"(?i)\*{1,3}\s*acciona\s*\*{1,3}\s*:?", "", t)
    t = re.sub(r"(?i)\bacciona\b\s*:?", "", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


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


def cargar_modulos_reto(modulos_reto_ids, curso_id=None):
    """
    Módulos para reto Darío/Facilitadora. Si se pasa curso_id, excluye IDs huérfanos de otro curso.
    """
    from .models import Modulo
    if not modulos_reto_ids:
        return []
    qs = Modulo.objects.filter(id__in=modulos_reto_ids).order_by('numero')
    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    rows = list(qs)
    if curso_id and modulos_reto_ids and len(rows) < len(set(modulos_reto_ids)):
        logger.warning(
            "[reto] Módulos del reto filtrados por curso_id=%s | pedidos=%s | cargados=%s",
            curso_id,
            modulos_reto_ids,
            [m.id for m in rows],
        )
    return rows


def listar_modulos_cobertura_reto(modulo_actual, curso):
    """
    Lista de módulos (instancias) que abarca el reto Darío/Claudia según el módulo-checkpoint.

    Antes: solo `numero == 3` usaba módulos <=3; cualquier otro checkpoint con número < 4
    caía en `numero__gte=4`, devolviendo lista vacía (p. ej. facilitador_checkpoint=Sí en módulo 1 o 2).
    Ahora: si el checkpoint es hasta el módulo 3 (incl.), se toman todos los del curso con
    numero <= ese número; si es mayor, se mantiene la ventana 4..N.
    """
    if not modulo_actual or not curso:
        return []
    try:
        n_act = int(modulo_actual.numero)
    except (TypeError, ValueError):
        n_act = 0
    if n_act <= 3:
        rows = list(curso.modulos.filter(numero__lte=n_act).order_by('numero'))
    else:
        rows = list(
            curso.modulos.filter(numero__gte=4, numero__lte=n_act).order_by('numero')
        )
    if not rows:
        rows = [modulo_actual]
    return rows


def descripcion_rango_modulos_reto_esp(modulos_reto) -> str:
    """Frase para el mensaje de Darío (reemplaza 'los 3 primeros' / '4 a N' fijos)."""
    if not modulos_reto:
        return 'el contenido que venís viendo'
    lo = modulos_reto[0].numero
    hi = modulos_reto[-1].numero
    if lo == hi:
        return f'el módulo {lo}'
    return f'los módulos {lo} a {hi}'


# Plantillas de formato para Claudia (tipo_reto_ia en el módulo checkpoint).
_INSTRUCCION_TIPO_RETO = {
    'situacion_decision': (
        "FORMATO OBLIGATORIO DEL RETO: situación cotidiana breve + UNA pregunta de decisión "
        "práctica (qué haría / qué priorizaría y por qué), anclada solo a los módulos listados."
    ),
    'diagnostico': (
        "FORMATO OBLIGATORIO DEL RETO: situación con un síntoma o problema observado + UNA pregunta "
        "de diagnóstico (qué revisaría primero y cómo lo comprobaría)."
    ),
    'plan_accion': (
        "FORMATO OBLIGATORIO DEL RETO: situación real + UNA pregunta que pida un plan concreto "
        "para esta semana (qué, cuándo, con qué recursos)."
    ),
    'aplicacion_practica': (
        "FORMATO OBLIGATORIO DEL RETO: invite a aplicar lo aprendido a su finca, hogar o trabajo "
        "con UNA sola pregunta (qué cambiaría mañana y cómo lo mediría)."
    ),
    'reflexion': (
        "FORMATO OBLIGATORIO DEL RETO: UNA pregunta de reflexión breve (qué aprendió y cómo lo "
        "usaría), sin tono de examen ni listas."
    ),
}


def _resumen_micros_modulo(modulo, limite: int = 4) -> str:
    """Títulos de pasos activos para anclar el reto al módulo, no a otro dominio."""
    if modulo is None:
        return ''
    try:
        from .module_steps import pasos_activos_qs

        qs = pasos_activos_qs(modulo).order_by('orden', 'id')[:limite]
    except Exception:
        return ''
    lineas = []
    for p in qs:
        t = (getattr(p, 'titulo', None) or '').strip()
        if not t:
            t = (getattr(p, 'contenido', None) or '').strip()[:80]
        if t:
            lineas.append(f"  · {t}")
    if not lineas:
        return ''
    num = getattr(modulo, 'numero', '?')
    return f"MICROLECCIONES DEL MÓDULO {num} (use este vocabulario):\n" + '\n'.join(lineas)


def armar_guia_reto_para_prompt(curso=None, modulo_checkpoint=None) -> tuple[str, str]:
    """
    Une guía del módulo checkpoint (prioridad) + guía del curso.
    Devuelve (texto_para_prompt, tipo_reto_key).
    """
    partes: list[str] = []
    tipo = ''
    if modulo_checkpoint is not None:
        tipo = (getattr(modulo_checkpoint, 'tipo_reto_ia', None) or '').strip()
        if not tipo:
            tipo = modulo_checkpoint.TIPO_RETO_APLICACION
        guia_m = (getattr(modulo_checkpoint, 'reto_guia_ia', None) or '').strip()
        if guia_m:
            num = getattr(modulo_checkpoint, 'numero', '?')
            partes.append(
                f"GUÍA DEL MÓDULO CHECKPOINT {num} (prioridad absoluta; adaptar sin inventar otro tema):\n"
                f"{_quitar_encabezado_acciona(guia_m)}"
            )
        micros = _resumen_micros_modulo(modulo_checkpoint)
        if micros:
            partes.append(micros)
    curso_ej = ''
    if curso is not None:
        curso_ej = (getattr(curso, 'preguntas_ejemplo_ia', None) or '').strip()
    if curso_ej:
        label = (
            'GUÍA DEL CURSO (complemento; la del módulo manda si hay conflicto)'
            if partes
            else 'PREGUNTAS/RETOS EJEMPLO DEL INSTRUCTOR (prioridad absoluta; adaptar al curso)'
        )
        partes.append(f"{label}:\n{_quitar_encabezado_acciona(curso_ej)}")
    return '\n\n'.join(partes), tipo


def generar_reto_facilitador(
    modulos_cubiertos,
    curso_nombre,
    estudiante_nombre="Estudiante",
    preguntas_ejemplo="",
    *,
    curso=None,
    modulo_checkpoint=None,
    tipo_reto="",
) -> str:
    """
    Facilitadora Claudia genera un RETO ABR que cubre los módulos indicados.
    Se llama después de que Darío termina (módulos 3 y 5).

    Args:
        modulos_cubiertos: lista de instancias Modulo que cubre el reto
        curso_nombre: nombre del curso
        estudiante_nombre: nombre del estudiante
        preguntas_ejemplo: texto ya compuesto (opcional si se pasa curso/módulo)
        curso: instancia Curso (para armar guía si preguntas_ejemplo vacío)
        modulo_checkpoint: módulo que disparó el checkpoint (tipo + guía propias)
        tipo_reto: clave de plantilla; si vacío se toma del módulo checkpoint

    Returns:
        str: mensaje con el reto
    """
    client = _get_client()
    if not client:
        return _fallback_reto(modulos_cubiertos, curso_nombre)

    if not modulo_checkpoint and modulos_cubiertos:
        modulo_checkpoint = modulos_cubiertos[-1]
    if curso is None and modulos_cubiertos:
        curso = getattr(modulos_cubiertos[0], 'curso', None)

    guia_compuesta, tipo_desde_mod = armar_guia_reto_para_prompt(curso, modulo_checkpoint)
    if guia_compuesta:
        preguntas_ejemplo = guia_compuesta
    tipo_reto = (tipo_reto or tipo_desde_mod or '').strip()

    if preguntas_ejemplo:
        preguntas_ejemplo = _quitar_encabezado_acciona(str(preguntas_ejemplo).strip())

    # Resumen de módulos (más contexto = menos mezcla con otros dominios)
    _lim = 900
    modulos_info = ""
    for m in modulos_cubiertos:
        contenido_corto = (m.contenido[:_lim] if m.contenido else m.descripcion or '')
        modulos_info += f"- Módulo {m.numero}: {m.titulo}\n  Contenido: {contenido_corto}\n"

    # RAG: pregunta anclada a títulos + nombre del curso (mejor relevancia que consulta genérica)
    titulos_linea = ", ".join(f"{m.numero}. {m.titulo}" for m in modulos_cubiertos) if modulos_cubiertos else ""
    pregunta_rag = (
        f"Situación práctica y reto corto coherente con el curso «{curso_nombre}» "
        f"según estos módulos: {titulos_linea}"
    )

    contexto_rag = ""
    try:
        from .rag_manager import rag_manager
        curso_rag = curso or (modulos_cubiertos[0].curso if modulos_cubiertos else None)
        if curso_rag:
            cliente_id = curso_rag.cliente_id if curso_rag.cliente_id else 0
            contexto_rag = rag_manager.obtener_contexto_para_ia(
                cliente_id=cliente_id,
                curso_id=curso_rag.id,
                pregunta=pregunta_rag,
                max_chars=1200
            )
            logger.info(
                "[reto] RAG curso_id=%s curso=%s modulos=%s chars=%s tipo=%s",
                curso_rag.id,
                curso_nombre[:60],
                [m.id for m in modulos_cubiertos],
                len(contexto_rag or ""),
                tipo_reto or '-',
            )
    except Exception as e:
        logger.warning(f"[RAG] Error en reto facilitador: {e}")

    ejemplo_txt = ""
    if preguntas_ejemplo:
        ejemplo_txt = f"\n{preguntas_ejemplo}\n"

    max_modulo = max((getattr(m, "numero", 0) or 0) for m in modulos_cubiertos) if modulos_cubiertos else 0
    if max_modulo <= 3:
        instruccion_pregunta = (
            "Genere UN reto conversacional breve: situación cotidiana alineada SOLO con los temas de los módulos anteriores "
            "(ej. ingresos/gastos/ahorro/metas si es ese el contenido). "
            "Una sola pregunta integrada que pida aplicar lo estudiado. "
            "NO mencione plagas, Diatraea, cultivos ni agricultura si los módulos no hablan de ello."
        )
    else:
        instruccion_pregunta = (
            "Genere UN reto: situación cotidiana coherente con los módulos listados + UNA pregunta integrada "
            "(qué revisaría o priorizaría y qué haría en la práctica), siempre en el dominio de este curso."
        )

    tipo_txt = _INSTRUCCION_TIPO_RETO.get(tipo_reto, '')
    if tipo_txt:
        instruccion_pregunta = f"{tipo_txt}\n{instruccion_pregunta}"

    prompt_usuario = f"""OBLIGATORIO:
- Curso actual (no mezclar con otros): *{curso_nombre}*
- Use únicamente los temas de «MÓDULOS QUE CUBRE ESTE RETO» y el RAG de ESTE curso.

Participante: {estudiante_nombre}

MÓDULOS QUE CUBRE ESTE RETO:
{modulos_info}
{contexto_rag}
{ejemplo_txt}
{instruccion_pregunta}

PROHIBIDO: Inventar otro tipo de curso o ejemplo de otro programa distinto al indicado arriba.
PROHIBIDO: Incluir la palabra ACCIONA (o Acciona) en el mensaje."""

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
        respuesta = _quitar_encabezado_acciona(response.choices[0].message.content.strip())
        logger.info(f"✅ Facilitadora reto: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        logger.error(f"❌ Error Facilitadora reto: {e}")
        return _fallback_reto(modulos_cubiertos, curso_nombre)


def _extraer_nota_1_5(feedback: str) -> float:
    import re

    texto = feedback or ''
    for patron in (
        r'(\d+(?:[.,]\d+)?)\s*/\s*5',
        r'nota\s*(?:final)?\s*:?\s*(\d+(?:[.,]\d+)?)',
    ):
        match = re.search(patron, texto, re.I)
        if match:
            valor = float(match.group(1).replace(',', '.'))
            return min(5.0, max(1.0, valor))
    return 3.5


def evaluar_reto_facilitador(modulos_cubiertos, respuesta_estudiante, reto_original,
                              estudiante_nombre="Estudiante", curso_nombre=None,
                              modo_gamificacion=None) -> tuple:
    """
    Facilitadora evalúa la respuesta al reto con rúbrica ABR.

    Returns:
        tuple: (puntaje int 1-10 o nota float 1-5, feedback: str)
    """
    from core.gamificacion_modo import MODO_CALIFICACION, MODO_PUNTOS

    modo = modo_gamificacion or MODO_PUNTOS
    usar_notas = modo == MODO_CALIFICACION
    respuesta_limpia = (respuesta_estudiante or "").strip()
    if _es_respuesta_sin_contenido_reto(respuesta_limpia):
        # Regla anti-alucinación: si la persona dice "no sé"/"no se", nunca inventar evidencia.
        return 1, _feedback_respuesta_sin_contenido(estudiante_nombre)

    client = _get_client()
    if not client:
        return 0, _fallback_evaluacion_reto(estudiante_nombre)

    nombre_curso = (curso_nombre or "").strip()
    if not nombre_curso and modulos_cubiertos:
        c0 = getattr(modulos_cubiertos[0], "curso", None)
        nombre_curso = (getattr(c0, "nombre", "") or "").strip()

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

    prompt_usuario = f"""CURSO (único marco de evaluación; no exija conceptos ajenos): {nombre_curso or 'Curso actual'}

Módulos cubiertos:
{modulos_info}
{contexto_rag}

RETO PLANTEADO: {reto_original}
RESPUESTA DEL PARTICIPANTE ({estudiante_nombre}): {respuesta_limpia}

Evalúe según la rúbrica y el dominio de este curso. Dé retroalimentación y {'nota 1-5' if usar_notas else 'puntaje 1-10'}."""

    system_prompt = (
        PROMPT_FACILITADOR_EVALUACION_NOTAS if usar_notas else PROMPT_FACILITADOR_EVALUACION
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.5,
            max_tokens=250,
            timeout=12
        )
        feedback = response.choices[0].message.content.strip()

        import re
        if usar_notas:
            nota = _extraer_nota_1_5(feedback)
            logger.info("✅ Facilitadora evaluación reto (notas): %s/5", nota)
            return nota, feedback

        puntaje = 7
        match = re.search(r'(\d+)\s*/\s*10', feedback)
        if match:
            puntaje = min(10, max(1, int(match.group(1))))

        logger.info(f"✅ Facilitadora evaluación reto: {puntaje}/10")
        return puntaje, feedback
    except Exception as e:
        logger.error(f"❌ Error evaluación reto: {e}")
        return 0, _fallback_evaluacion_reto(estudiante_nombre)


def generar_respuesta_asistente(modulos_cubiertos, pregunta_estudiante,
                                 estudiante_nombre="Estudiante",
                                 nombre_asistente=None) -> str:
    """
    El asistente (compañero) responde una pregunta del estudiante basada en RAG/módulos.
    Máximo 2 preguntas antes de pasar a la Facilitadora.

    Returns:
        str: respuesta del asistente
    """
    client = _get_client()
    na = (nombre_asistente or "").strip()
    if not na and modulos_cubiertos:
        c = modulos_cubiertos[0].curso
        cl = getattr(c, "cliente", None) if c else None
        na = (
            (getattr(cl, "nombre_agente_asistente", None) or "")
            or (getattr(c, "nombre_agente_asistente", None) or "")
            or "Darío"
        )
    na = (na or "Darío").strip() or "Darío"

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
                {"role": "system", "content": _prompt_sistema_asistente(na)},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7,
            max_tokens=120,
            timeout=10
        )
        respuesta = _quitar_encabezado_acciona(response.choices[0].message.content.strip())
        logger.info(f"✅ Asistente ({na}) respuesta: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        logger.error(f"❌ Error respuesta asistente: {e}")
        return _fallback_respuesta_asistente()


def _fallback_reto(modulos_cubiertos, curso_nombre):
    """Reto de fallback sin IA: anclado al nombre del curso y a los módulos (sin tema fijo de agricultura)."""
    if modulos_cubiertos:
        temas = ", ".join(f"{m.numero}. {m.titulo}" for m in modulos_cubiertos)
    else:
        temas = curso_nombre
    return (
        f"En el marco del curso *{curso_nombre}*, después de repasar: {temas}, "
        f"piense en una situación de su día a día donde deba aplicar lo aprendido.\n\n"
        f"¿Qué haría usted de forma concreta (primer paso y criterio para saber si va bien)? ✍️\n\n"
        f"Escriba o envíe un audio con su respuesta."
    )


def _fallback_evaluacion_reto(estudiante_nombre: str = "Estudiante"):
    """Sin IA disponible: no regalar puntos; pedir reintento."""
    return (
        f"{estudiante_nombre}, en este momento no pude evaluar su respuesta por un problema técnico.\n\n"
        "Por favor envíe de nuevo su respuesta al reto (puede ser más breve). "
        "En este intento *no se registró puntaje*.\n\n"
        "Disculpe la molestia. 🌱"
    )


def _es_respuesta_sin_contenido_reto(respuesta: str) -> bool:
    """Detecta respuestas vacías o explícitamente sin contenido (ej. 'no sé', 'bueno')."""
    r = (respuesta or "").strip().lower()
    r = re.sub(r'\s+', ' ', r)
    if not r:
        return True
    expresiones_directas = {
        "no se",
        "no sé",
        "nose",
        "ni idea",
        "no tengo idea",
        "no lo se",
        "no lo sé",
        "no sabria",
        "no sabría",
        "n/a",
        "na",
        "bueno",
        "ok",
        "okay",
        "vale",
        "listo",
        "gracias",
        "si",
        "sí",
        "bien",
        "dale",
        "perfecto",
        "esta bien",
        "está bien",
    }
    if r in expresiones_directas:
        return True
    # Variantes cortas tipo "pues no sé profe" o "bueno profe"
    if len(r) <= 40 and (
        "no se" in r or "no sé" in r or re.match(r'^(bueno|ok|vale|bien|si|sí)\b', r)
    ):
        return True
    # Muy corta sin verbos de acción ni sustantivos técnicos (≤3 palabras genéricas)
    palabras = r.split()
    if len(palabras) <= 2 and all(p in expresiones_directas for p in palabras):
        return True
    return False


def _feedback_respuesta_sin_contenido(estudiante_nombre: str) -> str:
    """Feedback duro, pero justo, sin inventar evidencia cuando la respuesta fue 'no sé'."""
    return (
        f"1. {estudiante_nombre}, gracias por responder. En este intento usted indicó que no sabía la respuesta, "
        "así que no hay evidencia técnica para evaluar diagnóstico ni acción.\n\n"
        "2. Para subir su puntaje, responda con al menos: (a) cómo diagnosticaría, (b) qué acción concreta aplicaría, "
        "indicando qué, cuánto, cuándo y con qué.\n\n"
        "3. Puntaje total: 1/10\n"
        "4. Desglose: Enfoque 0/3 | Fundamentación 0/4 | Claridad 1/3\n\n"
        "5. Veredicto por componente:\n"
        "   - Diagnóstico: no logrado + no presentó método de diagnóstico.\n"
        "   - Acción/Control: no logrado + no propuso acción de control concreta.\n\n"
        "Siga adelante: con una respuesta específica su resultado mejora de inmediato. 🌱"
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
