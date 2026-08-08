"""Tags de admin eki (Unfold header / hub)."""
from __future__ import annotations

import random

from django import template
from django.utils import timezone

register = template.Library()

# ≥20 saludos (rotan en cada carga / hard refresh).
_SALUDOS = (
    "Buenos días, {nombre}",
    "Qué bueno verte, {nombre}",
    "Listos para operar, {nombre}",
    "Hoy el campo cuenta contigo, {nombre}",
    "Arrancamos con energía, {nombre}",
    "Bienvenida al hub, {nombre}",
    "Bienvenido al hub, {nombre}",
    "Tu panel está al día, {nombre}",
    "Vamos paso a paso, {nombre}",
    "Buenas tardes, {nombre}",
    "La operación te espera, {nombre}",
    "Un café y a medir impacto, {nombre}",
    "Hola {nombre}, el ecosistema está vivo",
    "Buenas noches, {nombre}",
    "Cierre con claridad, {nombre}",
    "Seguimos cerca del productor, {nombre}",
    "Hoy sumamos retención, {nombre}",
    "Nat y el aula te saludan, {nombre}",
    "Enfoque rural, mirada Latam — {nombre}",
    "Gracias por cuidar eki, {nombre}",
    "Otra ronda de aprendizaje, {nombre}",
    "Que el WhatsApp fluya hoy, {nombre}",
    "Métricas honestas, {nombre}",
    "Listo para el siguiente módulo, {nombre}",
)

_FRASES_MOTIVADORAS = (
    "El progreso se construye un paso a la vez.",
    "Hecho es mejor que perfecto: empieza y ajusta.",
    "La constancia vence al talento cuando el talento no es constante.",
    "Enfócate en lo que sí depende de ti hoy.",
    "Las grandes metas se logran con pequeñas acciones diarias.",
    "Un buen comienzo ya es media tarea resuelta.",
    "La disciplina es el puente entre las metas y los logros.",
    "Ordena tu día y el día trabajará a tu favor.",
    "Cada problema trae escondida una oportunidad.",
    "El esfuerzo de hoy es la tranquilidad de mañana.",
    "No cuentes los días; haz que los días cuenten.",
    "Lo importante no es la velocidad, sino no detenerse.",
    "La calidad nace del cuidado en los detalles.",
    "Rodéate de buenas ideas y ejecútalas con calma.",
    "Los equipos que se apoyan llegan más lejos.",
    "Respira, prioriza y avanza con claridad.",
    "El mejor momento para empezar es ahora.",
    "Aprende algo nuevo cada día y multiplícalo.",
    "La actitud correcta convierte el trabajo en logro.",
    "Celebra los pequeños avances: suman al gran resultado.",
)


@register.simple_tag(takes_context=True)
def eki_admin_saludo(context) -> str:
    """Saludo rotativo (≥20 variantes) + nombre del staff."""
    request = context.get("request")
    user = getattr(request, "user", None) if request else None
    nombre = "equipo"
    if user and getattr(user, "is_authenticated", False):
        nombre = (user.first_name or "").strip() or (user.get_username() or "").strip() or "equipo"
    plantilla = random.choice(_SALUDOS)
    return plantilla.format(nombre=nombre)


@register.simple_tag
def eki_admin_frase_motivadora() -> str:
    """Frase motivadora distinta en cada carga del Inicio."""
    return random.choice(_FRASES_MOTIVADORAS)


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

    from django.utils import timezone

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
