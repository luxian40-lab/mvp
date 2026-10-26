"""Intent `numero_invalido` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    return """❌ Número inválido.

Las opciones del menú son:

1️⃣ Ver mi progreso
2️⃣ Ver cursos de café
3️⃣ Ayuda y soporte

Escribe solo el número: 1, 2 o 3

O escribe "menú" para ver todas las opciones."""
