"""Snapshot ligero de infra (Redis / DB / S3) para admin.

Pensado para polling cada 30s: timeouts cortos + caché corta.
Incluye playbooks detallados: cuándo NO tocar vs cuándo cambiar instancia / ElastiCache / etc.
"""
from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.core.cache import cache

CACHE_KEY = 'eki_infra_monitor_v2'
CACHE_SECONDS = 20

_LOCAL: dict[str, Any] = {'ts': 0.0, 'payload': None}

# Baseline documentado (medición ~jul 2026). Sirve de referencia en el panel.
BASELINE = {
    'rds_instance': 'db.t4g.micro',
    'rds_allocated_gb': 20,
    'rds_max_storage_gb': 1000,
    'rds_multi_az': False,
    'rds_used_gb_approx': 1.7,
    'rds_cpu_avg_pct_approx': 3.6,
    's3_bucket': 'eki-produccion',
    's3_used_gb_approx': 1.75,
    'eb_env': 'eki-prod-final',
    'region': 'us-east-2',
}

# Capacidad operativa documentada (1 instancia t3.medium + Redis local + RDS micro).
# Estimaciones conservadoras; re-medir con `manage.py medir_capacidad_eki`.
CAPACITY_LIMITS = {
    'estudiantes_activos_db_comodo': 5_000,
    'estudiantes_activos_db_techo': 15_000,
    'mensajes_wa_concurrentes_comodo': 30,
    'mensajes_wa_concurrentes_techo': 80,
    'gunicorn_workers_estimado': 3,
    'celery_concurrency_estimado': 2,
    'campana_destinatarios_comodo': 500,
    'campana_destinatarios_techo': 2_000,
    'nota': (
        'Comodo = sin saturar t3.medium actual. Techo = riesgo de cola/timeout; '
        'activar WEBHOOK_CELERY_ASYNC=true, NAT_WEBHOOK_CELERY_ASYNC=true y/o 2ª instancia EB / ElastiCache.'
    ),
}


def _cache_get():
    try:
        return cache.get(CACHE_KEY)
    except Exception:
        now = time.time()
        if _LOCAL['payload'] and (now - float(_LOCAL['ts'])) < CACHE_SECONDS:
            return _LOCAL['payload']
        return None


def _cache_set(payload: dict[str, Any]) -> None:
    _LOCAL['ts'] = time.time()
    _LOCAL['payload'] = payload
    try:
        cache.set(CACHE_KEY, payload, CACHE_SECONDS)
    except Exception:
        pass


def _mask_url(url: str) -> str:
    if not url:
        return '(vacío)'
    if '@' in url:
        pre, post = url.split('@', 1)
        if '//' in pre:
            scheme, _rest = pre.split('//', 1)
            return f'{scheme}//***@{post}'
    return url


def _human_bytes(n: int | float | None) -> str:
    if n is None:
        return '—'
    n = float(n)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return f'{n:.1f} {unit}' if unit != 'B' else f'{int(n)} B'
        n /= 1024
    return f'{n:.1f} TB'


def _redis_status() -> dict[str, Any]:
    broker = getattr(settings, 'CELERY_BROKER_URL', '') or ''
    out: dict[str, Any] = {
        'ok': False,
        'broker': _mask_url(broker),
        'mode': 'local' if ('127.0.0.1' in broker or 'localhost' in broker) else 'external',
        'latency_ms': None,
        'error': None,
    }
    if not broker:
        out['error'] = 'CELERY_BROKER_URL vacío'
        return out
    try:
        import redis
        from urllib.parse import urlparse

        u = urlparse(broker)
        t0 = time.perf_counter()
        r = redis.Redis(
            host=u.hostname or '127.0.0.1',
            port=u.port or 6379,
            db=int((u.path or '/0').lstrip('/') or 0),
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
            ssl=broker.startswith('rediss://'),
        )
        out['ok'] = bool(r.ping())
        out['latency_ms'] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:
        out['error'] = str(exc)[:200]
    return out


