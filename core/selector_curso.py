"""
Función para continuar con un curso específico seleccionado
"""

from django.utils import timezone


def _curso_desde_campana_cliente(estudiante, org):
    """
    Curso destino declarado en campañas del cliente (envío registrado o estudiante en destinatarios).
    Cubre cursos con Curso.cliente nulo pero asignados vía Campana.curso_destino.
    """
    from .models import Campana, EnvioLog

    if not org:
        return None

    log = (
        EnvioLog.objects.filter(estudiante=estudiante, campana__cliente_id=org.id)
        .select_related('campana__curso_destino')
        .order_by('-fecha_envio')
        .first()
    )
    if log and log.campana and log.campana.curso_destino_id:
        cd = log.campana.curso_destino
        if cd and cd.activo:
            return cd

    camp = (
        Campana.objects.filter(
            cliente=org,
            curso_destino__isnull=False,
            curso_destino__activo=True,
            destinatarios=estudiante,
        )
        .select_related('curso_destino')
        .order_by('-id')
        .first()
    )
    if camp and camp.curso_destino:
        return camp.curso_destino
    return None


def cursos_visibles_para_estudiante(estudiante):
    """
    Cursos activos que el estudiante puede tomar al inscribirse o ver en el menú.
    Si tiene cliente: cursos con ese cliente; si no hay ninguno, el curso destino de una
    campaña del cliente hacia este estudiante (Curso.cliente puede ser nulo).
    Si no tiene cliente: todos los cursos activos (sandbox / legacy).
    """
    from .models import Curso

    org = getattr(estudiante, 'cliente', None)
    if org:
        directos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
        if directos.exists():
            return directos
        promo = _curso_desde_campana_cliente(estudiante, org)
        if promo:
            return Curso.objects.filter(pk=promo.pk, activo=True)
        return Curso.objects.none()
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
        if c.cliente_id is None or c.cliente_id == estudiante.cliente_id:
            if not progreso_existente.modulo_actual:
                primer = c.modulos.order_by('numero').first()
                if primer:
                    progreso_existente.modulo_actual = primer
                    from .module_steps import reset_progreso_pasos_modulo
                    reset_progreso_pasos_modulo(progreso_existente, save=False)
                    progreso_existente.save(
                        update_fields=[
                            'modulo_actual',
                            'paso_actual_modulo',
                            'esperando_respuesta_evaluacion_paso',
                            'paso_evaluacion_paso_id',
                        ]
                    )
            return progreso_existente

    cursos = cursos_visibles_para_estudiante(estudiante)
    curso = cursos.first()
    if not curso:
        curso = _curso_desde_campana_cliente(estudiante, estudiante.cliente)
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
        from .module_steps import reset_progreso_pasos_modulo
        reset_progreso_pasos_modulo(progreso, save=False)
        progreso.save(
            update_fields=[
                'modulo_actual',
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso_id',
            ]
        )
    return progreso


def resolver_curso_post_confirmacion(estudiante):
    """
    Tras confirmar datos (B2B): qué curso iniciar.
    Progreso incompleto coherente → catálogo cliente=org → curso de campaña → (solo sin org) primer curso activo global.
    """
    from .models import Curso, ProgresoEstudiante

    org = getattr(estudiante, 'cliente', None)

    progreso_existente = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, completado=False)
        .select_related('curso')
        .order_by('-fecha_inicio')
        .first()
    )
    if progreso_existente and progreso_existente.curso and progreso_existente.curso.activo:
        c = progreso_existente.curso
        if not org or c.cliente_id is None or c.cliente_id == org.id:
            return c

    if org:
        curso = (
            Curso.objects.filter(cliente=org, activo=True)
            .order_by('orden', 'nombre')
            .first()
        )
        if curso:
            return curso
        curso = _curso_desde_campana_cliente(estudiante, org)
        if curso:
            return curso
        return None

    return Curso.objects.filter(activo=True).order_by('orden', 'nombre').first()


