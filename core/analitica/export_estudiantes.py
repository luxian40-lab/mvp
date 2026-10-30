"""Utilidades para exportación de estudiantes a Excel."""


def limpiar_telefono(raw: str | None) -> str:
    """Devuelve solo los dígitos colombianos sin prefijo (+57 / whatsapp:)."""
    if not raw:
        return ''
    t = str(raw).replace('whatsapp:', '').strip()
    if t.startswith('+57'):
        t = t[3:]
    elif t.startswith('57') and len(t) > 10:
        t = t[2:]
    t = t.replace('+', '').replace(' ', '')
    return t
