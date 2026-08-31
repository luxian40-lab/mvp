"""Costos Course Engine en nav admin — módulos publicados con media IA."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_KEY = 'eki_course_engine_published_costs_v1'
_CACHE_TTL = 900
_RUN_ID_RE = re.compile(r'course_engine/videos/([a-f0-9]{8,16})\.mp4', re.I)


@dataclass(frozen=True)
class PublishedCourseEngineCosts:
    n_modulos: int
    n_con_media: int
    total_usd: float
    medidos_usd: float
    estimados_usd: float
    n_medidos: int
    n_estimados: int


def course_engine_costs_badge() -> tuple[str, str, PublishedCourseEngineCosts]:
    """Texto + tono para chip nav; cacheado 15 min."""
    cached = cache.get(_CACHE_KEY)
    if isinstance(cached, tuple) and len(cached) == 3:
        return cached[0], cached[1], cached[2]

    snap = _compute()
    if snap.n_con_media == 0:
        texto = 'IA cursos $0 · 0 mód. IA'
        tono = 'info'
    elif snap.n_estimados and not snap.n_medidos:
        texto = f'IA cursos ~${snap.total_usd:.2f} · {snap.n_con_media} mód.'
        tono = 'warning'
    elif snap.n_estimados:
        texto = (
            f'IA cursos ${snap.total_usd:.2f} · {snap.n_con_media} mód.'
            f' ({snap.n_medidos} medidos)'
        )
        tono = 'info'
    else:
        texto = f'IA cursos ${snap.total_usd:.2f} · {snap.n_con_media} mód.'
        tono = 'info'

    if snap.total_usd >= 25:
        tono = 'warning'
    if snap.total_usd >= 50:
        tono = 'danger'

    result = (texto, tono, snap)
    cache.set(_CACHE_KEY, result, _CACHE_TTL)
    return result


def _compute() -> PublishedCourseEngineCosts:
    from core.models import Modulo, PasoModulo

    publicados = Modulo.objects.filter(publicado_wa=True).select_related('curso')
    n_modulos = publicados.count()
    if n_modulos == 0:
        return PublishedCourseEngineCosts(0, 0, 0.0, 0.0, 0.0, 0, 0)

    pasos = PasoModulo.objects.filter(
        activo=True,
        modulo__publicado_wa=True,
        media_url__icontains='course_engine',
    ).select_related('modulo', 'modulo__curso')

    modulo_ids: set[int] = set()
    run_by_modulo: dict[int, str] = {}
    for paso in pasos:
        mid = paso.modulo_id
        modulo_ids.add(mid)
        rid = _run_id_from_url(paso.media_url or '')
        if rid and mid not in run_by_modulo:
            run_by_modulo[mid] = rid

    total = 0.0
    medidos = 0.0
    estimados = 0.0
    n_medidos = 0
    n_estimados = 0

    for mid in modulo_ids:
        run_id = run_by_modulo.get(mid)
        real = _manifest_cost(run_id) if run_id else None
        if real is not None:
            total += real
            medidos += real
            n_medidos += 1
        else:
            est = _estimate_modulo_cost(mid, pasos)
            total += est
            estimados += est
            n_estimados += 1

    return PublishedCourseEngineCosts(
        n_modulos=n_modulos,
        n_con_media=len(modulo_ids),
        total_usd=round(total, 2),
        medidos_usd=round(medidos, 2),
        estimados_usd=round(estimados, 2),
        n_medidos=n_medidos,
        n_estimados=n_estimados,
    )


def _run_id_from_url(url: str) -> str | None:
    m = _RUN_ID_RE.search(url or '')
    return m.group(1) if m else None


def _manifest_cost(run_id: str | None) -> float | None:
    if not run_id:
        return None
    try:
        from core.course_engine.local_store import local_runs_root

        path = local_runs_root() / run_id / 'bundle_manifest.json'
        if path.is_file():
            data = json.loads(path.read_text(encoding='utf-8'))
            raw = data.get('costo_real_usd')
            if raw is not None:
                return float(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        logger.debug('manifest costo no leido run=%s', run_id, exc_info=True)
    return None


def _estimate_modulo_cost(modulo_id: int, pasos) -> float:
    from core.course_engine.bundle import estimar_costo_modulo_mixto
    from core.course_engine.format_config import plan_desde_curso

    modulo = next((p.modulo for p in pasos if p.modulo_id == modulo_id), None)
    if not modulo or not modulo.curso:
        return 0.35
    tier = modulo.get_course_engine_tier()
    plan = plan_desde_curso(modulo.curso, tier_override=tier)
    return estimar_costo_modulo_mixto(plan).total_usd
