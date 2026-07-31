"""Tags de admin eki (Unfold header / hub)."""
from __future__ import annotations

from django import template
from django.utils import timezone

register = template.Library()


@register.simple_tag(takes_context=True)
def eki_admin_saludo(context) -> str:
    """Buenos días / tardes / noches + primer nombre del staff."""
    request = context.get("request")
    user = getattr(request, "user", None) if request else None
    nombre = ""
    if user and getattr(user, "is_authenticated", False):
        nombre = (user.first_name or "").strip() or (user.get_username() or "").strip()
    try:
        now = timezone.localtime()
    except Exception:
        now = timezone.now()
    h = now.hour
    if h < 12:
        franja = "Buenos días"
    elif h < 19:
        franja = "Buenas tardes"
    else:
        franja = "Buenas noches"
    if nombre:
        return f"{franja}, {nombre}"
    return franja


@register.inclusion_tag("admin/partials/eki_health_strip.html", takes_context=True)
def eki_health_strip(context):
    """Chips de salud en la barra superior Unfold."""
    from core.infra_monitor import header_health_strip

    chips = []
    try:
        chips = header_health_strip()
    except Exception:
        chips = []
    return {"chips": chips, "infra_url": "/admin/infra/"}
