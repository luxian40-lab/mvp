"""Aviso de módulo disponible. Sale cuando el calendario del cliente abre el módulo.

Solo a quien terminó el módulo anterior y quedó esperando. Una vez por persona y módulo.
No envía si el flag está apagado.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_VARIABLES = 3


def aviso_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_AVISO_MODULO_DISPONIBLE_ENABLED', False))


def _ventana() -> timedelta:
    try:
        horas = float(getattr(settings, 'EKI_AVISO_MODULO_VENTANA_HORAS', 24))
    except (TypeError, ValueError):
        horas = 24
    return timedelta(hours=max(horas, 0))


def _pausa() -> float:
    try:
        return max(float(getattr(settings, 'EKI_AVISO_MODULO_PAUSA_SEG', 0.35)), 0.0)
    except (TypeError, ValueError):
        return 0.35


def motivo_plantilla(
    plantilla,
    phone_id: str,
    *,
    max_variables: int = MAX_VARIABLES,
    texto_variables: str = '{{1}} nombre, {{2}} módulo, {{3}} curso',
) -> str:
    """Vacío si la plantilla sirve para el aviso en esa línea. Si no, el motivo."""
    from core.lineas.campana import plantilla_sirve_en_linea
    from core.models_campana_meta import variables_en

    if plantilla is None:
        return 'Falta la plantilla.'
    if not plantilla.activa or plantilla.estado != 'APPROVED':
        return 'La plantilla no está aprobada en Meta.'
    if plantilla.tipo != 'TEXTO':
        return 'La plantilla debe ser de tipo Texto.'
    if variables_en(plantilla.header_texto):
        return 'El header no puede llevar variables.'
    for url in (plantilla.boton_1_url, plantilla.boton_2_url):
        if '{{' in (url or ''):
            return 'Los botones no pueden llevar variables.'
    if len(set(variables_en(plantilla.cuerpo))) > max_variables:
        return f'El cuerpo admite hasta {max_variables} variables: {texto_variables}.'
    return plantilla_sirve_en_linea(plantilla, phone_id)


def variables_aviso(plantilla, nombre: str, modulo_titulo: str, curso_nombre: str) -> dict:
    from core.models_campana_meta import variables_en

    valores = {
        '1': (nombre or '').strip() or 'Estudiante',
        '2': (modulo_titulo or '').strip(),
        '3': (curso_nombre or '').strip(),
    }
    numeros = sorted(set(variables_en(plantilla.cuerpo)))
    return {str(n): valores[str(n)] for n in numeros if str(n) in valores}


def _anterior(curso, modulo):
    from core.modulo_publicacion import modulos_publicados_wa

    publicados = modulos_publicados_wa(curso)
    ids = [m.pk for m in publicados]
    if modulo.pk not in ids:
        return None
    i = ids.index(modulo.pk)
    return publicados[i - 1] if i > 0 else None


def _esperando(aviso, modulo, ahora: datetime):
    """Progresos que terminaron el módulo anterior, aún sin aviso de este módulo."""
    from core.drip_schedule import estudiante_autorizado_en_modulo, habilitado_desde_efectivo
    from core.models import AvisoModuloEnviado, ProgresoEstudiante

    anterior = _anterior(aviso.curso, modulo)
    if anterior is None:
        return []
    qs = ProgresoEstudiante.objects.select_related('estudiante').filter(
        curso_id=aviso.curso_id,
        completado=False,
        modulo_actual_id=anterior.pk,
        modulos_completados__modulo_id=anterior.pk,
        estudiante__cliente_id=aviso.cliente_id,
        estudiante__activo=True,
        estudiante__wa_optout_fecha__isnull=True,
    ).exclude(
        estudiante_id__in=AvisoModuloEnviado.objects.filter(modulo_id=modulo.pk).values('estudiante_id'),
    )
    if aviso.grupo_id:
        qs = qs.filter(estudiante__grupos__id=aviso.grupo_id)
    salida = []
    for progreso in qs.distinct().order_by('id'):
        estudiante = progreso.estudiante
        desde = habilitado_desde_efectivo(estudiante, modulo)
        if desde is None or desde > ahora:
            continue
        if not estudiante_autorizado_en_modulo(estudiante, modulo):
            continue
        salida.append(progreso)
    return salida


def _habilitaciones(aviso):
    from core.models import HabilitacionModuloDripCliente

    return (
        HabilitacionModuloDripCliente.objects.select_related('modulo')
        .filter(cliente_id=aviso.cliente_id, curso_id=aviso.curso_id, activo=True, habilitado_desde__isnull=False)
        .order_by('habilitado_desde', 'modulo__numero')
    )


def vista_previa(aviso, ahora: datetime | None = None) -> list[dict]:
    """Módulos del calendario y cuántos esperan hoy cada uno. No envía."""
    ahora = ahora or timezone.now()
    desde = ahora - _ventana()
    filas = []
    for habilitacion in _habilitaciones(aviso):
        modulo = habilitacion.modulo
        if _anterior(aviso.curso, modulo) is None:
            continue
        filas.append({
            'modulo': modulo,
            'habilitado_desde': habilitacion.habilitado_desde,
            'en_ventana': desde < habilitacion.habilitado_desde <= ahora,
            'personas': len(_esperando(aviso, modulo, max(ahora, habilitacion.habilitado_desde))),
        })
    return filas


def _registrar_telemetria(estudiante, curso, modulo) -> None:
    from core.models import EstudianteEventoAprendizaje
    from core.telemetria import registrar_evento

    registrar_evento(
        tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_ENVIADO,
        estudiante=estudiante,
        curso=curso,
        modulo=modulo,
        metadata={'origen': 'aviso_modulo', 'template': True, 'modulo_desbloqueado_id': modulo.pk},
    )


def _enviar_uno(aviso, sender, progreso, modulo) -> str:
    from core.models import AvisoModuloEnviado

    estudiante = progreso.estudiante
    try:
        with transaction.atomic():
            envio = AvisoModuloEnviado.objects.create(aviso=aviso, estudiante=estudiante, modulo=modulo)
    except IntegrityError:
        return 'repetido'
    variables = variables_aviso(aviso.plantilla, estudiante.nombre, modulo.titulo, aviso.curso.nombre)
    resultado = sender.plantilla(estudiante.telefono, aviso.plantilla.meta_name, variables, agente='aviso_modulo')
    ok = bool(resultado.get('success'))
    envio.estado = 'ENVIADO' if ok else 'FALLIDO'
    envio.wamid = str(resultado.get('mensaje_id') or '')[:200]
    envio.respuesta = str(resultado.get('response') or '')[:2000]
    envio.save(update_fields=['estado', 'wamid', 'respuesta'])
    if ok:
        _registrar_telemetria(estudiante, aviso.curso, modulo)
    return 'enviado' if ok else 'fallido'


def ejecutar(ahora: datetime | None = None) -> dict:
    ahora = ahora or timezone.now()
    resumen = {'habilitado': aviso_habilitado(), 'enviados': 0, 'fallidos': 0,
               'avisos_invalidos': 0, 'omitido_token': False}
    if not resumen['habilitado']:
        return resumen
    from core.meta_token import token_invalido

    if token_invalido():
        resumen['omitido_token'] = True
        return resumen
    from core.lineas.sender import sender_de_linea
    from core.models import AvisoModuloDisponible

    desde = ahora - _ventana()
    pausa = _pausa()
    avisos = AvisoModuloDisponible.objects.select_related('curso', 'plantilla').filter(activo=True)
    for aviso in avisos:
        motivo = motivo_plantilla(aviso.plantilla, aviso.phone_number_id)
        if motivo:
            resumen['avisos_invalidos'] += 1
            logger.warning('aviso_modulo aviso=%s no sale: %s', aviso.pk, motivo)
            continue
        sender = sender_de_linea(aviso.phone_number_id)
        for habilitacion in _habilitaciones(aviso).filter(habilitado_desde__gt=desde, habilitado_desde__lte=ahora):
            for progreso in _esperando(aviso, habilitacion.modulo, ahora):
                estado = _enviar_uno(aviso, sender, progreso, habilitacion.modulo)
                if estado == 'enviado':
                    resumen['enviados'] += 1
                elif estado == 'fallido':
                    resumen['fallidos'] += 1
                if pausa:
                    time.sleep(pausa)
    logger.info('aviso_modulo resumen=%s', resumen)
    return resumen


def enviar_prueba(aviso, telefono: str) -> dict:
    """Envía el aviso con el primer módulo del calendario a un número interno. No deja registro."""
    from core.lineas.sender import sender_de_linea

    habilitacion = _habilitaciones(aviso).first()
    titulo = habilitacion.modulo.titulo if habilitacion else 'Módulo de prueba'
    variables = variables_aviso(aviso.plantilla, 'Prueba', titulo, aviso.curso.nombre)
    return sender_de_linea(aviso.phone_number_id).plantilla(
        telefono, aviso.plantilla.meta_name, variables, agente='aviso_modulo_prueba',
    )
