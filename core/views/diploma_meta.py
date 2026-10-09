"""Diploma por Meta. El aula de Twilio no se entera: solo se desvía este envío."""
from __future__ import annotations

_MARCAS_DIPLOMA = (
    '¡tu certificado',
    '¡su certificado',
    'certificado digital está listo',
    '— certificado *',
)


def es_entrega_diploma(texto: str, media_url: str | None = None) -> bool:
    """True solo si el mensaje es la imagen del diploma, no un video de clase."""
    if not str(media_url or '').strip():
        return False
    t = (texto or '').lower()
    return any(marca in t for marca in _MARCAS_DIPLOMA)


def entregar_si_es_diploma(
    telefono: str,
    texto: str,
    media_url: str | None = None,
    *,
    agente_evento: str = '',
) -> dict | None:
    """None si no es diploma. Si lo es, sale por Graph y no sigue a Twilio."""
    if not es_entrega_diploma(texto, media_url):
        return None
    from core.sandbox_canal import enviar_meta

    return enviar_meta(
        telefono,
        texto,
        media_url=media_url,
        canal_evento='certificado',
        agente_evento=agente_evento or 'diploma_meta',
    )
