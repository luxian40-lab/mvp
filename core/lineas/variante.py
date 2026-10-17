"""Dos variantes de línea. No es otro servicio: el menú pregunta aquí.

La principal es la versión Meta: carrusel, varios cursos y agentes.
La segunda es el modo Twilio: curso lineal, solo Formador y Compañero,
sin carrusel y sin lista de agentes. El aula sigue en Twilio HTTP.
"""
from core.lineas.meta import USO_SOLO_CURSOS, lineas_producto

# Alias de producto: mismo flag técnico, nombre claro.
USO_MODO_TWILIO = USO_SOLO_CURSOS

TEXTO_LINEA_MODO_TWILIO = (
    "Esta línea es solo del curso.\n\n"
    "Si ya está inscrito, escriba *continuar* para seguir. "
    "El Formador y el Compañero lo acompañan dentro del módulo.\n\n"
    "Aquí no hay menú de varios cursos ni asesores aparte."
)

# Compatibilidad con imports anteriores.
TEXTO_LINEA_SOLO_CURSOS = TEXTO_LINEA_MODO_TWILIO


def es_solo_cursos(phone_id: str | None = None) -> bool:
    """True = línea 2 / modo Twilio (curso lineal)."""
    if phone_id is None:
        from core.sandbox_canal import phone_id_de_salida

        phone_id = phone_id_de_salida()
    buscado = str(phone_id or '').strip()
    if not buscado:
        return False
    for linea in lineas_producto():
        if linea.phone_id == buscado:
            return linea.uso == USO_SOLO_CURSOS
    return False


def es_modo_twilio(phone_id: str | None = None) -> bool:
    """Misma regla que es_solo_cursos; nombre de producto."""
    return es_solo_cursos(phone_id)
