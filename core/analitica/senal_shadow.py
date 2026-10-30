"""Shadow pipeline: clasifica Nat → SenalTerritorial sin afectar la respuesta WA."""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def senal_clasificador_enabled() -> bool:
    return bool(getattr(settings, 'SENAL_CLASIFICADOR_ENABLED', True))


def senal_persistir_enabled() -> bool:
    """Aunque esté en sombra, podemos persistir señales internas."""
    return bool(getattr(settings, 'SENAL_PERSISTIR_SENALES', True))


def procesar_senal_shadow_nat(
    *,
    texto: str,
    telefono: str = '',
    cliente=None,
    estudiante=None,
    ctx_agro=None,
) -> Any | None:
    """
    Clasifica y, si hay tipo + territory_id, registra señal.
    Nunca lanza hacia el webhook. No envía WhatsApp.
    """
    if not senal_clasificador_enabled():
        return None
    try:
        from core.clasificador_senales import clasificar_consulta_territorial
        from core.event_engine import registrar_senal_territorial
        from core.territorio import obtener_territory_id_estudiante, resolver_territorio

        ctx = {}
        if ctx_agro is not None:
            try:
                ctx = ctx_agro.to_dict() if hasattr(ctx_agro, 'to_dict') else dict(ctx_agro or {})
            except Exception:
                ctx = {}

        clasif = clasificar_consulta_territorial(texto, contexto=ctx)
        if not clasif.tipo:
            logger.debug(
                'senal_shadow skip motivo=%s tel=%s',
                clasif.motivo,
                (telefono or '')[-4:],
            )
            return None

        tid = ''
        if estudiante is not None:
            tid = obtener_territory_id_estudiante(estudiante, persistir=True)
        if not tid:
            mun = (ctx.get('municipio') or ctx.get('region') or '').strip()
            if mun:
                ubic = resolver_territorio(mun, ctx.get('departamento') or '')
                tid = (ubic.territory_id or '').strip()

        if not tid:
            logger.info(
                'senal_shadow sin territory_id tipo=%s tel=%s',
                clasif.tipo,
                (telefono or '')[-4:],
            )
            return None

        if not senal_persistir_enabled():
            logger.info(
                'senal_shadow dry tipo=%s tid=%s conf=%.2f',
                clasif.tipo,
                tid,
                clasif.confianza,
            )
            return None

        org_id = getattr(cliente, 'pk', None) if cliente is not None else None
        actor_id = getattr(estudiante, 'pk', None) if estudiante is not None else None
        senal = registrar_senal_territorial(
            tipo=clasif.tipo,
            territory_id=tid,
            org_id=org_id,
            confianza=clasif.confianza,
            fuente='shadow_rules_v0',
            metadata={
                'metodo': clasif.metodo,
                'motivo': clasif.motivo,
                'familia': clasif.familia,
                'shadow': True,
                'preview': (texto or '')[:160],
            },
            actor_id=actor_id,
        )
        logger.info(
            'senal_shadow ok tipo=%s tid=%s id=%s',
            clasif.tipo,
            tid,
            getattr(senal, 'pk', None),
        )
        return senal
    except Exception:
        logger.exception('senal_shadow error')
        return None
