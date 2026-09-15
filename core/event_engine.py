"""Event Engine embrionario + Data Lake raw (Arco A slice).

- Outbox transaccional en PostgreSQL (EventOutbox).
- Publicación opcional a S3 lake/raw/... (DATA_LAKE_ENABLED).
- Correlación v0 de señales territoriales (umbrales densidad + k-anonimato).
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def data_lake_enabled() -> bool:
    return bool(getattr(settings, 'DATA_LAKE_ENABLED', False))


def seudonimizar_actor(actor_tipo: str, actor_id: str | int | None) -> str:
    raw = f"{actor_tipo}:{actor_id or ''}"
    salt = str(getattr(settings, 'DATA_LAKE_PSEUDO_SALT', 'eki-lake-v0') or 'eki-lake-v0')
    return hashlib.sha256(f'{salt}:{raw}'.encode('utf-8')).hexdigest()[:32]


def publicar_evento(
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
    org_id: int | None = None,
    territory_id: str = '',
    actor_tipo: str = 'system',
    actor_id: str | int | None = None,
    occurred_at=None,
    pii_class: str = 'internal',
    correlation_ids: list | None = None,
    session_or_trace_id: str = '',
) -> Any:
    """Escribe en outbox. No bloquea el webhook si falla el lake."""
    from core.models import EventOutbox

    event_id = uuid.uuid4()
    row = EventOutbox.objects.create(
        event_id=event_id,
        event_type=event_type,
        schema_version=SCHEMA_VERSION,
        occurred_at=occurred_at or timezone.now(),
        org_id=org_id,
        territory_id=(territory_id or '')[:32],
        actor_pseudo=seudonimizar_actor(actor_tipo, actor_id),
        session_or_trace_id=(session_or_trace_id or '')[:64],
        payload=payload or {},
        correlation_ids=correlation_ids or [],
        pii_class=pii_class or 'internal',
    )
    if data_lake_enabled():
        try:
            _flush_outbox_row_to_lake(row)
        except Exception:
            logger.exception('data_lake_flush_failed event_id=%s', event_id)
    return row


def _flush_outbox_row_to_lake(row) -> None:
    """Zona raw: lake/raw/{familia}/{yyyy}/{mm}/{dd}/{event_id}.json"""
    familia = (row.event_type or 'system').split('.')[0] or 'system'
    dt = row.occurred_at or timezone.now()
    key = (
        f"lake/raw/{familia}/{dt:%Y}/{dt:%m}/{dt:%d}/{row.event_id}.json"
    )
    body = {
        'event_id': str(row.event_id),
        'event_type': row.event_type,
        'schema_version': row.schema_version,
        'occurred_at': row.occurred_at.isoformat() if row.occurred_at else None,
        'ingested_at': row.ingested_at.isoformat() if row.ingested_at else None,
        'org_id': row.org_id,
        'territory_id': row.territory_id,
        'actor_pseudo': row.actor_pseudo,
        'session_or_trace_id': row.session_or_trace_id,
        'payload': row.payload,
        'correlation_ids': row.correlation_ids,
        'pii_class': row.pii_class,
    }
    prefix = str(getattr(settings, 'DATA_LAKE_S3_PREFIX', '') or '').strip().strip('/')
    if prefix:
        key = f'{prefix}/{key}'

    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None) or getattr(
        settings, 'AWS_S3_BUCKET_NAME', None
    )
    if not bucket:
        row.lake_uri = f'local://{key}'
        row.published_at = timezone.now()
        row.save(update_fields=['lake_uri', 'published_at'])
        return

    import boto3

    s3 = boto3.client(
        's3',
        region_name=getattr(settings, 'AWS_S3_REGION_NAME', None) or 'us-east-2',
    )
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json',
    )
    row.lake_uri = f's3://{bucket}/{key}'
    row.published_at = timezone.now()
    row.save(update_fields=['lake_uri', 'published_at'])


def flush_outbox_pendientes(limit: int = 100) -> int:
    from core.models import EventOutbox

    n = 0
    qs = EventOutbox.objects.filter(published_at__isnull=True).order_by('id')[:limit]
    for row in qs:
        try:
            _flush_outbox_row_to_lake(row)
            n += 1
        except Exception:
            logger.exception('flush_outbox_row_failed id=%s', row.pk)
    return n


def registrar_senal_territorial(
    *,
    tipo: str,
    territory_id: str,
    org_id: int | None = None,
    confianza: float = 0.7,
    fuente: str = 'manual',
    occurred_at=None,
    metadata: dict | None = None,
    actor_id: str | int | None = None,
):
    """Señal tipada (familia reporte territorial). Emite outbox + fila SenalTerritorial."""
    from core.models import SenalTerritorial

    tid = (territory_id or '').strip()
    if not tid:
        raise ValueError('territory_id requerido')
    tipo_n = (tipo or '').strip().lower()
    if not tipo_n:
        raise ValueError('tipo requerido')

    senal = SenalTerritorial.objects.create(
        tipo=tipo_n[:80],
        territory_id=tid[:32],
        org_id=org_id,
        confianza=max(0.0, min(1.0, float(confianza))),
        fuente=(fuente or 'manual')[:40],
        occurred_at=occurred_at or timezone.now(),
        metadata=metadata or {},
    )
    publicar_evento(
        event_type=f'reporte.{tipo_n}',
        payload={'senal_id': senal.pk, 'fuente': fuente, 'confianza': senal.confianza},
        org_id=org_id,
        territory_id=tid,
        actor_tipo='estudiante' if actor_id else 'system',
        actor_id=actor_id,
        occurred_at=senal.occurred_at,
        pii_class='aggregate_ok',
    )
    return senal


def correlacionar_clusters(
    *,
    ventana_horas: int | None = None,
    min_k: int | None = None,
    tipo_prefijo: str = '',
) -> list:
    """
    Correlación v0: densidad por territory_id + ventana.

    Algoritmo:
    1) Agrupa señales en la ventana por (territory_id, familia_tipo).
    2) Si conteo >= min_k (k-anonimato), crea/actualiza AlertaTerritorial.
    3) Score = min(1.0, conteo / (min_k * 2)) * confianza_media.

    No usa ML; es el umbral conservador de la visión (alerta v0).
    """
    from core.models import AlertaTerritorial, SenalTerritorial

    ventana = int(
        ventana_horas
        if ventana_horas is not None
        else getattr(settings, 'ALERTA_TERRITORIAL_VENTANA_HORAS', 72) or 72
    )
    min_k = int(
        min_k
        if min_k is not None
        else getattr(settings, 'ALERTA_TERRITORIAL_MIN_K', 3) or 3
    )
    since = timezone.now() - timedelta(hours=ventana)
    qs = SenalTerritorial.objects.filter(occurred_at__gte=since)
    if tipo_prefijo:
        qs = qs.filter(tipo__startswith=tipo_prefijo)

    # Familia = primeros dos segmentos (salud.sintoma) o el tipo completo
    filas = list(
        qs.values('territory_id', 'tipo')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    creadas = []
    for row in filas:
        if row['n'] < min_k:
            continue
        tid = row['territory_id']
        tipo = row['tipo']
        partes = tipo.split('.')
        familia = '.'.join(partes[:2]) if len(partes) >= 2 else tipo
        subtipo = f'cluster.{partes[-1]}' if partes else 'cluster'

        conf_avg = (
            qs.filter(territory_id=tid, tipo=tipo).values_list('confianza', flat=True)
        )
        confs = list(conf_avg)
        conf_media = sum(confs) / len(confs) if confs else 0.5
        score = round(min(1.0, row['n'] / float(min_k * 2)) * conf_media, 4)

        alerta, created = AlertaTerritorial.objects.update_or_create(
            familia=familia[:80],
            subtipo=subtipo[:80],
            territory_id=tid[:32],
            ventana_horas=ventana,
            estado='detectada',
            defaults={
                'conteo': row['n'],
                'score': score,
                'min_k': min_k,
                'explicacion': (
                    f'{row["n"]} señales «{tipo}» en territorio {tid} '
                    f'en {ventana}h (umbral k={min_k}).'
                ),
                'metadata': {
                    'tipo': tipo,
                    'algoritmo': 'density_v0',
                    'confianza_media': conf_media,
                },
            },
        )
        if not created:
            alerta.conteo = row['n']
            alerta.score = score
            alerta.explicacion = (
                f'{row["n"]} señales «{tipo}» en territorio {tid} '
                f'en {ventana}h (umbral k={min_k}).'
            )
            alerta.metadata = {
                'tipo': tipo,
                'algoritmo': 'density_v0',
                'confianza_media': conf_media,
            }
            alerta.save(
                update_fields=['conteo', 'score', 'explicacion', 'metadata', 'actualizado_en']
            )
        publicar_evento(
            event_type=f'alerta.{familia}.{subtipo}',
            payload={
                'alerta_id': alerta.pk,
                'conteo': alerta.conteo,
                'score': alerta.score,
                'ventana_horas': ventana,
            },
            territory_id=tid,
            pii_class='aggregate_ok',
        )
        creadas.append(alerta)
    return creadas
