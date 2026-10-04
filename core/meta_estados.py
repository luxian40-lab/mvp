"""Aplica statuses de Cloud API al WhatsappLog saliente. No toca el curso."""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_RANGO = {'sent': 1, 'delivered': 2, 'read': 3}


def extraer_statuses(payload) -> list[dict]:
    encontrados = []
    if not isinstance(payload, dict):
        return encontrados
    for entry in payload.get('entry') or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get('changes') or []:
            if not isinstance(change, dict):
                continue
            value = change.get('value') or {}
            if not isinstance(value, dict):
                continue
            for status in value.get('statuses') or []:
                if isinstance(status, dict):
                    encontrados.append(status)
    return encontrados


def payload_solo_statuses(payload) -> bool:
    if not extraer_statuses(payload):
        return False
    for entry in (payload or {}).get('entry') or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get('changes') or []:
            value = (change or {}).get('value') or {}
            if isinstance(value, dict) and value.get('messages'):
                return False
    return True


def _puede_avanzar(actual: str, nuevo: str) -> bool:
    actual = (actual or '').strip().lower()
    nuevo = (nuevo or '').strip().lower()
    if not nuevo or nuevo == actual:
        return False
    if nuevo == 'failed':
        return actual in ('', 'pending', 'sent')
    if nuevo not in _RANGO:
        return False
    if actual == 'failed':
        return nuevo in ('delivered', 'read')
    return _RANGO[nuevo] > _RANGO.get(actual, 0)


_ENTREGA = {'sent': 1, 'delivered': 2, 'read': 3}


def _aplicar_status_envio(item: dict, mid: str) -> bool:
    """Actualiza el envío de campaña. No crea WhatsappLog."""
    from django.utils import timezone

    from core.models_campana_meta import EnvioCampanaMeta

    nuevo = str(item.get('status') or '').strip().lower()
    envio = EnvioCampanaMeta.objects.filter(wamid=mid).order_by('-id').first()
    opaco = str(item.get('biz_opaque_callback_data') or '')
    if envio is None and opaco.startswith('envio:'):
        try:
            pk = int(opaco.split(':', 1)[1])
        except ValueError:
            pk = 0
        if pk:
            envio = EnvioCampanaMeta.objects.filter(pk=pk, estado='INCIERTO').first()
            if envio is not None:
                envio.estado = 'ENVIADO'
                envio.wamid = mid[:200]
    if envio is None:
        return False
    actual = (envio.estado_entrega or '').strip().lower()
    errores = item.get('errors') or []
    code = ''
    if errores and isinstance(errores[0], dict):
        code = str(errores[0].get('code') or '')[:16]
    campos = ['estado', 'wamid', 'estado_entrega', 'error_codigo', 'entregado_en', 'leido_en']
    if nuevo == 'failed':
        if actual == 'read':
            return False
        envio.estado_entrega = 'failed'
        envio.error_codigo = code
    elif nuevo in _ENTREGA and _ENTREGA[nuevo] > _ENTREGA.get(actual, 0):
        envio.estado_entrega = nuevo
        if nuevo == 'delivered' and not envio.entregado_en:
            envio.entregado_en = timezone.now()
        if nuevo == 'read':
            envio.leido_en = timezone.now()
            if not envio.entregado_en:
                envio.entregado_en = envio.leido_en
    elif envio.estado == 'ENVIADO' and envio.wamid == mid[:200] and actual:
        return False
    envio.save(update_fields=campos)
    return True


def aplicar_statuses(statuses) -> int:
    from core.models import WhatsappLog

    actualizados = 0
    acciones = getattr(settings, 'META_ERROR_ACCIONES', {}) or {}
    for item in statuses or []:
        if not isinstance(item, dict):
            continue
        mid = str(item.get('id') or '').strip()
        if not mid:
            continue
        toco_envio = _aplicar_status_envio(item, mid)
        if toco_envio:
            actualizados += 1
        log = (
            WhatsappLog.objects.filter(mensaje_id=mid, tipo='SENT')
            .order_by('-id')
            .first()
        )
        if log is None:
            if not toco_envio:
                logger.debug('meta_status_desconocido id=%s', mid[:32])
            continue
        nuevo = str(item.get('status') or '').strip().lower()
        if not _puede_avanzar(log.estado, nuevo):
            continue
        campos = ['estado']
        log.estado = nuevo
        errores = item.get('errors') or []
        if errores and isinstance(errores[0], dict):
            code = str(errores[0].get('code') or '')[:16]
            title = str(errores[0].get('title') or '')[:500]
            accion = str(acciones.get(code) or '')
            log.error_codigo = code or None
            log.error_detalle = ' '.join(p for p in (accion, code, title) if p)[:2000]
            campos.extend(['error_codigo', 'error_detalle'])
            if accion == 'token_invalido' or code == '190':
                from core.meta_token import marcar_token_invalido

                marcar_token_invalido()
            elif accion == 'reintentar':
                logger.info('meta_error_reintentable code=%s', code)
        opaco = str(item.get('biz_opaque_callback_data') or '')[:120]
        if opaco:
            logger.debug('meta_status_opaque id=%s', mid[:32])
        log.save(update_fields=campos)
        actualizados += 1
    return actualizados


def encolar_statuses(payload) -> int:
    statuses = extraer_statuses(payload)
    if not statuses:
        return 0
    from core.tasks import procesar_statuses_meta_async

    procesar_statuses_meta_async.delay(statuses)
    return len(statuses)


def contar_fallos_meta_24h(desde) -> dict[str, int]:
    from django.db.models import Count

    from core.models import WhatsappLog

    filas = (
        WhatsappLog.objects.filter(
            tipo='SENT',
            canal='meta',
            fecha__gte=desde,
            error_codigo__isnull=False,
        )
        .exclude(error_codigo='')
        .values('error_codigo')
        .annotate(n=Count('id'))
    )
    return {str(fila['error_codigo']): int(fila['n']) for fila in filas}
