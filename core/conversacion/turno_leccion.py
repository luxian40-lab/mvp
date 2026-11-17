"""Contrato de turno en lección (slice 1): tip sin LLM, no «No entendí».

Con EKI_TURNO_LECCION_TIP apagado no se usa. No abre Compañero ni avanza el curso.
"""
from __future__ import annotations

from django.conf import settings

from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS


TEXTO_TIP_LECCION_USTED = (
    'En esta parte del curso el avance es con *Continuar*.\n\n'
    'Si un video o una imagen no carga, escríbalo y le ayudamos. '
    'Si necesita soporte, escriba *ayuda*.\n\n'
    'Cuando quiera seguir, pulse Continuar.\n\n'
    + MARCADOR_BOTON_CONTINUEMOS
)

TEXTO_TIP_LECCION_TU = (
    'En esta parte del curso el avance es con *Continuar*.\n\n'
    'Si un video o una imagen no carga, escríbelo y te ayudamos. '
    'Si necesitas soporte, escribe *ayuda*.\n\n'
    'Cuando quieras seguir, toca Continuar.\n\n'
    + MARCADOR_BOTON_CONTINUEMOS
)

TEXTO_TIP_MEDIA_USTED = (
    'Si no descarga o no ve la imagen o el video, revise su señal y vuelva '
    'a tocar el archivo. Si sigue igual, escriba *ayuda* y le acompañamos.\n\n'
    'El curso no avanza con este mensaje: cuando quiera seguir, pulse *Continuar*.\n\n'
    + MARCADOR_BOTON_CONTINUEMOS
)


def turno_leccion_tip_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_TURNO_LECCION_TIP', False))


def clasificar_mensaje_leccion(mensaje: str) -> str:
    """Devuelve ``media`` o ``leccion`` (nunca avanza ni abre agente)."""
    from core.lineas.agricapital_experiencia import es_duda_media_agricapital

    if es_duda_media_agricapital(mensaje or ''):
        return 'media'
    return 'leccion'


def texto_tip_turno_leccion(estudiante, mensaje: str = '') -> str:
    """Copy de tip según clasificación; AgriCapital en tú."""
    from core.lineas.agricapital_experiencia import (
        estudiante_es_agricapital,
        texto_tip_media_agricapital,
    )

    clase = clasificar_mensaje_leccion(mensaje)
    agri = estudiante_es_agricapital(estudiante)
    if clase == 'media':
        if agri:
            tip = texto_tip_media_agricapital()
            if MARCADOR_BOTON_CONTINUEMOS not in tip:
                tip = tip.rstrip() + '\n\n' + MARCADOR_BOTON_CONTINUEMOS
            return tip
        return TEXTO_TIP_MEDIA_USTED
    if agri:
        return TEXTO_TIP_LECCION_TU
    return TEXTO_TIP_LECCION_USTED
