"""
Función para continuar con un curso específico seleccionado
"""

from django.utils import timezone


def cursos_visibles_para_estudiante(estudiante):
    """
    Cursos activos que el estudiante puede tomar al inscribirse o ver en el menú.
    Si tiene cliente: solo cursos de esa organización (mismo criterio en lista y al elegir número).
    Si no: todos los cursos activos (sandbox / legacy).
    """
    from .models import Curso

    org = getattr(estudiante, 'cliente', None)
    if org:
        return Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    return Curso.objects.filter(activo=True).order_by('orden', 'nombre')


def asegurar_inscripcion_catalogo_cliente(estudiante):
    """
    B2B: el estudiante ya pertenece a un cliente; asegura un ProgresoEstudiante activo
    en el catálogo de ese cliente (progreso existente o primer curso activo), alineado
    con el flujo post-confirmación en views (sin menú numerado).

    Retorna ProgresoEstudiante o None si el cliente no tiene cursos activos.
    """
    from .models import ProgresoEstudiante

    if not getattr(estudiante, 'cliente_id', None):
        return None

    progreso_existente = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, completado=False)
        .select_related('curso')
        .order_by('-fecha_inicio')
        .first()
    )
    if progreso_existente and progreso_existente.curso and progreso_existente.curso.activo:
        c = progreso_existente.curso
        if c.cliente_id == estudiante.cliente_id:
            if not progreso_existente.modulo_actual:
                primer = c.modulos.order_by('numero').first()
                if primer:
                    progreso_existente.modulo_actual = primer
                    progreso_existente.save(update_fields=['modulo_actual'])
            return progreso_existente

    cursos = cursos_visibles_para_estudiante(estudiante)
    curso = cursos.first()
    if not curso:
        return None

    primer_modulo = curso.modulos.order_by('numero').first()
    progreso, _ = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso,
        defaults={'completado': False, 'modulo_actual': primer_modulo},
    )
    if not progreso.modulo_actual and primer_modulo:
        progreso.modulo_actual = primer_modulo
        progreso.save(update_fields=['modulo_actual'])
    return progreso


