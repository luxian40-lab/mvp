
PROMPT_FACILITADOR_RETO = """Eres la Facilitadora de eki. Tu rol es plantear un reto conversacional al participante.
- Describe una situación real en 2-3 oraciones alineada SOLO al tema de los módulos y al nombre del curso recibidos en el mensaje (finanzas del hogar, emprendimiento rural, agricultura, otro — según ese contexto, sin inventar otro dominio).
- En seguida, UNA SOLA pregunta integrada (puede incluir qué revisaría o priorizaría y qué haría en la práctica), coherente con ese mismo tema. Sin títulos ni líneas intermedias tipo encabezado.
- PROHIBIDO listas numeradas tipo "1), 2), 3)" o varias preguntas sueltas.
1. TRATO DE USTED. NUNCA tutear.
2. MÁXIMO 80 PALABRAS en total.
3. Lenguaje sencillo, cercano al contexto rural/urbano que corresponda al curso.
4. Máximo 2 emojis al final.
5. CERO alucinación: solo temas que aparezcan en MÓDULOS / RAG / nombre del curso. PROHIBIDO mezclar plagas, cultivos o finanzas si los módulos no hablan de eso.
6. Termina con: "Escriba o envíe un audio con su respuesta."
7. Sin tecnicismos innecesarios ni tono de examen.
8. PROHIBIDO usar la palabra "ACCIONA", "Acciona" o variaciones como encabezado o en negrita."""
- Evalúe según el dominio de los módulos (presupuesto, ahorro, metas, campo, u otro): no exija conceptos que no estén en el material."""
# PROMPT ASISTENTE — Companion, tutea (nombre según cliente/curso)
def _prompt_sistema_asistente(nombre_asistente: str) -> str:
    na = (nombre_asistente or "Darío").strip() or "Darío"
    return f"""Eres {na}, el asistente y compañero de estudio de eki.
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

    if preguntas_ejemplo:
        preguntas_ejemplo = _quitar_encabezado_acciona(str(preguntas_ejemplo).strip())

    # Resumen de módulos (más contexto = menos mezcla con otros dominios)
    _lim = 900
        contenido_corto = (m.contenido[:_lim] if m.contenido else m.descripcion or '')
    # RAG: pregunta anclada a títulos + nombre del curso (mejor relevancia que consulta genérica)
    titulos_linea = ", ".join(f"{m.numero}. {m.titulo}" for m in modulos_cubiertos) if modulos_cubiertos else ""
    pregunta_rag = (
        f"Situación práctica y reto corto coherente con el curso «{curso_nombre}» "
        f"según estos módulos: {titulos_linea}"
    )

                pregunta=pregunta_rag,
                max_chars=1200
            )
            logger.info(
                "[reto] RAG curso_id=%s curso=%s modulos=%s chars=%s",
                curso.id,
                curso_nombre[:60],
                [m.id for m in modulos_cubiertos],
                len(contexto_rag or ""),
        ejemplo_txt = (
            f"\nPREGUNTAS/RETOS EJEMPLO DEL INSTRUCTOR (prioridad absoluta; adaptar al curso "
            f"«{curso_nombre}» y a los módulos listados, sin inventar otro tema):\n{preguntas_ejemplo}\n"
        )
            "Genere UN reto conversacional breve: situación cotidiana alineada SOLO con los temas de los módulos anteriores "
            "(ej. ingresos/gastos/ahorro/metas si es ese el contenido). "
            "Una sola pregunta integrada que pida aplicar lo estudiado. "
            "NO mencione plagas, Diatraea, cultivos ni agricultura si los módulos no hablan de ello."
            "Genere UN reto: situación cotidiana coherente con los módulos listados + UNA pregunta integrada "
            "(qué revisaría o priorizaría y qué haría en la práctica), siempre en el dominio de este curso."
    prompt_usuario = f"""OBLIGATORIO:
- Curso actual (no mezclar con otros): *{curso_nombre}*
- Use únicamente los temas de «MÓDULOS QUE CUBRE ESTE RETO» y el RAG de ESTE curso.


PROHIBIDO: Inventar otro tipo de curso o ejemplo de otro programa distinto al indicado arriba.
PROHIBIDO: Incluir la palabra ACCIONA (o Acciona) en el mensaje."""
        respuesta = _quitar_encabezado_acciona(response.choices[0].message.content.strip())
                              estudiante_nombre="Estudiante", curso_nombre=None) -> tuple:
    nombre_curso = (curso_nombre or "").strip()
    if not nombre_curso and modulos_cubiertos:
        c0 = getattr(modulos_cubiertos[0], "curso", None)
        nombre_curso = (getattr(c0, "nombre", "") or "").strip()

    prompt_usuario = f"""CURSO (único marco de evaluación; no exija conceptos ajenos): {nombre_curso or 'Curso actual'}

Evalúe según la rúbrica y el dominio de este curso. Dé retroalimentación y puntaje."""
                                 estudiante_nombre="Estudiante",
                                 nombre_asistente=None) -> str:
    El asistente (compañero) responde una pregunta del estudiante basada en RAG/módulos.
        str: respuesta del asistente
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

                {"role": "system", "content": _prompt_sistema_asistente(na)},
        respuesta = _quitar_encabezado_acciona(response.choices[0].message.content.strip())
        logger.info(f"✅ Asistente ({na}) respuesta: {respuesta[:50]}...")
        logger.error(f"❌ Error respuesta asistente: {e}")
    """Reto de fallback sin IA: anclado al nombre del curso y a los módulos (sin tema fijo de agricultura)."""
    if modulos_cubiertos:
        temas = ", ".join(f"{m.numero}. {m.titulo}" for m in modulos_cubiertos)
    else:
        temas = curso_nombre
        f"En el marco del curso *{curso_nombre}*, después de repasar: {temas}, "
        f"piense en una situación de su día a día donde deba aplicar lo aprendido.\n\n"
        f"¿Qué haría usted de forma concreta (primer paso y criterio para saber si va bien)? ✍️\n\n"