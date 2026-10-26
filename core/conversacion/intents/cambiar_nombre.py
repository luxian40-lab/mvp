"""Intent `cambiar_nombre` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    return """Para cambiar tu nombre, escribe:

Mi nombre es [Tu Nombre]

Ejemplo:
- Mi nombre es Juan Pérez
- Mi nombre es María González"""
