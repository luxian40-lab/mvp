"""Intent `ver_cursos` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.models import Curso, Estudiante
    from core.selector_curso import cursos_visibles_para_estudiante, asegurar_inscripcion_catalogo_cliente

    estudiante_id_vc = kwargs.get('estudiante_id')
    cursos_activos = None
    if estudiante_id_vc:
        try:
            _est_vc = Estudiante.objects.select_related('cliente').get(id=estudiante_id_vc)
            cursos_activos = cursos_visibles_para_estudiante(_est_vc)
            if _est_vc.cliente_id and cursos_activos.count() == 1:
                prog = asegurar_inscripcion_catalogo_cliente(_est_vc)
                if prog and prog.curso:
                    return (
                        f"📚 Tu curso: *{prog.curso.nombre}*\n\n"
                        "Escribe *continuar* para seguir."
                    )
        except Estudiante.DoesNotExist:
            pass
    if cursos_activos is None:
        from django.db.models import Count
        cursos_activos = (
            Curso.objects.filter(activo=True)
            .annotate(_n_modulos=Count('modulos'))
            .filter(_n_modulos__gt=0)
            .order_by('orden', 'nombre')
        )

    if not cursos_activos.exists():
        return "No hay cursos disponibles en este momento. ⚠️"

    respuesta = "📚 CURSOS DISPONIBLES EN eki\n\n"

    for idx, curso in enumerate(cursos_activos, 1):
        respuesta += f"{idx}️⃣ {curso.emoji} *{curso.nombre}*\n"
        respuesta += f"   📅 {curso.duracion_semanas} semanas | 📖 {curso.modulos.count()} módulos\n\n"

    respuesta += "👉 *Escribe el número* del curso que quieres tomar"
    return respuesta
