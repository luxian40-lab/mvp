"""Resolución de broker Redis/Celery para EB (ElastiCache vs Redis local).

Función pura para poder testear sin recargar Django settings.
"""
from __future__ import annotations


LOCAL_REDIS_URL = 'redis://127.0.0.1:6379/0'


def env_truthy_local_redis(raw: str | None, default: str = '1') -> bool:
    """USE_LOCAL_REDIS: default True. 0/false/no/off → False."""
    val = (raw if raw is not None else default).strip().lower()
    return val not in ('0', 'false', 'no', 'off')


def is_external_redis_url(url: str) -> bool:
    u = (url or '').strip()
    if not u:
        return False
    if u.startswith('redis://127.0.0.1') or u.startswith('redis://localhost'):
        return False
    return u.startswith('redis://') or u.startswith('rediss://')


def resolve_eb_celery_redis(
    *,
    broker_env: str,
    result_backend_env: str = '',
    use_local_redis: bool = True,
    on_elastic_beanstalk: bool = True,
    default_local: str = LOCAL_REDIS_URL,
) -> tuple[str, str, str]:
    """
    Devuelve (broker_url, result_backend, mode).

    mode:
      - 'external'  → ElastiCache / Redis gestionado
      - 'local'     → Redis en la caja EB (comportamiento histórico)
      - 'unchanged' → no estamos en EB; el caller no debe sobrescribir
    """
    if not on_elastic_beanstalk:
        return ('', '', 'unchanged')

    broker = (broker_env or '').strip()
    backend = (result_backend_env or '').strip()

    if broker and is_external_redis_url(broker):
        return (broker, backend or broker, 'external')

    if broker and not is_external_redis_url(broker):
        # Explicit local URL in env
        return (broker, backend or broker, 'local')

    # Sin broker en env: siempre preferir local si está permitido.
    # Si USE_LOCAL_REDIS=0 sin URL externa → fallback local (no dejar Celery sin broker).
    if use_local_redis or not broker:
        return (default_local, backend or default_local, 'local')

    return (default_local, backend or default_local, 'local')