def continuar_curso_seleccionado(estudiante_id: int, indice_curso: int, mensaje_original: str):
    """
    Continúa con un curso elegido por número.
    Usa el mismo orden que la lista vista por el usuario: catálogo por cliente o,
    si venía de *continuar* con varios progresos activos, ese subconjunto ordenado por fecha.
    Crea ProgresoEstudiante si aún no existe.

    Respeta el drip (espera entre módulos) como el flujo principal en response_templates.
    """
    from .models import Estudiante, Curso, ProgresoEstudiante, ModuloCompletado
    from .drip_schedule import drip_bloquea_siguiente_modulo, mensaje_bloqueo_avance_siguiente_modulo
    from .response_templates import obtener_video_url, partes_presentacion_agentes_curso

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
        from .module_steps import reset_progreso_pasos_modulo
        reset_progreso_pasos_modulo(progreso, save=False)
        progreso.save(
            update_fields=[
                'modulo_actual',
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso_id',
            ]
        )

    mensaje_lower = mensaje_original.strip().lower()

    def _persist_curso_foco():
        ctx = dict(estudiante.contexto_temporal or {})
        ctx.pop('tipo', None)
        ctx['curso_activo_id'] = curso_seleccionado.id
        estudiante.contexto_temporal = ctx
        estudiante.save(update_fields=['contexto_temporal'])

    def _prefijo_agentes_primera_inscripcion_selector():
        if not creado:
            return []
        return partes_presentacion_agentes_curso(estudiante, curso_seleccionado)

    # Si el mensaje es SOLO un número, mostrar el módulo actual sin avanzar
    if mensaje_original.strip().isdigit():
        if drip_bloquea_siguiente_modulo(progreso, modulo_actual):
            _blk = mensaje_bloqueo_avance_siguiente_modulo(
                estudiante, progreso, modulo_actual
            )
            _persist_curso_foco()
            return _blk or ''

        avance = progreso.porcentaje_avance()

        from .module_steps import (
            modulo_usa_pasos,
            mensaje_recordatorio_paso_actual,
            pasos_activos_qs,
            log_y_mensaje_modo_pasos_sin_pasos,
        )

        if modulo_usa_pasos(modulo_actual):
            if not pasos_activos_qs(modulo_actual).exists():
                _persist_curso_foco()
                return log_y_mensaje_modo_pasos_sin_pasos(
                    modulo_actual, 'selector_curso_digito'
                )
            _np_sel = pasos_activos_qs(modulo_actual).count()
            if (
                progreso.paso_actual_modulo > _np_sel
                and not progreso.esperando_respuesta_evaluacion_paso
            ):
                _persist_curso_foco()
                return (
                    "✅ Ya recibiste todo el material de esta unidad.\n\n"
                    "Escribe *listo* para registrar tu avance y seguir 👇"
                )
            _rem_sel = mensaje_recordatorio_paso_actual(progreso, modulo_actual)
            if _rem_sel:
                _hdr_sel = (
                    f"✅ {'Iniciando' if creado else 'Retomando'} *{curso_seleccionado.emoji or '📚'} "
                    f"{curso_seleccionado.nombre}*\n\n"
                    f"📍 Módulo actual: {modulo_actual.numero}. {modulo_actual.titulo}\n"
                    f"📈 Avance: {avance}%\n\n"
                )
                _inner_sel = _rem_sel[len('[MULTI_MSG]') :]
                _persist_curso_foco()
                _pfx = _prefijo_agentes_primera_inscripcion_selector()
                if _pfx:
                    _inner_parts = [p for p in _inner_sel.split('[SEP]') if p]
                    return '[MULTI_MSG]' + '[SEP]'.join(_pfx + [_hdr_sel] + _inner_parts)
                return '[MULTI_MSG]' + _hdr_sel + '[SEP]' + _inner_sel

        respuesta = f"""✅ {'Iniciando' if creado else 'Retomando'} *{curso_seleccionado.emoji or '📚'} {curso_seleccionado.nombre}*

📍 Módulo actual: {modulo_actual.numero}. {modulo_actual.titulo}
📈 Avance: {avance}%

{modulo_actual.contenido}


Cuando termines, escribe: *"listo"*"""

        # Agregar multimedia si hay
        video_url = obtener_video_url(modulo_actual)
        if video_url:
            respuesta += f"\n\n[MEDIA:{video_url}]"

        _pfx = _prefijo_agentes_primera_inscripcion_selector()
        if _pfx:
            respuesta = '[MULTI_MSG]' + '[SEP]'.join(_pfx + [respuesta])

        _persist_curso_foco()
        return respuesta

    # Si escribieron "listo" o "siguiente", avanzar al siguiente módulo (misma regla de espera que el flujo principal)
    palabras_completar = ['listo', 'siguiente', 'ok', 'dale', 'avanzar', 'sigue', 'continuar']

    if any(palabra in mensaje_lower for palabra in palabras_completar):
        _blk_listo = mensaje_bloqueo_avance_siguiente_modulo(
            estudiante, progreso, modulo_actual
        )
        if _blk_listo:
            _persist_curso_foco()
            return _blk_listo

        from .module_steps import modulo_usa_pasos

        if modulo_usa_pasos(modulo_actual):
            _persist_curso_foco()
            from .response_templates import get_response_for_intent

            return get_response_for_intent(
                'continuar_leccion',
                estudiante.nombre or 'Estudiante',
                estudiante_id=estudiante.id,
                mensaje_original=mensaje_original,
            )

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
            _blk_sig = mensaje_bloqueo_avance_siguiente_modulo(
                estudiante, progreso, modulo_actual
            )
            if _blk_sig:
                _persist_curso_foco()
                return _blk_sig

            progreso.modulo_actual = siguiente_modulo
            from .module_steps import reset_progreso_pasos_modulo
            reset_progreso_pasos_modulo(progreso, save=False)
            progreso.save(
                update_fields=[
                    'modulo_actual',
                    'paso_actual_modulo',
                    'esperando_respuesta_evaluacion_paso',
                    'paso_evaluacion_paso_id',
                ]
            )

            from .module_steps import (
                modulo_usa_pasos,
                pasos_activos_qs,
                entregar_bloque_secciones_desde_paso,
                log_y_mensaje_modo_pasos_sin_pasos,
            )

            _persist_curso_foco()
            if modulo_usa_pasos(siguiente_modulo):
                if not pasos_activos_qs(siguiente_modulo).exists():
                    return log_y_mensaje_modo_pasos_sin_pasos(
                        siguiente_modulo, 'selector_curso_siguiente_modulo'
                    )
                _hdr_next = (
                    f"✅ ¡Completaste {modulo_actual.titulo}!\n\n"
                    f"📚 Siguiente: Módulo {siguiente_modulo.numero} - {siguiente_modulo.titulo}\n\n"
                )
                msg_p = entregar_bloque_secciones_desde_paso(progreso, siguiente_modulo, 1)
                _inner_p = msg_p[len('[MULTI_MSG]') :]
                return '[MULTI_MSG]' + _hdr_next + '[SEP]' + _inner_p

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
