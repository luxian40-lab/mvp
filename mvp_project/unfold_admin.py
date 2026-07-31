"""Configuración Unfold (admin eki). Importado desde settings.py.

Porta la experiencia que teníamos en Jazzmin a Unfold:
- Modelos viven en aplicaciones Django (`show_all_applications`).
- Atajos custom (Panel GEI, Bot, Ajustar avance…) van agrupados por la misma app.
- Alta = botón «Añadir» en cada listado (no ítems «Nuevo…» en el menú).
No es un clon visual de Jazzmin: es el mismo mapa mental en el shell Unfold.
"""

from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


def _eki_admin_styles(request):
    return static("admin/css/eki_admin_unfold.css")


UNFOLD = {
    "SITE_TITLE": "eki",
    "SITE_HEADER": "eki",
    "SITE_SUBHEADER": "Panel de operaciones",
    "SITE_SYMBOL": "school",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "BORDER_RADIUS": "0.5rem",
    "STYLES": [_eki_admin_styles],
    "COLORS": {
        "base": {
            "50": "#faf9fb",
            "100": "#f7f5f9",
            "200": "#ebe7f0",
            "300": "#d4cde0",
            "400": "#a89bb8",
            "500": "#7a6d88",
            "600": "#5a4f68",
            "700": "#3f3649",
            "800": "#2a1f33",
            "900": "#1a1625",
            "950": "#120e18",
        },
        "primary": {
            "50": "#f8f4fa",
            "100": "#f0e8f4",
            "200": "#e0d0e8",
            "300": "#c9aed4",
            "400": "#b08cbe",
            "500": "#9A6CAC",
            "600": "#7a4e8e",
            "700": "#5F3A6E",
            "800": "#4a2d56",
            "900": "#3a2344",
            "950": "#24162b",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "command_search": True,
        # Catálogo de apps/modelos (equivalente al sidebar Jazzmin por app).
        "show_all_applications": True,
        "navigation": [
            # Antes: topmenu Jazzmin (Inicio, Dashboard, Centro de Éxito…).
            {
                "title": _("Operación"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Inicio"),
                        "icon": "home",
                        "link": reverse_lazy("admin:index"),
                    },
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": "/admin/dashboard/",
                    },
                    {
                        "title": _("Centro de Éxito"),
                        "icon": "trending_up",
                        "link": "/admin/dashboard/?tab=retencion",
                    },
                    {
                        "title": _("Manual"),
                        "icon": "help",
                        "link": "/admin/instrucciones/",
                    },
                ],
            },
            # custom_links → core
            {
                "title": _("Core (atajos)"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Ajustar avance"),
                        "icon": "tune",
                        "link": "/admin/ajustar-avance/",
                    },
                    {
                        "title": _("Cobertura"),
                        "icon": "map",
                        "link": "/admin/cobertura/",
                    },
                    {
                        "title": _("Envío certificados"),
                        "icon": "verified",
                        "link": "/admin/envio-certificados/",
                    },
                ],
            },
            # custom_links → agents_commercial
            {
                "title": _("Comercial / Nat"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Bot comercial"),
                        "icon": "smart_toy",
                        "link": "/admin/bot-comercial/",
                    },
                    {
                        "title": _("Knowledge Studio"),
                        "icon": "lightbulb",
                        "link": "/admin/knowledge-studio/",
                    },
                ],
            },
            # custom_links → analytics
            {
                "title": _("Analytics / Infra"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("AI Ops"),
                        "icon": "memory",
                        "link": "/admin/ai-ops/eventos/",
                    },
                    {
                        "title": _("Infra"),
                        "icon": "monitor_heart",
                        "link": "/admin/infra/",
                    },
                ],
            },
            # custom_links → agents_edu + formulario + aprende
            {
                "title": _("GEI / Aula / IA"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Panel GEI"),
                        "icon": "eco",
                        "link": "/admin/gei/panel/",
                    },
                    {
                        "title": _("Crear curso IA"),
                        "icon": "auto_awesome",
                        "link": "/admin/crear-curso-ia/",
                    },
                    {
                        "title": _("Aula web"),
                        "icon": "laptop",
                        "link": "/admin/aula-web/",
                    },
                ],
            },
        ],
    },
}
