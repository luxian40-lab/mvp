"""Estado curso_finalizado. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import Contexto, Respuesta

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    texto_respuesta = contexto.texto_respuesta
    logger.info(f"🚫 Curso finalizado — sin interacción post-certificado")
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
        if _diploma_entregado_de_verdad(estudiante):
            texto_respuesta = (
                "✅ *Tu progreso del curso ya finalizó y tu certificado fue enviado.*\n\n"
                "Cuando tu organización te inscriba en un nuevo curso, te notificaremos. "
                "¡Gracias por tu participación! 🎓"
            )
        else:
            texto_respuesta = (
                "✅ *Tu progreso del curso ya finalizó.*\n\n"
                "Su certificado está listo; si no lo ve en este chat, escriba *certificado* "
                "o espere el reenvío de su organización.\n\n"
                "Cuando le inscriban en un nuevo curso, le avisamos. ¡Gracias! 🎓"
            )
    return Respuesta(texto=texto_respuesta)


def _diploma_entregado_de_verdad(estudiante) -> bool:
    """True solo si hay envío diploma Meta no fallido (no basta el flag del admin)."""
    from core.models import Certificado, WhatsappLog

    if not Certificado.objects.filter(
        estudiante=estudiante, emitido=True, enviado_whatsapp=True,
    ).exists():
        return False
    tel = getattr(estudiante, 'telefono', '') or ''
    digits = ''.join(c for c in tel if c.isdigit())
    if len(digits) < 10:
        return False
    ultimo = (
        WhatsappLog.objects.filter(
            telefono__endswith=digits[-10:],
            tipo='SENT',
            agente_usado__icontains='diploma',
        )
        .order_by('-fecha')
        .first()
    )
    if ultimo is None:
        return False
    estado = (ultimo.estado or '').strip().lower()
    return estado not in ('failed', 'error', 'undelivered')
