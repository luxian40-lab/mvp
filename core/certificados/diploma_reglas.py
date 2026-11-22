"""Emisión de diploma detrás de reglas (corte 3 del expediente).

Con ``EKI_DIPLOMA_LEE_REGLAS`` apagado: mismo criterio que el ``post_save``
histórico (``completado`` + ``fecha_completado``).

Con el interruptor prendido: además exige módulos publicados recorridos y,
si el curso tiene pregunta abierta final activa, que ya esté respondida.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def diploma_lee_reglas_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_DIPLOMA_LEE_REGLAS', False))


def cumple_reglas_diploma(progreso) -> tuple[bool, str | None]:
    """¿Puede emitirse el diploma para este progreso?

    Returns:
        (ok, motivo_si_no)
    """
    if progreso is None:
        return False, 'sin_progreso'
    if not getattr(progreso, 'completado', False):
        return False, 'no_completado'
    if not getattr(progreso, 'fecha_completado', None):
        return False, 'sin_fecha_completado'

    if not diploma_lee_reglas_habilitado():
        return True, None

    estudiante = getattr(progreso, 'estudiante', None)
    curso = getattr(progreso, 'curso', None)
    if estudiante is None or curso is None:
        return False, 'sin_estudiante_o_curso'

    if getattr(estudiante, 'estado_onboarding', None) == 'esperando_respuesta_pregunta_abierta_final':
        return False, 'pregunta_abierta_pendiente'

    from core.models import ModuloCompletado, PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal
    from core.modulo_publicacion import modulos_publicados_wa_qs

    publicados = list(modulos_publicados_wa_qs(curso).order_by('numero', 'id'))
    if publicados:
        hechos = set(
            ModuloCompletado.objects.filter(
                progreso=progreso,
                modulo_id__in=[m.id for m in publicados],
            ).values_list('modulo_id', flat=True)
        )
        faltantes = [m for m in publicados if m.id not in hechos]
        if faltantes:
            return False, 'modulos_publicados_incompletos'

    preguntas = list(
        PreguntaAbiertaFinalCurso.objects.filter(curso=curso, activa=True).order_by('orden', 'id')
    )
    for pregunta in preguntas:
        if not RespuestaAbiertaFinal.objects.filter(
            pregunta=pregunta,
            estudiante=estudiante,
        ).exists():
            return False, 'evaluacion_abierta_sin_responder'

    return True, None


def emitir_diploma_si_cumple(progreso):
    """Emisión a propósito. No-op si ya hay certificado o las reglas no pasan.

    Returns:
        Certificado | None
    """
    ok, motivo = cumple_reglas_diploma(progreso)
    if not ok:
        logger.info(
            'diploma_omitido progreso_id=%s motivo=%s',
            getattr(progreso, 'id', None),
            motivo,
        )
        return None

    from core.certificados.certificado_service import crear_certificado_automatico, generar_y_guardar_certificado
    from core.models_certificados import Certificado

    estudiante = progreso.estudiante
    curso = progreso.curso

    existente = Certificado.objects.filter(estudiante=estudiante, curso=curso).first()
    if existente:
        logger.info(
            'Certificado ya existe para %s - %s (%s)',
            estudiante.nombre,
            curso.nombre,
            existente.codigo_verificacion,
        )
        return existente

    logger.info('Generando certificado para %s - %s', estudiante.nombre, curso.nombre)
    certificado = crear_certificado_automatico(estudiante, curso)
    if not certificado:
        logger.error('Error al crear certificado para %s', estudiante.nombre)
        return None

    if not getattr(settings, 'EKI_CERTIFICADO_ASYNC', False):
        if not certificado.archivo_imagen and not certificado.archivo_pdf:
            generar_y_guardar_certificado(certificado)

    logger.info(
        'Certificado generado: %s (envío via views.py)',
        certificado.codigo_verificacion,
    )
    return certificado
