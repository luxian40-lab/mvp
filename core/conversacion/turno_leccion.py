"""Contrato de turno en lección: tip y, opcional, una duda al Compañero.

Slice 1 (EKI_TURNO_LECCION_TIP): tip sin LLM, no «No entendí».
Slice 2 (EKI_TURNO_LECCION_COMPANERO): una respuesta del Compañero a una
pregunta clara. No abre el estado de checkpoint ni el reto del Formador.
No avanza el curso. Flags apagados = copy actual.
"""
from __future__ import annotations

import logging

from django.conf import settings

from core.conversacion.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS

logger = logging.getLogger(__name__)

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

CIERRE_COMPANERO_USTED = (
    '\n\nCuando quiera seguir con la lección, pulse *Continuar*.\n\n'
    + MARCADOR_BOTON_CONTINUEMOS
)
CIERRE_COMPANERO_TU = (
    '\n\nCuando quieras seguir con la lección, toca *Continuar*.\n\n'
    + MARCADOR_BOTON_CONTINUEMOS
)


def turno_leccion_tip_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_TURNO_LECCION_TIP', False))


def turno_leccion_companero_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_TURNO_LECCION_COMPANERO', False))


def clasificar_mensaje_leccion(mensaje: str) -> str:
    """Devuelve ``media``, ``pregunta`` o ``leccion``. Nunca avanza el curso."""
    from core.conversacion.intent_detector import mensaje_parece_pregunta_companero
    from core.lineas.agricapital_experiencia import es_duda_media_agricapital

    texto = mensaje or ''
    if es_duda_media_agricapital(texto):
        return 'media'
    if mensaje_parece_pregunta_companero(texto):
        return 'pregunta'
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


def _modulos_para_duda(estudiante) -> list:
    """Módulo actual del curso activo; si no hay, nada (el Compañero usa fallback)."""
    from core.models import ProgresoEstudiante

    ctx = getattr(estudiante, 'contexto_temporal', None) or {}
    curso_id = ctx.get('curso_activo_id')
    qs = ProgresoEstudiante.objects.filter(estudiante_id=estudiante.pk, completado=False)
    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    progreso = qs.select_related('modulo_actual', 'curso').order_by('-id').first()
    if progreso is None:
        return []
    modulo = getattr(progreso, 'modulo_actual', None)
    return [modulo] if modulo is not None else []


def responder_duda_en_leccion(estudiante, mensaje: str) -> str | None:
    """Una respuesta del Compañero. None si no aplica. No cambia estado ni avance."""
    if not turno_leccion_companero_habilitado():
        return None
    if clasificar_mensaje_leccion(mensaje) != 'pregunta':
        return None
    try:
        from core.agentes.agentes_whatsapp import mensaje_con_titular_agente
        from core.lineas.agricapital_experiencia import estudiante_es_agricapital
        from core.agentes.tutor_ia_modulo import generar_respuesta_asistente

        modulos = _modulos_para_duda(estudiante)
        cuerpo = generar_respuesta_asistente(
            modulos,
            mensaje or '',
            estudiante_nombre=getattr(estudiante, 'nombre', None) or 'Estudiante',
            nombre_asistente='Compañero',
        )
        agri = estudiante_es_agricapital(estudiante)
        cierre = CIERRE_COMPANERO_TU if agri else CIERRE_COMPANERO_USTED
        return mensaje_con_titular_agente('Compañero', (cuerpo or '').strip()) + cierre
    except Exception:
        logger.exception('turno_leccion_companero_fail')
        return None
