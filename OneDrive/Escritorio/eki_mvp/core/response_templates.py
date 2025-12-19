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
        modulo_actual = kwargs.get('modulo_actual', 'Matemáticas Básicas')
        return f"""📊 **Tu Progreso**

Módulo: {modulo_actual}
Avance: {progreso}

Vas muy bien. Sigue adelante! 💪

*Responde "tareas" para ver qué hacer a continuación.*"""
    
    # Opción 2: Tareas
    if intent == 'opcion_2':
        siguiente_tarea = kwargs.get('siguiente_tarea', 'Resolver ecuaciones lineales')
        fecha_vence = kwargs.get('fecha_vence', 'hoy')
        return f"""📝 **Tu Siguiente Tarea**

{siguiente_tarea}
Vence: {fecha_vence}

*Abre la app Eki para ver detalles y resolver.*

¿Necesitas ayuda? Escribe "ayuda"."""
    
    # Opción 3: Ayuda
    if intent == 'opcion_3':
        return """🆘 **Ayuda**

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
    
    # Desconocido
    if intent == 'desconocido':
        return f"""Hola {nombre_usuario}, no entendí bien tu mensaje. 🤔

¿Qué necesitas?

1️⃣  Ver mi progreso
2️⃣  Ver mis tareas
3️⃣  Ayuda

*Responde con 1, 2 o 3*"""
    
    return f"Hola {nombre_usuario}, ¿cómo te puedo ayudar?"
