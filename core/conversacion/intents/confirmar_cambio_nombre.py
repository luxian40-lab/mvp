"""Intent `confirmar_cambio_nombre` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    nuevo_nombre = kwargs.get('nuevo_nombre', 'Usuario')
    return f"""✅ Listo, ahora te llamaré {nuevo_nombre}.

¿Quieres continuar?
Escribe "continuar", "ver cursos" o "mi progreso"."""
