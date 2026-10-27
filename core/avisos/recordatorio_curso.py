"""Recordatorio para quien tiene contenido disponible y no avanza.

El primero sale tras `dias_sin_avanzar` días sin escribir; después uno cada `repetir_cada_dias`
hasta que termine o vuelva a escribir. Quien espera el calendario no recibe recordatorio.
No envía si el flag está apagado.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.avisos.modulo_disponible import _pausa, motivo_plantilla as _motivo_aviso

logger = logging.getLogger(__name__)

MAX_VARIABLES = 2


def recordatorio_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_RECORDATORIO_CURSO_ENABLED', False))


def motivo_plantilla(plantilla, phone_id: str) -> str:
    return _motivo_aviso(
        plantilla, phone_id, max_variables=MAX_VARIABLES, texto_variables='{{1}} nombre, {{2}} curso',
    )


def variables_recordatorio(plantilla, nombre: str, curso_nombre: str) -> dict:
    from core.models_campana_meta import variables_en

    valores = {'1': (nombre or '').strip() or 'Estudiante', '2': (curso_nombre or '').strip()}
    numeros = sorted(set(variables_en(plantilla.cuerpo)))
    return {str(n): valores[str(n)] for n in numeros if str(n) in valores}


def disponible_desde(progreso, ahora: datetime):
    """(True, desde) si tiene contenido para avanzar; (False, None) si espera el calendario o no hay más."""
    from core.drip_schedule import estudiante_autorizado_en_modulo, habilitado_desde_efectivo
    from core.modulo_publicacion import siguiente_modulo_publicado_wa

    estudiante = progreso.estudiante
    actual = progreso.modulo_actual
    if actual is None:
        return False, None
    modulo = actual
    if progreso.modulos_completados.filter(modulo_id=actual.pk).exists():
        modulo = siguiente_modulo_publicado_wa(progreso.curso, actual)
        if modulo is None:
            return False, None
    desde = habilitado_desde_efectivo(estudiante, modulo)
    if desde is not None and desde > ahora:
        return False, None
    if not estudiante_autorizado_en_modulo(estudiante, modulo):
        return False, None
    return True, desde


def ultima_senal(progreso):
    """Lo más reciente entre su último mensaje y el último aviso de módulo de este curso. None si nunca escribió."""
    from core.models import AvisoModuloEnviado
    from core.reenganche_meta import ultimo_entrante, ultimo_evento_meta

    estudiante = progreso.estudiante
    log = ultimo_entrante(estudiante)
    entrantes = [f for f in (getattr(log, 'fecha', None), ultimo_evento_meta(estudiante)) if f]
    if not entrantes:
        return None
    aviso = (
        AvisoModuloEnviado.objects.filter(estudiante=estudiante, modulo__curso_id=progreso.curso_id, estado='ENVIADO')
        .order_by('-fecha')
        .values_list('fecha', flat=True)
        .first()
    )
    return max([*entrantes, aviso] if aviso else entrantes)


def _toca(recordatorio, progreso, ahora: datetime) -> bool:
    from core.models import RecordatorioCursoEnviado

    hay, desde = disponible_desde(progreso, ahora)
    if not hay:
        return False
    senal = ultima_senal(progreso)
    if senal is None:
        return False
    referencia = max(senal, desde) if desde else senal
    if referencia > ahora - timedelta(days=recordatorio.dias_sin_avanzar):
        return False
    ultimo = (
        RecordatorioCursoEnviado.objects.filter(recordatorio=recordatorio, estudiante_id=progreso.estudiante_id)
        .order_by('-fecha')
        .values_list('fecha', flat=True)
        .first()
    )
    if ultimo and ultimo > referencia and ultimo > ahora - timedelta(days=recordatorio.repetir_cada_dias):
        return False
    return True


def candidatos(recordatorio, ahora: datetime) -> list:
    from core.models import ProgresoEstudiante

    qs = ProgresoEstudiante.objects.select_related('estudiante', 'curso', 'modulo_actual').filter(
        curso_id=recordatorio.curso_id,
        completado=False,
        estudiante__cliente_id=recordatorio.cliente_id,
        estudiante__activo=True,
        estudiante__acepto_terminos=True,
        estudiante__wa_optout_fecha__isnull=True,
    )
    if recordatorio.grupo_id:
        qs = qs.filter(estudiante__grupos__id=recordatorio.grupo_id)
    return [p for p in qs.distinct().order_by('id') if _toca(recordatorio, p, ahora)]


def _enviar_uno(recordatorio, sender, progreso, ahora: datetime) -> str:
    from core.models import RecordatorioCursoEnviado

    estudiante = progreso.estudiante
    try:
        with transaction.atomic():
            envio = RecordatorioCursoEnviado.objects.create(
                recordatorio=recordatorio, estudiante=estudiante, dia=timezone.localdate(ahora),
            )
    except IntegrityError:
        return 'repetido'
    variables = variables_recordatorio(recordatorio.plantilla, estudiante.nombre, recordatorio.curso.nombre)
    resultado = sender.plantilla(
        estudiante.telefono, recordatorio.plantilla.meta_name, variables, agente='recordatorio_curso',
    )
    ok = bool(resultado.get('success'))
    envio.estado = 'ENVIADO' if ok else 'FALLIDO'
    envio.wamid = str(resultado.get('mensaje_id') or '')[:200]
    envio.respuesta = str(resultado.get('response') or '')[:2000]
    envio.save(update_fields=['estado', 'wamid', 'respuesta'])
    if ok:
        from core.models import EstudianteEventoAprendizaje
        from core.telemetria import registrar_evento

        registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_ENVIADO,
            estudiante=estudiante,
            curso=recordatorio.curso,
            metadata={'origen': 'recordatorio_curso', 'template': True},
        )
    return 'enviado' if ok else 'fallido'


def ejecutar(ahora: datetime | None = None) -> dict:
    """Corre cada hora; cada recordatorio sale solo en su hora (Bogotá)."""
    ahora = ahora or timezone.now()
    resumen = {'habilitado': recordatorio_habilitado(), 'enviados': 0, 'fallidos': 0,
               'invalidos': 0, 'omitido_token': False}
    if not resumen['habilitado']:
        return resumen
    from core.meta_token import token_invalido

    if token_invalido():
        resumen['omitido_token'] = True
        return resumen
    from core.lineas.sender import sender_de_linea
    from core.models import RecordatorioCurso

    hora = timezone.localtime(ahora).hour
    pausa = _pausa()
    for recordatorio in RecordatorioCurso.objects.select_related('curso', 'plantilla').filter(activo=True, hora=hora):
        motivo = motivo_plantilla(recordatorio.plantilla, recordatorio.phone_number_id)
        if motivo:
            resumen['invalidos'] += 1
            logger.warning('recordatorio_curso id=%s no sale: %s', recordatorio.pk, motivo)
            continue
        sender = sender_de_linea(recordatorio.phone_number_id)
        for progreso in candidatos(recordatorio, ahora):
            estado = _enviar_uno(recordatorio, sender, progreso, ahora)
            if estado == 'enviado':
                resumen['enviados'] += 1
            elif estado == 'fallido':
                resumen['fallidos'] += 1
            if pausa:
                time.sleep(pausa)
    logger.info('recordatorio_curso resumen=%s', resumen)
    return resumen


def vista_previa(recordatorio, ahora: datetime | None = None) -> dict:
    """Cuántos lo recibirían si saliera ahora. No envía."""
    ahora = ahora or timezone.now()
    return {'personas': len(candidatos(recordatorio, ahora))}


def enviar_prueba(recordatorio, telefono: str) -> dict:
    """Envía el recordatorio a un número interno. No deja registro."""
    from core.lineas.sender import sender_de_linea

    variables = variables_recordatorio(recordatorio.plantilla, 'Prueba', recordatorio.curso.nombre)
    return sender_de_linea(recordatorio.phone_number_id).plantilla(
        telefono, recordatorio.plantilla.meta_name, variables, agente='recordatorio_curso_prueba',
    )
