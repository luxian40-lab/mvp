"""Tags de admin eki (Unfold header / hub)."""
from __future__ import annotations

from django import template
from django.utils import timezone

register = template.Library()

# Saludos formales por franja horaria (hora local). Tono empresa.
_SALUDO_MANANA = "Buenos días, {nombre}"
_SALUDO_TARDE = "Buenas tardes, {nombre}"
_SALUDO_NOCHE = "Buenas noches, {nombre}"

# Líneas operativas bajo el saludo (corporativas; estables por día).
_FRASES_OPS = (
    "Panel de operaciones eki.",
    "Priorice entregas, retención y soporte.",
    "Datos listos para decisión operativa.",
    "WhatsApp, aula y Nat en un solo hub.",
)


def _hora_local() -> int:
    try:
        return timezone.localtime().hour
    except Exception:
        return timezone.now().hour


def saludo_por_hora(nombre: str, hour: int | None = None) -> str:
    """Saludo formal según hora (0–23). Exportado para tests."""
    h = _hora_local() if hour is None else int(hour)
    if 5 <= h < 12:
        plantilla = _SALUDO_MANANA
    elif 12 <= h < 19:
        plantilla = _SALUDO_TARDE
    else:
        plantilla = _SALUDO_NOCHE
    return plantilla.format(nombre=(nombre or "equipo").strip() or "equipo")


@register.simple_tag(takes_context=True)
def eki_admin_saludo(context) -> str:
    """Saludo formal por hora local + nombre del staff."""
    request = context.get("request")
    user = getattr(request, "user", None) if request else None
    nombre = "equipo"
    if user and getattr(user, "is_authenticated", False):
        nombre = (
            (user.first_name or "").strip()
            or (user.get_username() or "").strip()
            or "equipo"
        )
    return saludo_por_hora(nombre)


@register.simple_tag
def eki_admin_frase_motivadora() -> str:
    """Línea operativa bajo el saludo (tono empresa; estable por día)."""
    try:
        day = timezone.localtime().timetuple().tm_yday
    except Exception:
        day = timezone.now().timetuple().tm_yday
    return _FRASES_OPS[day % len(_FRASES_OPS)]


_MESES_ES = (
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


@register.simple_tag
def eki_fecha_hoy() -> str:
    """Fecha larga en español para el chip de calendario del hub."""
    try:
        now = timezone.localtime()
    except Exception:
        now = timezone.now()
    return f"{now.day} de {_MESES_ES[now.month]} de {now.year}"


@register.simple_tag
def eki_panel_snap():
    """Snapshot del Panel ejecutivo para Inicio (/admin/)."""
    from core.views_admin_panel import build_panel_snapshot

    return build_panel_snapshot()


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


@register.inclusion_tag("admin/partials/eki_ops_bell.html", takes_context=True)
def eki_ops_bell(context):
    """Campanita: campañas programadas pendientes (próximas 7 días)."""
    from datetime import timedelta

    n = 0
    try:
        from core.models import Campana

        ahora = timezone.now()
        n = Campana.objects.filter(
            ejecutada=False,
            fecha_programada__isnull=False,
            fecha_programada__gte=ahora,
            fecha_programada__lte=ahora + timedelta(days=7),
        ).count()
    except Exception:
        n = 0
    return {
        "pendientes": n,
        "calendario_url": "/admin/calendario/",
        "push_url": "/admin/push-estudiantes/",
    }