def continuar_curso_seleccionado(estudiante_id: int, indice_curso: int, mensaje_original: str):
    """
    Continúa con un curso elegido por número.
    Usa el mismo orden que la lista vista por el usuario: catálogo por cliente o,
    si venía de *continuar* con varios progresos activos, ese subconjunto ordenado por fecha.
    Crea ProgresoEstudiante si aún no existe.

    Respeta el drip (espera entre módulos) como el flujo principal en response_templates.
    """
    from .models import Estudiante, Curso, ProgresoEstudiante, ModuloCompletado
    from .drip_schedule import dias_espera_efectivos, drip_bloquea_siguiente_modulo, fecha_desbloqueo_drip
    from .response_templates import _mensaje_bloqueo_drip, obtener_video_url

    try:
        estudiante = Estudiante.objects.select_related('cliente').get(id=estudiante_id)
    except Estudiante.DoesNotExist:
        return "Error: No se encontró tu perfil de estudiante."

    ctx = estudiante.contexto_temporal or {}
    # Lista mostrada al elegir entre varios *progresos* activos (continuar_leccion), no el catálogo de inscripción
    if ctx.get('tipo') == 'seleccion_curso':
        progresos_ordenados = ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False,
            curso__activo=True,
        ).select_related('curso').order_by('-fecha_inicio')
        cursos_list = [p.curso for p in progresos_ordenados]
    else:
        cursos_list = list(cursos_visibles_para_estudiante(estudiante))

    # Validar índice
    if indice_curso < 1 or indice_curso > len(cursos_list):
        return f"Número inválido. Tienes {len(cursos_list)} cursos disponibles. Escribe un número del 1 al {len(cursos_list)}."

    # Obtener el curso seleccionado
    curso_seleccionado = cursos_list[indice_curso - 1]

    # Buscar o crear progreso para este curso
    progreso, creado = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso_seleccionado,
        defaults={'completado': False}
    )

    if progreso.completado:
        return (
            f"✅ Ya completaste *{curso_seleccionado.nombre}*\n\n"
            f"🎓 Tu certificado está disponible.\n\n"
            f"Escribe *menú* para ver las opciones o selecciona otro curso."
        )

    # Obtener módulo actual
    modulo_actual = progreso.modulo_actual
    if not modulo_actual:
        modulo_actual = curso_seleccionado.modulos.order_by('numero').first()
        if not modulo_actual:
            return f"El curso {curso_seleccionado.nombre} no tiene módulos configurados."
        progreso.modulo_actual = modulo_actual
        progreso.save()

    mensaje_lower = mensaje_original.strip().lower()

    def _persist_curso_foco():
        ctx = dict(estudiante.contexto_temporal or {})
        ctx.pop('tipo', None)
        ctx['curso_activo_id'] = curso_seleccionado.id
        estudiante.contexto_temporal = ctx
        estudiante.save(update_fields=['contexto_temporal'])

    # Si el mensaje es SOLO un número, mostrar el módulo actual sin avanzar
    if mensaje_original.strip().isdigit():
        if drip_bloquea_siguiente_modulo(progreso, modulo_actual):
            dias_drip = dias_espera_efectivos(estudiante, curso_seleccionado)
            fecha_desbloqueo = fecha_desbloqueo_drip(progreso.fecha_ultimo_avance, dias_drip)
            _persist_curso_foco()
            return _mensaje_bloqueo_drip(fecha_desbloqueo)

        avance = progreso.porcentaje_avance()

        respuesta = f"""✅ {'Iniciando' if creado else 'Retomando'} *{curso_seleccionado.emoji or '📚'} {curso_seleccionado.nombre}*

📍 Módulo actual: {modulo_actual.numero}. {modulo_actual.titulo}
📈 Avance: {avance}%

{modulo_actual.contenido}


Cuando termines, escribe: *"listo"*"""

        # Agregar multimedia si hay
        video_url = obtener_video_url(modulo_actual)
        if video_url:
            respuesta += f"\n\n[MEDIA:{video_url}]"

        _persist_curso_foco()
        return respuesta

    # Si escribieron "listo" o "siguiente", avanzar al siguiente módulo (misma regla de espera que el flujo principal)
    palabras_completar = ['listo', 'siguiente', 'ok', 'dale', 'avanzar', 'sigue', 'continuar']

    if any(palabra in mensaje_lower for palabra in palabras_completar):
        dias_drip = dias_espera_efectivos(estudiante, curso_seleccionado)
        if dias_drip > 0:
            ya_completo_modulo = ModuloCompletado.objects.filter(
                progreso=progreso,
                modulo=modulo_actual
            ).exists()
            if ya_completo_modulo and progreso.fecha_ultimo_avance:
                fecha_desbloqueo = fecha_desbloqueo_drip(progreso.fecha_ultimo_avance, dias_drip)
                if fecha_desbloqueo and timezone.localdate() < fecha_desbloqueo:
                    _persist_curso_foco()
                    return _mensaje_bloqueo_drip(fecha_desbloqueo)

        # Marcar módulo actual como completado
        try:
            creado_mc, created_mc = ModuloCompletado.objects.get_or_create(
                progreso=progreso,
                modulo=modulo_actual
            )
            if created_mc:
                progreso.fecha_ultimo_avance = timezone.now()
                progreso.save(update_fields=['fecha_ultimo_avance'])
        except Exception as e:
            print(f"Error al completar módulo: {e}")

        # Buscar siguiente módulo
        siguiente_modulo = curso_seleccionado.modulos.filter(
            numero__gt=modulo_actual.numero
        ).order_by('numero').first()

        if siguiente_modulo:
            if dias_drip > 0 and progreso.fecha_ultimo_avance:
                fecha_desbloqueo = fecha_desbloqueo_drip(progreso.fecha_ultimo_avance, dias_drip)
                if fecha_desbloqueo and timezone.localdate() < fecha_desbloqueo:
                    _persist_curso_foco()
                    return _mensaje_bloqueo_drip(fecha_desbloqueo)

            progreso.modulo_actual = siguiente_modulo
            progreso.save()

            video_url = obtener_video_url(siguiente_modulo)

            respuesta = f"""✅ ¡Completaste {modulo_actual.titulo}!

📚 Siguiente: Módulo {siguiente_modulo.numero} - {siguiente_modulo.titulo}

{siguiente_modulo.contenido}"""

            if video_url:
                respuesta += f"\n\n🎥 Video educativo:\n{video_url}"

            respuesta += "\n\n\nCuando termines, escribe: *\"listo\"*"

            _persist_curso_foco()
            return respuesta
        else:
            progreso.completado = True
            progreso.save()

            ctx = dict(estudiante.contexto_temporal or {})
            ctx.pop('curso_activo_id', None)
            estudiante.contexto_temporal = ctx or None
            estudiante.save(update_fields=['contexto_temporal'])

            return f"""🎉 ¡FELICITACIONES!

Has completado el curso: {curso_seleccionado.nombre}

🏆 Tu certificado se está generando.

Escribe *menú* para ver las opciones."""

    _persist_curso_foco()
    return f"Escribe *listo* cuando termines el módulo o *menú* para volver."
