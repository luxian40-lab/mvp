"""Celery: revisión periódica del advisor de infra (reglas, no LLM)."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='core.tasks_infra.revisar_infra_advisor')
def revisar_infra_advisor():
    """
    Snapshot force + notificación email si overall pasa a ACTUAR.
    No envía WhatsApp. Máx. 1 mail cada 6h (cooldown en cache).
    """
    from core.infra_monitor import maybe_notify_infra_act, snapshot_infra

    snap = snapshot_infra(force=True)
    notify = maybe_notify_infra_act(snap)
    logger.info(
        'infra_advisor overall=%s notify=%s',
        snap.get('overall'),
        notify,
    )
    return {
        'overall': snap.get('overall'),
        'advisor_items': len((snap.get('advisor') or {}).get('items') or []),
        'notify': notify,
    }