def _db_status() -> dict[str, Any]:
    from django.db import connection

    out: dict[str, Any] = {
        'ok': False,
        'engine': settings.DATABASES.get('default', {}).get('ENGINE', ''),
        'size_bytes': None,
        'size_human': None,
        'size_gb': None,
        'latency_ms': None,
        'error': None,
        'note': None,
        'allocated_gb_baseline': BASELINE['rds_allocated_gb'],
        'used_pct_of_allocated': None,
    }
    try:
        t0 = time.perf_counter()
        with connection.cursor() as cur:
            if connection.vendor == 'postgresql':
                cur.execute('SELECT pg_database_size(current_database())')
                size = int(cur.fetchone()[0])
                out['size_bytes'] = size
                out['size_human'] = _human_bytes(size)
                out['size_gb'] = round(size / (1024 ** 3), 3)
                allocated = float(BASELINE['rds_allocated_gb'])
                out['used_pct_of_allocated'] = round((out['size_gb'] / allocated) * 100, 2)
                out['note'] = (
                    f'RDS Postgres · tamaño lógico de esta DB. '
                    f'Disco allocated baseline {allocated:g} GB '
                    f'(autoscaling hasta {BASELINE["rds_max_storage_gb"]} GB).'
                )
            else:
                cur.execute('SELECT 1')
                out['note'] = f'Engine {connection.vendor} (sin pg_database_size)'
        out['ok'] = True
        out['latency_ms'] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:
        out['error'] = str(exc)[:200]
    return out


def _s3_status() -> dict[str, Any]:
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None) or BASELINE['s3_bucket']
    region = getattr(settings, 'AWS_S3_REGION_NAME', '') or BASELINE['region']
    out: dict[str, Any] = {
        'ok': False,
        'bucket': bucket or '(no configurado)',
        'region': region,
        'reachable': False,
        'baseline_used_gb': BASELINE['s3_used_gb_approx'],
        'error': None,
        'note': (
            'S3 no tiene cuota fija de GB: escala solo y se cobra por GB-mes + requests. '
            f'Baseline reciente ~{BASELINE["s3_used_gb_approx"]} GB en {BASELINE["s3_bucket"]}.'
        ),
    }
    if not bucket:
        out['error'] = 'AWS_STORAGE_BUCKET_NAME vacío'
        return out
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            's3',
            region_name=region or None,
            config=Config(connect_timeout=2, read_timeout=3, retries={'max_attempts': 1}),
        )
        client.head_bucket(Bucket=bucket)
        out['ok'] = True
        out['reachable'] = True
    except Exception as exc:
        out['error'] = str(exc)[:200]
        out['note'] = (
            'No se pudo hacer HeadBucket desde este proceso (credenciales/red). '
            'En prod EB con rol IAM debería marcar alcanzable.'
        )
    return out


def _verdict_rds(db: dict[str, Any]) -> dict[str, Any]:
    """ok | watch | act según señales locales (no CloudWatch CPU en vivo)."""
    size_gb = db.get('size_gb')
    pct = db.get('used_pct_of_allocated')
    lat = db.get('latency_ms')
    status = 'ok'
    label = 'HOY: NO CAMBIAR INSTANCIA'
    reasons = []

    if not db.get('ok'):
        status = 'act'
        label = 'ACTUAR: DB NO RESPONDE'
        reasons.append('Ping/query a Postgres falló — revisar RDS Security Group, credenciales o disco.')
    else:
        if lat is not None and lat > 500:
            status = 'act'
            label = 'ACTUAR: LATENCIA ALTA'
            reasons.append(f'Query de tamaño tardó {lat} ms (>500). Revisar carga RDS / conexiones.')
        elif lat is not None and lat > 150:
            status = 'watch'
            label = 'VIGILAR: latencia elevada'
            reasons.append(f'Query {lat} ms (>150). Aún no obliga upgrade, pero mirar CloudWatch CPU.')
        if pct is not None and pct >= 80:
            status = 'act'
            label = 'ACTUAR: DISCO CERCA DEL LÍMITE'
            reasons.append(
                f'DB usa ~{pct}% del allocated {BASELINE["rds_allocated_gb"]} GB. '
                'Aunque hay autoscaling, revisar crecimiento anómalo y costo.'
            )
        elif pct is not None and pct >= 50:
            if status == 'ok':
                status = 'watch'
                label = 'VIGILAR: disco al 50%+'
            reasons.append(f'Disco lógico ~{pct}% del allocated. Autoscaling puede subir el volumen solo.')
        if size_gb is not None and size_gb < 5 and status == 'ok':
            reasons.append(
                f'Tamaño actual ~{size_gb} GB vs baseline ~{BASELINE["rds_used_gb_approx"]} GB — holgado.'
            )

    return {'status': status, 'label': label, 'reasons': reasons}


