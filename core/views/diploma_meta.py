"""Diploma por Meta.

El aula es Aprende: el mismo curso. Twilio sigue entregando módulos y audio.
Este módulo solo desvía la imagen del diploma, y la plantilla cuando hay nombre.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

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


def nombre_plantilla_diploma() -> str:
    """Entorno gana. Si está vacío, el nombre que se edita en Configuración Global."""
    env = (getattr(settings, 'META_TEMPLATE_DIPLOMA', '') or '').strip()
    if env:
        return env
    try:
        from core.models import ConfiguracionGlobal
        return (ConfiguracionGlobal.get_solo().meta_plantilla_diploma or '').strip()
    except Exception:
        logger.exception('diploma_meta_nombre_plantilla')
        return ''


def enviar_diploma_plantilla_meta(
    telefono,
    media_url,
    *,
    nombre_estudiante: str = '',
    curso: str = '',
    codigo: str = '',
) -> dict | None:
    """None si no hay plantilla configurada. El caller sigue con la imagen de sesión."""
    nombre = nombre_plantilla_diploma()
    if not nombre or not str(media_url or '').strip():
        return None
    from core.sandbox_canal import enviar_meta_plantilla_imagen
    idioma = (getattr(settings, 'META_TEMPLATE_DIPLOMA_IDIOMA', 'es') or 'es').strip() or 'es'
    return enviar_meta_plantilla_imagen(
        telefono,
        nombre,
        media_url,
        {
            '1': (nombre_estudiante or 'estudiante')[:1024],
            '2': (curso or 'curso')[:1024],
            '3': (codigo or '')[:1024],
        },
        idioma=idioma,
        agente_evento='diploma_meta',
    )
