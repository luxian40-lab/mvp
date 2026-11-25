"""Recordatorio para quien tiene contenido disponible y no avanza.

El primero sale tras `dias_sin_avanzar` días sin escribir; después uno cada `repetir_cada_dias`
hasta que termine o vuelva a escribir. Quien espera el calendario no recibe recordatorio.
No envía si el flag está apagado.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.avisos.modulo_disponible import _pausa, motivo_plantilla as _motivo_aviso

logger = logging.getLogger(__name__)

MAX_VARIABLES = 3
TEXTO_VARIABLES = '{{1}} nombre, {{2}} curso, {{3}} módulo (opcional)'


def recordatorio_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_RECORDATORIO_CURSO_ENABLED', False))


def motivo_plantilla(plantilla, phone_id: str) -> str:
    """Texto o imagen (con media_url). Hasta 3 variables de cuerpo."""
    if plantilla is not None and plantilla.tipo == 'IMAGEN':
        if not (plantilla.media_url or '').strip():
            return 'La plantilla de imagen necesita URL de muestra.'
        from core.lineas.campana import plantilla_sirve_en_linea
        from core.campanas.models_campana_meta import variables_en

        if not plantilla.activa or plantilla.estado != 'APPROVED':
            return 'La plantilla no está aprobada en Meta.'
        if variables_en(plantilla.header_texto):
            return 'El header no puede llevar variables.'
        for url in (plantilla.boton_1_url, plantilla.boton_2_url):
            if '{{' in (url or ''):
                return 'Los botones no pueden llevar variables.'
        if len(set(variables_en(plantilla.cuerpo))) > MAX_VARIABLES:
            return f'El cuerpo admite hasta {MAX_VARIABLES} variables: {TEXTO_VARIABLES}.'
        return plantilla_sirve_en_linea(plantilla, phone_id)
    return _motivo_aviso(
        plantilla, phone_id, max_variables=MAX_VARIABLES, texto_variables=TEXTO_VARIABLES,
    )


def _enviar_plantilla(sender, plantilla, telefono: str, variables: dict, *, agente: str) -> dict:
    if plantilla.tipo == 'IMAGEN':
        media = (plantilla.media_url or '').strip()
        enviar = getattr(sender, 'plantilla_imagen', None)
        if not callable(enviar) or not media:
            return {'success': False, 'mensaje_id': None, 'response': 'sin_plantilla_imagen'}
        return enviar(telefono, plantilla.meta_name, media, variables, agente=agente)
    return sender.plantilla(telefono, plantilla.meta_name, variables, agente=agente)


def recordatorio_vigente(recordatorio, ahora: datetime | None = None) -> bool:
    """False si está apagado o ya pasó activo_hasta (Bogotá)."""
    if not recordatorio.activo:
        return False
    hasta = getattr(recordatorio, 'activo_hasta', None)
    if hasta is None:
        return True
    ahora = ahora or timezone.now()
    return timezone.localdate(ahora) <= hasta


def variables_recordatorio(
    plantilla, nombre: str, curso_nombre: str, modulo_titulo: str = '',
) -> dict:
    from core.campanas.models_campana_meta import variables_en

    valores = {
        '1': (nombre or '').strip() or 'Estudiante',
        '2': (curso_nombre or '').strip(),
        '3': (modulo_titulo or '').strip() or 'su módulo',
    }
    numeros = sorted(set(variables_en(plantilla.cuerpo)))
    return {str(n): valores[str(n)] for n in numeros if str(n) in valores}


def _modulo_titulo(progreso) -> str:
    modulo = getattr(progreso, 'modulo_actual', None)
    if modulo is None:
        return ''
    titulo = (getattr(modulo, 'titulo', None) or '').strip()
    numero = getattr(modulo, 'numero', None)
    if titulo and numero is not None:
        return f'Módulo {numero}: {titulo}'
    return titulo or (f'Módulo {numero}' if numero is not None else '')


def disponible_desde(progreso, ahora: datetime):
    """(True, desde) si tiene contenido para avanzar; (False, None) si espera el calendario o no hay más."""
    from core.curso.drip_schedule import estudiante_autorizado_en_modulo, habilitado_desde_efectivo
    from core.curso.modulo_publicacion import siguiente_modulo_publicado_wa

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
    from core.campanas.reenganche_meta import ultimo_entrante, ultimo_evento_meta

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
    enviados = RecordatorioCursoEnviado.objects.filter(
        recordatorio=recordatorio,
        estudiante_id=progreso.estudiante_id,
        estado='ENVIADO',
        fecha__gt=referencia,
    )
    if enviados.count() >= recordatorio.maximo_envios:
        return False
    ultimo = enviados.order_by('-fecha').values_list('fecha', flat=True).first()
    if ultimo and ultimo > ahora - timedelta(days=recordatorio.repetir_cada_dias):
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
    variables = variables_recordatorio(
        recordatorio.plantilla,
        estudiante.nombre,
        recordatorio.curso.nombre,
        _modulo_titulo(progreso),
    )
    resultado = _enviar_plantilla(
        sender, recordatorio.plantilla, estudiante.telefono, variables, agente='recordatorio_curso',
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
    from core.canal.meta_token import token_invalido

    if token_invalido():
        resumen['omitido_token'] = True
        return resumen
    from core.lineas.sender import sender_de_linea
    from core.models import RecordatorioCurso

    hora = timezone.localtime(ahora).hour
    pausa = _pausa()
    for recordatorio in RecordatorioCurso.objects.select_related('curso', 'plantilla').filter(activo=True, hora=hora):
        if not recordatorio_vigente(recordatorio, ahora):
            continue
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
                from core.lineas.entrega_delays import pausar_lote

                if pausar_lote(pausa, tarea='core.avisos.tareas.recordatorio_curso'):
                    logger.info('recordatorio_curso resumen=%s diferido', resumen)
                    return resumen
    logger.info('recordatorio_curso resumen=%s', resumen)
    return resumen


def vista_previa(recordatorio, ahora: datetime | None = None) -> dict:
    """Cuántos lo recibirían si saliera ahora. No envía."""
    ahora = ahora or timezone.now()
    if not recordatorio_vigente(recordatorio, ahora):
        return {'personas': 0}
    return {'personas': len(candidatos(recordatorio, ahora))}


def enviar_prueba(recordatorio, telefono: str) -> dict:
    """Envía el recordatorio a un número interno. No deja registro."""
    from core.lineas.sender import sender_de_linea

    variables = variables_recordatorio(recordatorio.plantilla, 'Prueba', recordatorio.curso.nombre)
    return _enviar_plantilla(
        sender_de_linea(recordatorio.phone_number_id),
        recordatorio.plantilla,
        telefono,
        variables,
        agente='recordatorio_curso_prueba',
    )