def _verdict_redis(redis_s: dict[str, Any]) -> dict[str, Any]:
    if not redis_s.get('ok'):
        return {
            'status': 'act',
            'label': 'ACTUAR: REDIS CAÍDO',
            'reasons': [
                'Celery/campañas/drip/RAG dependen de Redis. '
                'Si es local: reiniciar redis6 en la instancia EB. '
                'Si ya hay ElastiCache: revisar SG y CELERY_BROKER_URL.',
            ],
        }
    if redis_s.get('mode') == 'local':
        return {
            'status': 'ok',
            'label': 'HOY: REDIS LOCAL OK (sin ElastiCache)',
            'reasons': [
                'Con 1 instancia EB y poco Celery es el diseño actual. '
                'NO crear ElastiCache solo “por si acaso”.',
            ],
        }
    return {
        'status': 'ok',
        'label': 'HOY: REDIS EXTERNO (ElastiCache) OK',
        'reasons': ['Broker fuera de la caja — correcto para multi-instancia / durabilidad.'],
    }


def _verdict_s3(s3: dict[str, Any]) -> dict[str, Any]:
    if not s3.get('ok'):
        return {
            'status': 'watch',
            'label': 'VIGILAR: S3 no verificado desde aquí',
            'reasons': [
                'HeadBucket falló desde este proceso. En prod con IAM suele funcionar. '
                'No implica upgrade; revisar rol de la instancia si media falla en uploads.',
            ],
        }
    return {
        'status': 'ok',
        'label': 'HOY: NO CAMBIAR S3',
        'reasons': [
            f'Baseline ~{BASELINE["s3_used_gb_approx"]} GB. S3 escala solo; no hay “cambiar de instancia S3”.',
        ],
    }


