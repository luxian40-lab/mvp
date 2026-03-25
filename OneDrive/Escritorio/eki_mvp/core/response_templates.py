"""
Plantillas de respuesta para cada intent.
Permite personalizar respuestas sin cambiar la lógica del webhook.
"""


def get_response_for_intent(intent: str, nombre_usuario: str = "Estudiante", **kwargs) -> str:
    """
    Retorna una respuesta templada según el intent.
    
    Args:
        intent: categoría detectada (saludo, progreso, tareas, ayuda, etc.)
        nombre_usuario: nombre del estudiante (para personalizar)
        **kwargs: datos adicionales (progreso, siguiente_tarea, etc.)
    
    Returns:
        mensaje: respuesta en formato texto
    """
    
    # Saludos
    if intent == 'saludo':
        return f"""¡Hola {nombre_usuario}! 👋

Bienvenido a Eki. ¿Qué necesitas?

1️⃣  Ver mi progreso
2️⃣  Ver mis tareas
3️⃣  Ayuda

*Responde con 1, 2 o 3*"""
    
    # Opción 1: Progreso
    if intent == 'opcion_1':
        progreso = kwargs.get('progreso', '50%')
        modulo_actual = kwargs.get('modulo_actual', 'Módulo actual')
        return f"""📊 *Tu Progreso*

Módulo: {modulo_actual}
Avance: {progreso}

Vas muy bien. ¡Sigue adelante! 💪

*Responde "continuar" para avanzar al siguiente módulo.*"""
    
    # Opción 2: Tareas
    if intent == 'opcion_2':
        siguiente_tarea = kwargs.get('siguiente_tarea', 'Resolver ecuaciones lineales')
        fecha_vence = kwargs.get('fecha_vence', 'hoy')
        return f"""📝 *Tu Siguiente Tarea*

{siguiente_tarea}
Vence: {fecha_vence}

*Abre la app Eki para ver detalles y resolver.*

¿Necesitas ayuda? Escribe "ayuda"."""
    
    # Opción 3: Ayuda
    if intent == 'opcion_3':
        return """🆘 *Ayuda*

Puedo ayudarte con:
- 📊 Ver tu progreso
- 📝 Mostrar tus tareas
- 💬 Responder dudas sobre temas
- 🎯 Recomendaciones de estudio

¿Sobre qué necesitas ayuda?"""
    
    # Progreso (sin pasar por menú)
    if intent == 'progreso':
        return get_response_for_intent('opcion_1', nombre_usuario, **kwargs)
    
    # Tareas (sin pasar por menú)
    if intent == 'tareas':
        return get_response_for_intent('opcion_2', nombre_usuario, **kwargs)
    
    # Ayuda (sin pasar por menú)
    if intent == 'ayuda':
        return get_response_for_intent('opcion_3', nombre_usuario, **kwargs)

    # ---- Drip Content: Continuar Lección ----

    if intent == 'continuar_leccion_bloqueado':
        fecha_desbloqueo = kwargs.get('fecha_desbloqueo', 'próximamente')
        return (
            f"¡Excelente energía, {nombre_usuario}! 💪 Pero tu próxima lección se desbloquea el "
            f"*{fecha_desbloqueo}*. ¡Repasa lo aprendido mientras tanto! 📖"
        )

    if intent == 'continuar_leccion_libre':
        modulo_siguiente = kwargs.get('modulo_siguiente', 'el siguiente módulo')
        return (
            f"¡Perfecto, {nombre_usuario}! 🚀 Aquí va tu nueva lección: *{modulo_siguiente}*.\n\n"
            f"¡Mucho éxito!"
        )

    if intent == 'continuar_leccion_completado':
        curso = kwargs.get('curso', 'tu curso')
        return (
            f"🎓 ¡Felicitaciones, {nombre_usuario}! Has completado *{curso}*.\n\n"
            f"🏆 Has desbloqueado el *Radar de Empleos en Subachoque*. "
            f"Ve al parque principal y envíame tu 'Ubicación' usando el clip de WhatsApp (📎) "
            f"para encontrar empresas aliadas cerca de ti."
        )

    # ---- Gamificación Geolocalizada ----

    if intent == 'ubicacion_lejos':
        sector = kwargs.get('sector', 'el área central')
        return (
            f"📍 Aún estás lejos de nuestras empresas aliadas, {nombre_usuario}. "
            f"Sigue caminando por *{sector}* y vuelve a enviarme tu ubicación. 🚶"
        )

    if intent == 'ubicacion_cerca':
        metros = kwargs.get('metros', '?')
        empresa = kwargs.get('empresa', 'una empresa aliada')
        return (
            f"🎯 ¡Estás a *{metros} metros* de *{empresa}*! "
            f"Acércate a la entrada y envía el *código secreto* que verás en la puerta. 🔑"
        )

    if intent == 'codigo_correcto':
        empresa = kwargs.get('empresa', 'la empresa')
        return (
            f"🏆 ¡Felicitaciones, {nombre_usuario}! Has desbloqueado el logro *Conexión Laboral* "
            f"con *{empresa}*. Un representante se pondrá en contacto contigo muy pronto. 🌟"
        )

    if intent == 'codigo_incorrecto':
        return (
            f"🔒 Código incorrecto, {nombre_usuario}. Verifica el código en la puerta de la empresa "
            f"e inténtalo de nuevo."
        )

    # ---- Pregunta Abierta ----

    if intent == 'pregunta_abierta':
        pregunta = kwargs.get('pregunta', '')
        return (
            f"✍️ *Pregunta de reflexión:*\n\n{pregunta}\n\n"
            f"Responde con tus propias palabras. Tu facilitadora revisará tu respuesta."
        )

    if intent == 'respuesta_registrada':
        return (
            f"✅ ¡Gracias, {nombre_usuario}! Tu respuesta fue registrada. "
            f"Tu facilitadora la revisará pronto."
        )

    # Desconocido
    if intent == 'desconocido':
        return f"""Hola {nombre_usuario}, no entendí bien tu mensaje. 🤔

¿Qué necesitas?

1️⃣  Ver mi progreso
2️⃣  Ver mis tareas
3️⃣  Ayuda

*Responde con 1, 2 o 3*"""
    
    return f"Hola {nombre_usuario}, ¿cómo te puedo ayudar?"
