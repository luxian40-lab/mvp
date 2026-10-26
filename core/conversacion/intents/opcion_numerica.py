"""Intent `opcion_numerica` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    # Curso de lista (mismo orden que opcion_2 / selector_curso por cliente)
    from core.selector_curso import continuar_curso_seleccionado

    sid = kwargs.get('estudiante_id')
    msg = (kwargs.get('mensaje_original') or '').strip()
    if not sid or not msg.isdigit():
        return "Escribe el número del curso o *menú* para volver."
    return continuar_curso_seleccionado(sid, int(msg), msg)
