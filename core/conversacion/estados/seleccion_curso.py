"""Estado esperando_seleccion_curso. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
from core.conversacion.contexto import Contexto, Respuesta


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    msg_sel = msg_body.strip().lower()
    if msg_sel in ['menu', 'menú']:
        estudiante.estado_onboarding = 'completado'
        estudiante.contexto_temporal = None
        estudiante.save()
        from core.response_templates import get_response_for_intent
        texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
    else:
        import re as re_curso_sel
        indice_sel = None
        match_tomar_sel = re_curso_sel.match(r'^tomar\s*(\d+)$', msg_sel)
        if match_tomar_sel:
            indice_sel = int(match_tomar_sel.group(1))
        elif msg_body.strip().isdigit():
            indice_sel = int(msg_body.strip())
        if indice_sel is not None:
            from core.selector_curso import continuar_curso_seleccionado
            estudiante.estado_onboarding = 'completado'
            estudiante.save(update_fields=['estado_onboarding'])
            texto_respuesta = continuar_curso_seleccionado(estudiante.id, indice_sel, msg_body)
            print(f"✅ Curso seleccionado: {indice_sel}")
        else:
            # Si no es número/tomar ni menú, resetear estado y procesar normalmente
            estudiante.estado_onboarding = 'completado'
            estudiante.contexto_temporal = None
            estudiante.save()
            from core.eventos_ia import detectar_intent_con_evento
            from core.response_templates import get_response_for_intent
            _p0 = estudiante.progresos.order_by('-fecha_inicio').first()
            intent = detectar_intent_con_evento(
                msg_body,
                estudiante=estudiante,
                curso=_p0.curso if _p0 else None,
                modulo=_p0.modulo_actual if _p0 else None,
            )
            if intent != 'desconocido':
                texto_respuesta = get_response_for_intent(intent, estudiante.nombre, estudiante_id=estudiante.id, mensaje_original=msg_body)
            else:
                texto_respuesta = "No entendí tu selección. Escribe *menú* para ver las opciones."
    return Respuesta(texto=texto_respuesta)
