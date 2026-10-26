"""Intent `progreso` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.response_templates import get_response_for_intent
    return get_response_for_intent('opcion_1', nombre_usuario, kwargs)
