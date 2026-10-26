"""Intent `ayuda` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    estudiante_id = kwargs.get('estudiante_id')
    if estudiante_id:
        try:
            from core.models import Estudiante, SolicitudSoporte
            est = Estudiante.objects.get(id=estudiante_id)
            ctx = est.contexto_temporal or {}
            conteo_ayuda = ctx.get('conteo_ayuda', 0) + 1
            
            if conteo_ayuda >= 2:
                # Segunda vez pidiendo ayuda → crear ticket de soporte
                solicitud = SolicitudSoporte.objects.create(
                    estudiante=est,
                    mensaje_original=kwargs.get('mensaje_original', 'ayuda x2'),
                    keyword_usada='ayuda (doble)',
                    prioridad='media'
                )
                # Limpiar conteo
                ctx.pop('conteo_ayuda', None)
                est.contexto_temporal = ctx if ctx else None
                est.save()
                
                return f"""🆘 *Ticket de Soporte Creado*

Hola {nombre_usuario}, vemos que necesitas más ayuda.

📝 *Ticket #{solicitud.id}* registrado correctamente.
📧 Nuestro equipo ha sido notificado.

🕐 *Tiempo de respuesta:* menos de 24 horas.

Mientras tanto puedes seguir usando la plataforma normalmente.

Escribe *"menú"* para volver al inicio."""
            else:
                # Primera vez → guardar conteo y mostrar ayuda normal
                ctx['conteo_ayuda'] = conteo_ayuda
                est.contexto_temporal = ctx
                est.save()
        except Exception:
            pass
    
    return """☕ AYUDA - CURSOS DE CAFÉ eki

📋 COMANDOS PRINCIPALES:

• "ver cursos" - Ver cursos disponibles
• "2" - Inscribirte en un curso
• "continuar" - Seguir tu curso actual
• "progreso" o "1" - Ver tu avance
• "menú" - Volver al inicio

🎮 GAMIFICACIÓN:
⭐ Ganas puntos al completar módulos
🏆 Desbloqueas badges por logros
📈 Subes de nivel

💬 PREGUNTAS:
También puedes preguntarme sobre café:
• "¿Cómo hacer análisis de suelos?"
• "¿Qué sistema de riego usar?"
• "¿Cómo controlar la roya?"

🆘 _Si necesitas hablar con soporte, escribe *"ayuda"* otra vez._
✍️ Escribe "menú" para volver al inicio."""
