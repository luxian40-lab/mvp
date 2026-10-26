"""Intent `opcion_2` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.models import Curso, Estudiante
    from core.selector_curso import cursos_visibles_para_estudiante, asegurar_inscripcion_catalogo_cliente

    estudiante_id_menu = kwargs.get('estudiante_id')
    if estudiante_id_menu:
        try:
            _est_cur = Estudiante.objects.select_related('cliente').get(id=estudiante_id_menu)
            if _est_cur.cliente_id:
                prog = asegurar_inscripcion_catalogo_cliente(_est_cur)
                if not prog or not prog.curso:
                    return (
                        "Tu organización aún no tiene cursos activos en este momento. ⚠️\n\n"
                        "Escribe *ayuda* si necesitas soporte."
                    )
                cursos_list = list(cursos_visibles_para_estudiante(_est_cur))
                if len(cursos_list) <= 1:
                    return (
                        f"📚 Tu curso asignado es *{prog.curso.nombre}*.\n\n"
                        "Escribe *continuar* para seguir."
                    )
                respuesta = f"📚 *Cursos en {_est_cur.cliente.nombre}*\n\n"
                for idx, curso in enumerate(cursos_list, 1):
                    respuesta += f"{idx}. {curso.emoji} *{curso.nombre}*\n"
                    respuesta += f"   📅 {curso.duracion_semanas} semanas | 📖 {curso.modulos.count()} módulos\n\n"
                respuesta += (
                    "👉 Escribe el *número* del curso que quieres (o *continuar* para seguir el actual).\n\n"
                    "Escribe *menú* para volver al mensaje de bienvenida."
                )
                _est_cur.estado_onboarding = 'esperando_seleccion_curso'
                _est_cur.save(update_fields=['estado_onboarding'])
                return respuesta
        except Estudiante.DoesNotExist:
            pass

        try:
            _est_cur = Estudiante.objects.select_related('cliente').get(id=estudiante_id_menu)
            cursos_activos = cursos_visibles_para_estudiante(_est_cur)
        except Estudiante.DoesNotExist:
            from django.db.models import Count
            cursos_activos = (
                Curso.objects.filter(activo=True)
                .annotate(_n_modulos=Count('modulos'))
                .filter(_n_modulos__gt=0)
                .order_by('orden', 'nombre')
            )
    else:
        from django.db.models import Count
        cursos_activos = (
            Curso.objects.filter(activo=True)
            .annotate(_n_modulos=Count('modulos'))
            .filter(_n_modulos__gt=0)
            .order_by('orden', 'nombre')
        )

    if not cursos_activos.exists():
        return "No hay cursos disponibles en este momento. ⚠️"

    respuesta = "📚 *CURSOS DISPONIBLES EN eki*\n\n"

    for idx, curso in enumerate(cursos_activos, 1):
        respuesta += f"{idx}. {curso.emoji} *{curso.nombre}*\n"
        respuesta += f"   📅 {curso.duracion_semanas} semanas | 📖 {curso.modulos.count()} módulos\n\n"

    respuesta += "Para inscribirte en un curso:\n"
    respuesta += "👉 Escribe el *número* (ej: *1* o *2*)\n\n"
    respuesta += "También puedes escribir *MENÚ* para volver"

    estudiante_id = kwargs.get('estudiante_id')
    if estudiante_id:
        try:
            est = Estudiante.objects.get(id=estudiante_id)
            est.estado_onboarding = 'esperando_seleccion_curso'
            est.save()
        except Estudiante.DoesNotExist:
            pass

    return respuesta
