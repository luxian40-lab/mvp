"""Estado curso_finalizado. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import Contexto, Respuesta


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    texto_respuesta = contexto.texto_respuesta
    print(f"🚫 Curso finalizado — sin interacción post-certificado")
    # Check if student has a new active course
    from core.models import ProgresoEstudiante
    nuevo_progreso = ProgresoEstudiante.objects.filter(
        estudiante=estudiante, completado=False
    ).first()
    if nuevo_progreso:
        # New course assigned — reset state
        estudiante.estado_onboarding = 'completado'
        estudiante.save()
        texto_respuesta = (
            f"🎉 *¡Tienes un nuevo curso asignado!*\n\n"
            f"📚 *{nuevo_progreso.curso.nombre}*\n\n"
            "Pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
        )
    else:
        texto_respuesta = (
            "✅ *Tu proceso del curso ya finalizó y tu certificado fue enviado.*\n\n"
            "Cuando tu organización te inscriba en un nuevo curso, te notificaremos. "
            "¡Gracias por tu participación! 🎓"
        )
    return Respuesta(texto=texto_respuesta)
