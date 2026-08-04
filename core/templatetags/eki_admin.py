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
    "Cada listo en el campo es un paso hacia el territorio que soñamos.",
    "La claridad operativa es el mejor regalo para el productor.",
    "Pequeños envíos, gran confianza: WhatsApp primero.",
    "Medir sin inventar: datos honestos, decisiones firmes.",
    "Hoy alguien en Latam rural puede avanzar gracias a eki.",
    "Retener es acompañar; acompañar es escuchar.",
    "Un certificado bien hecho abre puertas reales.",
    "Nat vende con verdad; el curso forma con cuidado.",
    "El ecosistema eki crece cuando el equipo respira.",
    "Menos ruido en el admin, más impacto en la finca.",
    "La telemetría cuenta historias; tú decides el final.",
    "Un módulo corto llega más lejos que un manual largo.",
    "Infra estable = estudiantes que no se quedan a medias.",
    "El mapa de abandono apunta el camino; tú das el empujón.",
    "Diseño limpio: menos scroll, más acción.",
    "Soberanía de datos empieza con buen orden hoy.",
    "Cada campaña con plantilla es respeto al canal.",
    "Aprende y campo son un mismo viaje con dos puertas.",
    "Cuando dudas, prioriza al estudiante en 3G.",
    "Tu trabajo silencioso sostiene la voz de eki.",
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
