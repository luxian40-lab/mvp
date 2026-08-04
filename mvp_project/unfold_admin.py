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


def environment_callback(request):
    """Badge esquina superior (estilo demo Unfold)."""
    return ["PRODUCCIÓN", "danger"]


UNFOLD = {
    "SITE_TITLE": "eki",
    "SITE_HEADER": "eki",
    "SITE_SUBHEADER": "Panel de operaciones",
    "SITE_SYMBOL": "school",
    "SITE_ICON": {
        "light": lambda request: static("favicons/admin-32.png"),
        "dark": lambda request: static("favicons/admin-32.png"),
    },
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_BACK_BUTTON": True,
    # Sin THEME forzado → switcher light/dark/auto (sidebar usuario + barra superior vía userlinks override).
    # Paletas/COLORS = branding eki en código; no hay skins Jazzmin.
    "BORDER_RADIUS": "12px",
    "ENVIRONMENT": "mvp_project.unfold_admin.environment_callback",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "type": "image/svg+xml",
            "href": lambda request: static("favicons/admin.svg"),
        },
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/png",
            "href": lambda request: static("favicons/admin-32.png"),
        },
        {
            "rel": "icon",
            "sizes": "48x48",
            "type": "image/png",
            "href": lambda request: static("favicons/admin-48.png"),
        },
        {
            "rel": "icon",
            "type": "image/png",
            "href": lambda request: static("favicons/admin.png"),
        },
        {
            "rel": "apple-touch-icon",
            "sizes": "180x180",
            "href": lambda request: static("favicons/admin-180.png"),
        },
    ],
    # Dropdown marca (esquina superior): atajos ops. Apariencia light/dark/auto = switcher nativo Unfold.
    "SITE_DROPDOWN": [
        {
            "icon": "home",
            "title": _("Inicio"),
            "link": reverse_lazy("admin:index"),
        },
        {
            "icon": "dashboard",
            "title": _("Dashboard"),
            "link": "/admin/dashboard/",
        },
        {
            "icon": "trending_up",
            "title": _("Centro de Éxito"),
            "link": "/admin/dashboard/?tab=retencion",
        },
        {
            "icon": "school",
            "title": _("Cursos"),
            "link": reverse_lazy("admin:core_curso_changelist"),
        },
        {
            "icon": "campaign",
            "title": _("Campañas"),
            "link": reverse_lazy("admin:core_campana_changelist"),
        },
        {
            "icon": "storefront",
            "title": _("Studio (vitrina)"),
            "link": "https://studio.eki.technology/studio/",
            "attrs": {"target": "_blank"},
        },
        {
            "icon": "menu_book",
            "title": _("Aprende (aula)"),
            "link": "https://aprende.eki.technology/aprende/",
            "attrs": {"target": "_blank"},
        },
        {
            "icon": "help",
            "title": _("Manual"),
            "link": "/admin/instrucciones/",
        },
    ],
    "STYLES": [_eki_admin_styles],
    "COLORS": {
        # base un poco más gris → las cajas blancas se leen (antes casi se fundían).
        "base": {
            "50": "#f0eef3",
            "100": "#e8e4ef",
            "200": "#d9d3e3",
            "300": "#c4bbd0",
            "400": "#9a8eaa",
            "500": "#6f647c",
            "600": "#52485c",
            "700": "#3a3344",
            "800": "#2a2433",
            "900": "#1c1822",
            "950": "#110e16",
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
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-700)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
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
