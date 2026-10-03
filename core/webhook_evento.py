"""Idempotencia del webhook: un wamid o MessageSid se reclama una sola vez."""
from __future__ import annotations

import copy
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db import models

logger = logging.getLogger(__name__)

CANAL_META = 'meta'
CANAL_TWILIO = 'twilio'


class WebhookEventoProcesado(models.Model):
    canal = models.CharField(max_length=10)
    external_id = models.CharField(max_length=128)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        constraints = [
            models.UniqueConstraint(
                fields=['canal', 'external_id'],
                name='uniq_webhook_evento',
            ),
        ]

    def __str__(self):
        return f'{self.canal}:{self.external_id}'


def external_id_de_payload(datos) -> str:
    """Id del mensaje en las tres tareas del webhook.

    Twilio educativo y Nat: MessageSid del POST.
    Meta sandbox: inbound_desde_meta_message copia message['id'] (wamid) a MessageSid.
    Si el dict solo trae id, se usa ese valor.
    """
    if not isinstance(datos, dict):
        return ''
    return str(datos.get('MessageSid') or datos.get('id') or '').strip()[:128]


def reclamar_evento(canal, external_id) -> bool:
    try:
        with transaction.atomic():
            WebhookEventoProcesado.objects.create(canal=canal, external_id=external_id)
        return True
    except IntegrityError:
        return False


class WebhookFallido(models.Model):
    """Mensaje que la tarea no pudo terminar. El payload tiene teléfono: solo staff, purga a 10 días."""

    canal = models.CharField(max_length=16)
    external_id = models.CharField(max_length=128, db_index=True)
    payload = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'webhook fallido'
        verbose_name_plural = 'webhooks fallidos'

    def __str__(self):
        return f'{self.canal}:{self.external_id}'


def purgar_webhooks_fallidos(dias: int = 10) -> int:
    """Borra fallos más viejos que `dias`. La usa limpiar_logs_antiguos."""
    from django.utils import timezone

    limite = timezone.now() - timezone.timedelta(days=dias)
    eliminados, _ = WebhookFallido.objects.filter(creado__lt=limite).delete()
    return eliminados


def purgar_eventos_procesados(dias: int = 10) -> int:
    """Borra reclamos más viejos que `dias`. La usa limpiar_logs_antiguos."""
    from django.utils import timezone

    limite = timezone.now() - timezone.timedelta(days=dias)
    eliminados, _ = WebhookEventoProcesado.objects.filter(creado__lt=limite).delete()
    return eliminados


def liberar_eventos(canal, external_ids) -> None:
    ids = [str(item) for item in (external_ids or []) if item]
    if not ids:
        return
    WebhookEventoProcesado.objects.filter(canal=canal, external_id__in=ids).delete()
    if canal == CANAL_META:
        try:
            from django.core.cache import cache

            cache.delete_many([f'sandbox_in:{sid}' for sid in ids])
        except Exception:
            logger.exception('webhook_liberar_cache_fail')


def firma_meta_invalida(raw_body: bytes, signature_header: str) -> bool:
    """True si hay que rechazar el POST de mensajes antes de reclamar.

    Con WHATSAPP_REQUIRE_SIGNATURE=False (default), un secreto vacío no rechaza.
    Con el flag en True, secreto vacío o firma inválida rechazan.
    """
    secret = (getattr(settings, 'WHATSAPP_APP_SECRET', None) or '').strip()
    exigir = bool(getattr(settings, 'WHATSAPP_REQUIRE_SIGNATURE', False))
    if not secret:
        return exigir
    from core.meta_waba import firma_meta_ok

    return not firma_meta_ok(raw_body or b'', signature_header or '', secret)


def preparar_payload_meta(payload: dict) -> tuple[dict, list[str], bool]:
    """Reclama cada messages[].id. No toca statuses.

    Devuelve (payload filtrado, ids reclamados, seguir).
    seguir es False cuando todos los mensajes ya estaban reclamados
    y el payload no trae statuses ni otro tipo de cambio.
    """
    payload = copy.deepcopy(payload) if isinstance(payload, dict) else {}
    reclamados: list[str] = []
    vio_mensajes = False
    quedo_alguno = False
    hay_otro_trabajo = False

    for entry in payload.get('entry') or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get('changes') or []:
            if not isinstance(change, dict):
                continue
            field = change.get('field')
            value = change.get('value')
            if not isinstance(value, dict):
                if field and field != 'messages':
                    hay_otro_trabajo = True
                continue
            if value.get('statuses'):
                hay_otro_trabajo = True
            if field and field != 'messages':
                hay_otro_trabajo = True
            messages = value.get('messages') or []
            if not isinstance(messages, list):
                continue
            kept = []
            for message in messages:
                if not isinstance(message, dict):
                    vio_mensajes = True
                    quedo_alguno = True
                    kept.append(message)
                    continue
                mid = str(message.get('id') or '').strip()[:128]
                vio_mensajes = True
                if not mid:
                    quedo_alguno = True
                    kept.append(message)
                    continue
                if reclamar_evento(CANAL_META, mid):
                    reclamados.append(mid)
                    quedo_alguno = True
                    kept.append(message)
            value['messages'] = kept

    if vio_mensajes and not quedo_alguno and not hay_otro_trabajo:
        return payload, reclamados, False
    return payload, reclamados, True


def reclamar_twilio(data, *, es_status: bool) -> tuple[bool, list[str]]:
    """Status callbacks no se deduplican. Un MessageSid nuevo se reclama."""
    if es_status:
        return True, []
    sid = str((data or {}).get('MessageSid') or '').strip()[:128]
    if not sid:
        return True, []
    if not reclamar_evento(CANAL_TWILIO, sid):
        return False, []
    return True, [sid]
