"""Envío de Campaña Meta con claim. Con el flag apagado no se usa.

INCIERTO no se reenvía. Un timeout pudo haber salido.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from core.meta_waba import (
    _destinatarios,
    _error_meta,
    _parametros_envio,
    _phone_default,
    _post,
    _version,
    campana_meta_habilitada,
)
from core.models_campana_meta import CampanaMeta, EnvioCampanaMeta

logger = logging.getLogger(__name__)

_RECLAMABLES = ('PENDIENTE', 'ERROR_REINTENTABLE')


def _codigos(nombre: str) -> set[str]:
    return {str(c) for c in (getattr(settings, nombre, None) or [])}


def clasificar_respuesta(status: int, data: dict) -> tuple[str, str]:
    err = _error_meta(data if isinstance(data, dict) else {})
    code = err['code']
    if status == 0 or status >= 500:
        return 'INCIERTO', code or str(status)
    if code == str(getattr(settings, 'META_CODIGO_TOKEN', '190')):
        return 'TOKEN', code
    if code in _codigos('META_CODIGOS_REINTENTABLES'):
        return 'ERROR_REINTENTABLE', code
    if code == str(getattr(settings, 'META_CODIGO_VENTANA', '131047')):
        return 'OMITIDO', 'ventana_cerrada'
    if code in _codigos('META_CODIGOS_ERROR'):
        return 'ERROR', code
    if status in (200, 201) and isinstance(data, dict) and data.get('messages'):
        return 'ENVIADO', ''
    return 'ERROR', code or 'desconocido'


def asegurar_pendientes(campana: CampanaMeta) -> None:
    ya = set(
        EnvioCampanaMeta.objects.filter(campana=campana).values_list('estudiante_id', flat=True)
    )
    nuevos = [
        EnvioCampanaMeta(campana=campana, estudiante=est, estado='PENDIENTE', respuesta='')
        for est in _destinatarios(campana)
        if est.id not in ya
    ]
    if nuevos:
        EnvioCampanaMeta.objects.bulk_create(nuevos, ignore_conflicts=True)


def reclamar(envio_id: int):
    token = uuid.uuid4()
    n = EnvioCampanaMeta.objects.filter(pk=envio_id, estado__in=_RECLAMABLES).update(
        estado='ENVIANDO',
        claim_token=token,
        claimed_at=timezone.now(),
        intentos=F('intentos') + 1,
    )
    if n != 1:
        return None
    return token


def marcar_enviando_viejos(minutos: int = 10) -> int:
    limite = timezone.now() - timedelta(minutes=minutos)
    return EnvioCampanaMeta.objects.filter(
        estado='ENVIANDO', claimed_at__lt=limite,
    ).update(estado='INCIERTO', omitido_motivo='enviando_viejo')


def _omitir(envio, motivo: str) -> None:
    envio.estado = 'OMITIDO'
    envio.omitido_motivo = motivo[:64]
    envio.save(update_fields=['estado', 'omitido_motivo'])


def ejecutar_campana_meta_v2(campana: CampanaMeta) -> dict:
    from core.consentimiento_wa import puede_recibir_plantilla
    from core.meta_token import marcar_token_invalido, token_invalido

    if not campana_meta_habilitada():
        raise ValueError('Campaña Meta está apagada (EKI_CAMPANA_META_ENABLED).')
    asegurar_pendientes(campana)
    plantilla = campana.plantilla
    phone_id = (campana.phone_number_id or _phone_default()).strip()
    base = str(getattr(settings, 'WHATSAPP_GRAPH_BASE_URL', 'https://graph.facebook.com')).rstrip('/')
    url = f'{base}/{_version()}/{phone_id}/messages'
    tope = int(getattr(settings, 'META_OPAQUE_MAX', 512) or 512)
    enviados = fallidos = omitidos = inciertos = 0
    envios = list(
        EnvioCampanaMeta.objects.filter(campana=campana, estado__in=_RECLAMABLES)
        .select_related('estudiante')
        .order_by('id')
    )
    for envio in envios:
        if token_invalido():
            _omitir(envio, 'token_invalido')
            omitidos += 1
            continue
        estudiante = envio.estudiante
        if not puede_recibir_plantilla(estudiante):
            _omitir(envio, 'optout' if estudiante.wa_optout_fecha else 'sin_optin')
            omitidos += 1
            continue
        if plantilla.estado != 'APPROVED':
            _omitir(envio, 'sin_plantilla')
            omitidos += 1
            continue
        if campana.pausada:
            break
        from core.campana_meta_ritmo import (
            anotar_resultado,
            bajo_tope_contactos,
            hueco_destino,
            pedir_token,
        )
        from core.locks import telefono_hash

        marca = telefono_hash(str(estudiante.telefono or ''))
        if not bajo_tope_contactos(marca):
            break
        ok_token, espera = pedir_token()
        if not ok_token:
            campana.save(update_fields=['total_enviados', 'ejecutada'])
            return {
                'enviados': enviados,
                'fallidos': fallidos,
                'omitidos': omitidos,
                'inciertos': inciertos,
                'espera': espera,
            }
        if not hueco_destino(marca):
            continue
        token = reclamar(envio.pk)
        if token is None:
            continue
        try:
            componentes = _parametros_envio(plantilla, campana, estudiante)
        except ValueError as exc:
            EnvioCampanaMeta.objects.filter(pk=envio.pk, claim_token=token).update(
                estado='ERROR', respuesta=str(exc)[:2000], error_codigo='params',
            )
            fallidos += 1
            continue
        payload = {
            'messaging_product': 'whatsapp',
            'to': str(estudiante.telefono or '').lstrip('+'),
            'type': 'template',
            'template': {
                'name': plantilla.meta_name,
                'language': {'code': plantilla.idioma or 'es'},
            },
            'biz_opaque_callback_data': f'envio:{envio.pk}'[:tope],
        }
        if componentes:
            payload['template']['components'] = componentes
        status, data = _post(url, payload)
        estado, motivo = clasificar_respuesta(status, data)
        if estado == 'TOKEN':
            marcar_token_invalido()
            EnvioCampanaMeta.objects.filter(pk=envio.pk, claim_token=token).update(
                estado='OMITIDO', omitido_motivo='token_invalido', error_codigo='190',
            )
            EnvioCampanaMeta.objects.filter(
                campana=campana, estado__in=_RECLAMABLES,
            ).update(estado='OMITIDO', omitido_motivo='token_invalido')
            omitidos += 1
            break
        wamid = ''
        if estado == 'ENVIADO':
            wamid = str((data.get('messages') or [{}])[0].get('id') or '')[:200]
            enviados += 1
        elif estado == 'INCIERTO':
            inciertos += 1
        elif estado == 'OMITIDO':
            omitidos += 1
        else:
            fallidos += 1
        EnvioCampanaMeta.objects.filter(pk=envio.pk, claim_token=token).update(
            estado=estado,
            wamid=wamid,
            error_codigo=(motivo or '')[:16],
            omitido_motivo=motivo[:64] if estado == 'OMITIDO' else '',
            respuesta=(_error_meta(data).get('message') or '')[:2000],
        )
        if estado == 'ENVIADO':
            anotar_resultado(campana, fallo=False, nuevo=True)
        elif estado == 'ERROR':
            anotar_resultado(campana, fallo=True, nuevo=True)
        campana.refresh_from_db(fields=['pausada', 'pausa_motivo'])
        if campana.pausada:
            break
    campana.total_enviados = EnvioCampanaMeta.objects.filter(
        campana=campana, estado='ENVIADO',
    ).count()
    quedan = EnvioCampanaMeta.objects.filter(campana=campana, estado__in=_RECLAMABLES).exists()
    if not quedan:
        campana.ejecutada = True
    campana.save(update_fields=['total_enviados', 'ejecutada'])
    return {
        'enviados': enviados,
        'fallidos': fallidos,
        'omitidos': omitidos,
        'inciertos': inciertos,
    }