def _playbooks(redis_s: dict, db: dict, s3: dict) -> list[dict[str, Any]]:
    """Guías muy detalladas: qué hacer en cada umbral."""
    v_rds = _verdict_rds(db)
    v_redis = _verdict_redis(redis_s)
    v_s3 = _verdict_s3(s3)

    return [
        {
            'id': 'rds',
            'title': 'Base de datos — Amazon RDS PostgreSQL',
            'verdict': v_rds,
            'current': {
                'recurso': f'{BASELINE["rds_instance"]} · eki-database',
                'region': BASELINE['region'],
                'disco': (
                    f'{BASELINE["rds_allocated_gb"]} GB allocated '
                    f'(autoscaling max {BASELINE["rds_max_storage_gb"]} GB)'
                ),
                'multi_az': 'No',
                'vivo_tamano': db.get('size_human') or '—',
                'vivo_pct_allocated': (
                    f'{db["used_pct_of_allocated"]}%' if db.get('used_pct_of_allocated') is not None else '—'
                ),
                'vivo_latencia_ms': db.get('latency_ms'),
                'cpu_baseline': f'~{BASELINE["rds_cpu_avg_pct_approx"]}% promedio (CloudWatch, jul 2026)',
            },
            'actions': [
                {
                    'action_type': 'NO_HACER_NADA',
                    'when': (
                        'CPU promedio < 40% en horas pico, disco < 50% del allocated, '
                        'sin timeouts en WhatsApp/portal, latencia de query de tamaño < 150 ms.'
                    ),
                    'do': 'Dejar db.t4g.micro. No pagar más.',
                    'specs': (
                        'db.t4g.micro ≈ 2 vCPU burstable, 1 GB RAM. Suficiente para MVP B2B '
                        'con carga actual (~3–7% CPU observada).'
                    ),
                    'approx_cost': 'Mantener costo actual del micro (orden ~US$12–15/mes + storage).',
                    'how': 'Nada en consola AWS.',
                },
                {
                    'action_type': 'CAMBIAR_INSTANCIA',
                    'when': (
                        'CPU promedio > 60–70% en horas pico varios días SEGUIDOS, '
                        'o picos > 90% sostenidos, o reportes/admin > 5–10 s habituales, '
                        'o errores de conexión bajo carga concurrente.'
                    ),
                    'do': 'Modify DB instance: db.t4g.micro → db.t4g.small',
                    'specs': (
                        'db.t4g.small ≈ 2 vCPU burstable, 2 GB RAM. '
                        'Misma familia Graviton. Downtime corto (reboot) en Single-AZ. '
                        'Aplicar en ventana de bajo tráfico. Snapshot automático recomendado antes.'
                    ),
                    'approx_cost': 'Roughly ~2× el compute del micro (verificar Pricing Calculator us-east-2).',
                    'how': (
                        'AWS Console → RDS → eki-database → Modify → DB instance class → '
                        'db.t4g.small → Apply immediately o en maintenance window.'
                    ),
                },
                {
                    'action_type': 'SOLO_DISCO',
                    'when': 'FreeStorageSpace < 20% o used_pct_of_allocated > 80% sin CPU alta.',
                    'do': 'Subir allocated storage (o dejar que autoscaling suba) + revisar tablas grandes.',
                    'specs': (
                        'Ya tienes MaxAllocatedStorage=1000 GB. El autoscaling puede crecer solo; '
                        'vigilar factura. Revisar logs WhatsappLog, EventoIA, media huérfana en DB.'
                    ),
                    'approx_cost': 'Storage gp3 ~US$0.115/GB-mes (orden de magnitud us-east).',
                    'how': 'RDS → Modify → Allocated storage, o confiar en autoscaling + alarmas CloudWatch.',
                },
                {
                    'action_type': 'MULTI_AZ',
                    'when': (
                        'SLA comercial: la DB no puede caer si falla una Availability Zone. '
                        'NO lo actives solo por “mejores prácticas” con poco tráfico.'
                    ),
                    'do': 'Enable Multi-AZ',
                    'specs': 'Standby síncrono en otra AZ. Failover automático ~1–2 min. No mejora lectura.',
                    'approx_cost': '~2× instancia + storage (casi duplica la factura RDS).',
                    'how': 'RDS → Modify → Multi-AZ deployment → Yes.',
                },
                {
                    'action_type': 'READ_REPLICA',
                    'when': 'Muchísima lectura analítica (dashboards) que compite con writes de WhatsApp.',
                    'do': 'Crear read replica y apuntar reportes pesados ahí (código aparte).',
                    'specs': 'Réplica asíncrona. No uses replica para writes. Solo si small no basta.',
                    'approx_cost': 'Otra instancia completa (casi +100% compute lectura).',
                    'how': 'RDS → Actions → Create read replica. Luego DATABASE_URL de solo-lectura en workers analytics.',
                },
            ],
            'cloudwatch_checks': [
                'CPUUtilization (Average 1h / 1d)',
                'FreeStorageSpace',
                'DatabaseConnections',
                'ReadLatency / WriteLatency',
            ],
        },
        {
            'id': 'redis',
            'title': 'Redis / Celery broker',
            'verdict': v_redis,
            'current': {
                'modo_vivo': redis_s.get('mode'),
                'broker': redis_s.get('broker'),
                'ping_ok': redis_s.get('ok'),
                'latencia_ms': redis_s.get('latency_ms'),
                'diseno_actual': 'Redis local en la caja EB (.ebextensions + postdeploy)',
            },
            'actions': [
                {
                    'action_type': 'NO_HACER_NADA',
                    'when': (
                        '1 sola instancia EB, campañas/drip estables, sin pérdida de colas tras deploy, '
                        'pocas tareas Celery/hora.'
                    ),
                    'do': 'Seguir con Redis local. Código ya soporta ElastiCache sin redeploy de lógica.',
                    'specs': 'Broker redis://127.0.0.1:6379/0. USE_LOCAL_REDIS default = 1.',
                    'approx_cost': 'US$0 extra (vive en el EC2 de EB).',
                    'how': 'No crear ElastiCache.',
                },
                {
                    'action_type': 'ELASTICACHE',
                    'when': (
                        'CUALQUIERA: (1) Auto Scaling / EB con 2+ instancias; '
                        '(2) colas Celery se pierden tras replace/deploy; '
                        '(3) campañas/RAG críticas no pueden quedar en cero si muere el EC2; '
                        '(4) >~50–100 tareas Celery/hora sostenidas o campañas >500 destinatarios con fallos de broker.'
                    ),
                    'do': 'Crear ElastiCache Redis/Valkey cache.t4g.micro + apuntar env EB',
                    'specs': (
                        'Misma VPC/SG que eki-prod-final. Puerto 6379. '
                        'Env: CELERY_BROKER_URL, CELERY_RESULT_BACKEND, USE_LOCAL_REDIS=0. '
                        'Ver docs/RUNBOOK_REDIS_CHROMA.md y docs/UMBRAL_ELASTICACHE.md.'
                    ),
                    'approx_cost': '~US$10–12/mes (cache.t4g.micro Redis OSS) o ~US$9 Valkey.',
                    'how': (
                        'ElastiCache → Create → Redis → t4g.micro → pegar endpoint en EB Configuration → '
                        'Redeploy. Verificar: manage.py diagnostico_infra --ping'
                    ),
                },
                {
                    'action_type': 'REINICIAR_LOCAL',
                    'when': 'Ping Redis falla y mode=local.',
                    'do': 'Reiniciar servicio redis6 en la instancia (o redeploy).',
                    'specs': 'systemctl restart redis6 (vía eb ssh). Hook postdeploy también intenta start si USE_LOCAL=1.',
                    'approx_cost': 'US$0',
                    'how': 'eb ssh eki-prod-final → sudo systemctl status redis6 / restart.',
                },
            ],
            'cloudwatch_checks': [
                'Tras ElastiCache: CurrConnections, Evictions, CPUUtilization, EngineCPUUtilization',
                'Antes: logs Celery worker/beat en EB',
            ],
        },
        {
            'id': 's3',
            'title': 'Almacenamiento de archivos — Amazon S3',
            'verdict': v_s3,
            'current': {
                'bucket': s3.get('bucket'),
                'region': s3.get('region'),
                'alcanzable': s3.get('reachable'),
                'uso_baseline_gb': BASELINE['s3_used_gb_approx'],
            },
            'actions': [
                {
                    'action_type': 'NO_HACER_NADA',
                    'when': 'Uso < ~50 GB y uploads/descargas normales (estado actual ~1.8 GB).',
                    'do': 'No “cambiar instancia”. S3 no se escala como RDS.',
                    'specs': 'Object storage ilimitado práctico. Costo = storage + PUT/GET + egress.',
                    'approx_cost': 'Standard ~US$0.023/GB-mes → ~US$0.04/mes solo storage hoy.',
                    'how': 'Nada.',
                },
                {
                    'action_type': 'LIFECYCLE',
                    'when': 'Costo storage/request sube o hay muchos archivos viejos (certificados/RAG históricos).',
                    'do': 'Lifecycle: Transition a Intelligent-Tiering o Glacier tras N días.',
                    'specs': 'No borra datos activos. Definir prefijos media/ antiguos.',
                    'approx_cost': 'Ahorro variable; Glacier mucho más barato en frío.',
                    'how': 'S3 → bucket → Management → Lifecycle rules.',
                },
                {
                    'action_type': 'CLOUDFRONT',
                    'when': 'Miles de descargas concurrentes o latencia alta de media pública.',
                    'do': 'Distribución CloudFront delante del bucket.',
                    'specs': 'CDN global + menos egress directo S3. Requiere ajustar MEDIA_URL / dominio.',
                    'approx_cost': 'Tráfico CDN (suele ser menor que egress S3 repetido).',
                    'how': 'CloudFront → Origin = S3 bucket → invalidation al cambiar assets.',
                },
            ],
            'cloudwatch_checks': [
                'BucketSizeBytes (StandardStorage)',
                'NumberOfObjects',
                'AllRequests / 4xxErrors',
            ],
        },
        {
            'id': 'eb',
            'title': 'Aplicación — Elastic Beanstalk (EC2)',
            'verdict': {
                'status': 'ok',
                'label': 'HOY: 1 INSTANCIA ESTÁ BIEN',
                'reasons': [
                    f'Entorno {BASELINE["eb_env"]}. Con 1 caja Redis local es coherente. '
                    'Pasar a 2+ instancias OBLIGA ElastiCache el mismo día.',
                ],
            },
            'current': {
                'environment': BASELINE['eb_env'],
                'health_hint': 'Revisar EB Console Health (Green/Yellow/Red)',
            },
            'actions': [
                {
                    'action_type': 'NO_HACER_NADA',
                    'when': 'CPU EC2 estable, 1 instancia, deploys verdes, sin 502 sostenidos.',
                    'do': 'Quedarse en single instance / ASG=1.',
                    'specs': 'Procfile: web + worker + beat + worker_rag en la misma caja.',
                    'approx_cost': 'Costo EC2 actual del env.',
                    'how': 'Nada.',
                },
                {
                    'action_type': 'SUBIR_TAMANO_EC2',
                    'when': 'CPU/RAM del EC2 al límite (no confundir con CPU de RDS).',
                    'do': 'Cambiar instance type del environment (ej. t3.small → t3.medium).',
                    'specs': 'Afecta web+workers juntos. Medir con EB monitoring / CloudWatch EC2.',
                    'approx_cost': 'Según tipo; medium suele ~2× small.',
                    'how': 'EB → Configuration → Capacity / Instance type.',
                },
                {
                    'action_type': 'ESCALAR_A_2_INSTANCIAS',
                    'when': 'Necesitas HA web o más throughput HTTP concurrente.',
                    'do': 'Load balanced + min 2 instances — Y el mismo día ElastiCache.',
                    'specs': (
                        'Sin ElastiCache, cada instancia tendría Redis distinto = colas rotas. '
                        'Chroma multi-writer en EFS también es riesgoso (ver runbook).'
                    ),
                    'approx_cost': '2× EC2 + ALB + ElastiCache (~US$10–12).',
                    'how': 'EB Capacity → Load balanced → Min=2 + crear ElastiCache primero.',
                },
            ],
            'cloudwatch_checks': [
                'EnvironmentHealth',
                'CPUUtilization (EC2)',
                '5xx en ALB / ApplicationRequests5xx',
            ],
        },
        {
            'id': 'chroma',
            'title': 'Vector store — Chroma (RAG Nati)',
            'verdict': {
                'status': 'ok',
                'label': 'HOY: DISCO INSTANCIA /var/app/chroma_data',
                'reasons': [
                    'Persiste entre deploys en la misma caja; se pierde si AWS REEMPLAZA el EC2. '
                    'EFS solo cuando ese riesgo sea inaceptable.',
                ],
            },
            'current': {
                'path_prod_default': '/var/app/chroma_data',
                'env_override': 'CHROMA_DB_DIR',
            },
            'actions': [
                {
                    'action_type': 'NO_HACER_NADA',
                    'when': '1 instancia, reindexar RAG es aceptable tras replace raro.',
                    'do': 'Dejar CHROMA_DB_DIR default.',
                    'specs': 'Ver settings_production.CHROMA_DB_DIR',
                    'approx_cost': 'US$0 extra',
                    'how': 'Nada.',
                },
                {
                    'action_type': 'EFS',
                    'when': 'No puedes permitirte reindexar tras replace de instancia, o planeas 2 cajas con un solo writer.',
                    'do': 'Montar EFS + CHROMA_DB_DIR=/mnt/efs/chroma_data',
                    'specs': (
                        'NFS 2049 desde SG EB. Cuidado: multi-writer Chroma en EFS puede corromper. '
                        'Con ASG>1 preferir un solo worker RAG o vector DB remoto a futuro.'
                    ),
                    'approx_cost': 'Pocos US$/mes en volumen pequeño + throughput.',
                    'how': 'docs/RUNBOOK_REDIS_CHROMA.md sección EFS.',
                },
            ],
            'cloudwatch_checks': ['Disco libre en EC2', 'Errores de indexación Celery cola rag_index'],
        },
    ]


