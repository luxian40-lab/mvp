"""Estado esperando_respuesta_recuperacion. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
from core.conversacion.contexto import Contexto, Respuesta


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    ctx = estudiante.contexto_temporal or {}
    pregunta_data = ctx.get('pregunta_data', {})
    correcta = pregunta_data.get('correcta', 'A')
    explicacion = pregunta_data.get('explicacion', '')

    from core.tutor_ia_modulo import evaluar_respuesta_recuperacion
    es_correcta, msg_evaluacion = evaluar_respuesta_recuperacion(msg_body, correcta, explicacion)

    # Si acertó, dar puntos bonus
    if es_correcta:
        try:
            from core.gamificacion import PerfilGamificacion
            perfil_rec = PerfilGamificacion.objects.get(estudiante=estudiante)
            perfil_rec.agregar_puntos(15, "🏆 Pregunta de recuperación correcta")
        except Exception:
            pass

    # Limpiar estado y continuar al certificado
    curso_id = ctx.get('curso_id')
    estudiante.estado_onboarding = 'completado'
    estudiante.contexto_temporal = None
    estudiante.save()

    # Generar certificado y resumen
    from core.response_templates import _generar_completado_final
    msg_final = _generar_completado_final(estudiante, curso_id)

    texto_respuesta = f"[MULTI_MSG]{msg_evaluacion}[SEP]{msg_final}"
    return Respuesta(texto=texto_respuesta)
