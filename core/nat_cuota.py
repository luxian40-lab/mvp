"""Cuota diaria de preguntas Nat (por teléfono) — sin LLM al agotar."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def max_preguntas_nat_dia() -> int:
    try:
        n = int(getattr(settings, 'BOT_COMERCIAL_MAX_PREGUNTAS_DIA', 40) or 0)
    except (TypeError, ValueError):
        n = 40
    return max(0, n)


def evaluar_cuota_nat(telefono: str) -> tuple[bool, int, int]:
    """
    Returns (excedida, usados_24h, max_permitidos).
    max=0 → cuota desactivada (nunca excedida).
    """
    max_q = max_preguntas_nat_dia()
    if max_q <= 0:
        return False, 0, 0

    from core.models import WhatsappLog
    from core.utils_telefono import normalizar_telefono, variantes_telefono

    tel = normalizar_telefono(telefono or '')
    if not tel:
        return False, 0, max_q

    variantes = set(variantes_telefono(tel))
    variantes.add(tel)
    desde = timezone.now() - timedelta(hours=24)
    usados = WhatsappLog.objects.filter(
        telefono__in=variantes,
        tipo='INCOMING',
        agente_usado='BOT_COMERCIAL',
        fecha__gte=desde,
    ).count()
    return usados > max_q, usados, max_q


def mensaje_cuota_agotada(*, usados: int, max_q: int) -> str:
    custom = (getattr(settings, 'BOT_COMERCIAL_CUOTA_MSG', '') or '').strip()
    if custom:
        return custom.replace('{max}', str(max_q)).replace('{usados}', str(usados))
    return (
        f"Has alcanzado el límite de *{max_q} consultas* con Nat en las últimas 24 horas "
        f"(vas {usados}).\n\n"
        "Mañana podrás seguir consultando. "
        "Si es urgente, escribe *menu* y elige *Cursos*, o contacta a tu organización eki."
    )