def _recommended_action(pb: dict[str, Any], status: str) -> dict[str, Any] | None:
    """Elige el primer paso operativo (no NO_HACER_NADA) del playbook."""
    preferred_by_id = {
        'rds': ('SOLO_DISCO', 'CAMBIAR_INSTANCIA', 'MULTI_AZ', 'READ_REPLICA'),
        'redis': ('REINICIAR_LOCAL', 'ELASTICACHE'),
        's3': ('LIFECYCLE', 'CLOUDFRONT'),
        'eb': ('SUBIR_TAMANO_EC2', 'ESCALAR_A_2_INSTANCIAS'),
        'chroma': ('EFS',),
    }
    actions = [a for a in (pb.get('actions') or []) if a.get('action_type') != 'NO_HACER_NADA']
    if not actions:
        return None
    order = preferred_by_id.get(pb.get('id') or '', ())
    by_type = {a.get('action_type'): a for a in actions}
    for t in order:
        if t in by_type:
            # En watch no empujar ESCALAR/MULTI_AZ como “hazlo ya”
            if status == 'watch' and t in ('ESCALAR_A_2_INSTANCIAS', 'MULTI_AZ', 'READ_REPLICA', 'ELASTICACHE'):
                continue
            return by_type[t]
    return actions[0]


def build_infra_advisor(playbooks: list[dict[str, Any]], overall: str) -> dict[str, Any]:
    """
    “Agente” operativo determinista (no LLM): resume qué vigilar / actuar
    a partir de los veredictos ya calculados.
    """
    items: list[dict[str, Any]] = []
    for pb in playbooks:
        v = pb.get('verdict') or {}
        st = v.get('status') or 'ok'
        if st == 'ok':
            continue
        nxt = _recommended_action(pb, st)
        items.append({
            'id': pb.get('id'),
            'title': pb.get('title'),
            'status': st,
            'label': v.get('label') or st,
            'reasons': list(v.get('reasons') or [])[:4],
            'next': {
                'action_type': nxt.get('action_type'),
                'do': nxt.get('do'),
                'when': nxt.get('when'),
                'how': nxt.get('how'),
                'approx_cost': nxt.get('approx_cost'),
            } if nxt else None,
        })

    if overall == 'act':
        summary = 'Hay al menos un recurso en ACTUAR. Revisa los pasos de abajo antes de tocar AWS.'
    elif overall == 'watch':
        summary = 'Hay señales para vigilar. Aún no obliga upgrade; revisa CloudWatch si persisten.'
    else:
        summary = 'Todo en verde según umbrales locales. No hace falta cambiar instancias hoy.'

    return {
        'level': overall,
        'needs_action': overall == 'act',
        'needs_attention': overall in ('act', 'watch'),
        'summary': summary,
        'items': items,
        'cta_path': '/admin/infra/',
        'kind': 'rules',  # no LLM
    }


NOTIFY_CACHE_KEY = 'eki_infra_advisor_last_level'
NOTIFY_COOLDOWN_KEY = 'eki_infra_advisor_last_mail_ts'
NOTIFY_COOLDOWN_SECONDS = 6 * 3600


def maybe_notify_infra_act(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Si overall pasa a 'act', avisa a staff por email (máx. 1 cada 6h).
    No envía WhatsApp. Silencioso si no hay ADMINS / email.
    """
    result = {'sent': False, 'skipped': True, 'reason': 'ok_or_watch'}
    overall = snapshot.get('overall') or 'ok'
    try:
        prev = cache.get(NOTIFY_CACHE_KEY)
    except Exception:
        prev = None

    try:
        cache.set(NOTIFY_CACHE_KEY, overall, 24 * 3600)
    except Exception:
        pass

    if overall != 'act':
        return result

    if prev == 'act':
        result['reason'] = 'still_act'
        return result

    try:
        last_ts = float(cache.get(NOTIFY_COOLDOWN_KEY) or 0)
    except Exception:
        last_ts = 0.0
    now = time.time()
    if last_ts and (now - last_ts) < NOTIFY_COOLDOWN_SECONDS:
        result['reason'] = 'cooldown'
        return result

    advisor = snapshot.get('advisor') or {}
    lines = [advisor.get('summary') or 'Infra requiere acción.', '']
    for it in advisor.get('items') or []:
        if it.get('status') != 'act':
            continue
        lines.append(f"• {it.get('title')}: {it.get('label')}")
        nxt = it.get('next') or {}
        if nxt.get('do'):
            lines.append(f"  → {nxt.get('action_type')}: {nxt.get('do')}")
        for r in (it.get('reasons') or [])[:2]:
            lines.append(f"  - {r}")
        lines.append('')
    lines.append('Panel: /admin/infra/')

    from django.conf import settings as dj_settings
    from django.core.mail import mail_admins

    recipients = getattr(dj_settings, 'ADMINS', None) or []
    extra = (getattr(dj_settings, 'INFRA_ALERT_EMAILS', '') or '').strip()
    if not recipients and not extra:
        result['reason'] = 'no_recipients'
        return result

    subject = '[eki infra] ACTUAR — revisión necesaria'
    body = '\n'.join(lines)
    try:
        if recipients:
            mail_admins(subject, body, fail_silently=True)
        if extra:
            from django.core.mail import send_mail
            send_mail(
                subject,
                body,
                getattr(dj_settings, 'DEFAULT_FROM_EMAIL', None),
                [e.strip() for e in extra.split(',') if e.strip()],
                fail_silently=True,
            )
        try:
            cache.set(NOTIFY_COOLDOWN_KEY, now, NOTIFY_COOLDOWN_SECONDS)
        except Exception:
            pass
        result = {'sent': True, 'skipped': False, 'reason': 'transition_to_act'}
    except Exception as exc:
        result = {'sent': False, 'skipped': True, 'reason': str(exc)[:120]}
    return result


def snapshot_infra(*, force: bool = False) -> dict[str, Any]:
    if not force:
        cached = _cache_get()
        if cached:
            cached = dict(cached)
            cached['cached'] = True
            return cached

    redis_s = _redis_status()
    db = _db_status()
    s3 = _s3_status()
    playbooks = _playbooks(redis_s, db, s3)

    overall = 'ok'
    for pb in playbooks:
        st = (pb.get('verdict') or {}).get('status')
        if st == 'act':
            overall = 'act'
            break
        if st == 'watch' and overall == 'ok':
            overall = 'watch'

    advisor = build_infra_advisor(playbooks, overall)

    payload = {
        'ts': time.time(),
        'cached': False,
        'overall': overall,
        'overall_label': {
            'ok': 'TODO EN VERDE — no hace falta cambiar instancias hoy',
            'watch': 'HAY SEÑALES PARA VIGILAR — aún no obliga upgrade',
            'act': 'HAY ALGO QUE REQUIERE ACCIÓN',
        }.get(overall, overall),
        'redis': redis_s,
        'db': db,
        's3': s3,
        'baseline': BASELINE,
        'capacity_limits': CAPACITY_LIMITS,
        'playbooks': playbooks,
        'advisor': advisor,
        'poll_hint_seconds': 30,
        'impact': (
            'Polling cada 30s con caché 20s es seguro para staff. '
            'El advisor es por reglas (umbrales), no un LLM. '
            'CPU de RDS/EC2 en detalle sigue en CloudWatch AWS.'
        ),
    }
    _cache_set(payload)
    return payload


HEADER_HEALTH_CACHE_KEY = 'eki_header_health_v2'
HEADER_HEALTH_CACHE_SECONDS = 25


def _celery_workers_ok() -> dict[str, Any]:
    """Ping corto a workers; eager = ok en local/tests."""
    out: dict[str, Any] = {'ok': False, 'mode': 'unknown'}
    try:
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            out['ok'] = True
            out['mode'] = 'eager'
            return out
        from mvp_project.celery import app as celery_app

        insp = celery_app.control.inspect(timeout=0.35)
        pong = insp.ping() if insp is not None else None
        out['ok'] = bool(pong)
        out['mode'] = 'workers' if pong else 'no_workers'
        if pong:
            out['workers'] = len(pong)
    except Exception as exc:
        out['error'] = str(exc)[:80]
    return out


def _meta_configured() -> dict[str, Any]:
    token = (getattr(settings, 'WHATSAPP_TOKEN', None) or '').strip()
    phone = (getattr(settings, 'WHATSAPP_PHONE_ID', None) or '').strip()
    ok = bool(token and phone)
    return {
        'ok': ok,
        'hint': 'Token + Phone ID Meta' if ok else 'Falta WHATSAPP_TOKEN o WHATSAPP_PHONE_ID',
    }


def _whatsapp_configured() -> dict[str, Any]:
    sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip()
    token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
    number = (
        (getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None) or '')
        or (getattr(settings, 'TWILIO_PHONE_NUMBER', None) or '')
    ).strip()
    ok = bool(sid and token and number)
    return {
        'ok': ok,
        'hint': 'Twilio WhatsApp listo' if ok else 'Falta SID, token o número Twilio',
    }


def header_health_strip(*, force: bool = False) -> list[dict[str, Any]]:
    """Chips ligeros para la barra Unfold: WhatsApp, Celery, Redis, S3, PostgreSQL.

    Meta Cloud API queda fuera del strip hasta que haya credenciales/probe estables
    (evita rojo permanente en nav cuando Twilio es el canal activo).
    """
    if not force:
        try:
            cached = cache.get(HEADER_HEALTH_CACHE_KEY)
            if cached:
                return cached
        except Exception:
            pass

    snap = snapshot_infra(force=False)
    redis_ok = bool((snap.get('redis') or {}).get('ok'))
    db_ok = bool((snap.get('db') or {}).get('ok'))
    s3_ok = bool((snap.get('s3') or {}).get('ok'))
    celery = _celery_workers_ok()
    wa = _whatsapp_configured()

    chips = [
        {
            'id': 'whatsapp',
            'label': 'WhatsApp',
            'ok': wa['ok'],
            'hint': wa['hint'],
        },
        {
            'id': 'celery',
            'label': 'Celery',
            'ok': celery['ok'],
            'hint': (
                f"Celery {celery.get('mode', '')}"
                + (f" ({celery.get('workers')} workers)" if celery.get('workers') else '')
            ).strip(),
        },
        {
            'id': 'redis',
            'label': 'Redis',
            'ok': redis_ok,
            'hint': 'Redis OK' if redis_ok else 'Redis no responde',
        },
        {
            'id': 's3',
            'label': 'S3',
            'ok': s3_ok,
            'hint': 'S3 OK' if s3_ok else 'S3 no responde',
        },
        {
            'id': 'postgres',
            'label': 'PostgreSQL',
            'ok': db_ok,
            'hint': 'PostgreSQL OK' if db_ok else 'Base de datos no responde',
        },
    ]
    try:
        cache.set(HEADER_HEALTH_CACHE_KEY, chips, HEADER_HEALTH_CACHE_SECONDS)
    except Exception:
        pass
    return chips
