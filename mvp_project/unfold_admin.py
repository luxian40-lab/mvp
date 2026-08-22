"""Configuración Unfold (admin eki). Importado desde settings.py.

Porta la experiencia que teníamos en Jazzmin a Unfold:
- Modelos viven en aplicaciones Django (`show_all_applications`).
- Atajos custom (Panel GEI, Bot, Ajustar avance…) van agrupados por la misma app.
- Alta = botón «Añadir» en cada listado (no ítems «Nuevo…» en el menú).
No es un clon visual de Jazzmin: es el mismo mapa mental en el shell Unfold.
"""

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from mvp_project.static_safe import static_safe


def _eki_admin_styles(request):
    return static_safe("admin/css/eki_admin_unfold.css")


def _eki_admin_tones_styles(request):
    return static_safe("admin/css/eki_admin_tones.css")


def _eki_eco_graph_script(request):
    return static_safe("admin/js/eki_eco_graph.js")


def _eki_admin_tones_script(request):
    return static_safe("admin/js/eki_admin_tones.js")


def _eki_copiloto_script(request):
    return static_safe("admin/js/eki_copiloto_chat.js")


def environment_callback(request):
    """Badge esquina superior: saldo Twilio (cache 15 min) o PRODUCCIÓN."""
    from core.twilio_balance import twilio_balance_badge

    texto, tono = twilio_balance_badge()
    return [texto, tono]


UNFOLD = {
    "SITE_TITLE": "eki",
    "SITE_HEADER": "eki",
    "SITE_SUBHEADER": "Panel de operaciones",
    "SITE_SYMBOL": "",
    "SITE_ICON": {
        "light": lambda request: static_safe("favicons/admin-32.png"),
        "dark": lambda request: static_safe("favicons/admin-32.png"),
    },
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_BACK_BUTTON": True,
    # Sin THEME forzado → switcher light/dark/auto (sidebar usuario + barra superior vía userlinks override).
    # Paletas/COLORS = branding eki en código; no hay skins Jazzmin.
    "BORDER_RADIUS": "12px",
    "ENVIRONMENT": "mvp_project.unfold_admin.environment_callback",
    "DASHBOARD_CALLBACK": "core.views_admin_panel.unfold_dashboard_callback",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/png",
            "href": lambda request: static_safe("favicons/admin-32.png"),
        },
        {
            "rel": "icon",
            "sizes": "48x48",
            "type": "image/png",
            "href": lambda request: static_safe("favicons/admin-48.png"),
        },
        {
            "rel": "icon",
            "type": "image/png",
            "href": lambda request: static_safe("favicons/admin.png"),
        },
        {
            "rel": "apple-touch-icon",
            "sizes": "180x180",
            "href": lambda request: static_safe("favicons/admin-180.png"),
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
            "icon": "analytics",
            "title": _("Analítica"),
            "link": "/admin/dashboard/",
        },
        {
            "icon": "trending_up",
            "title": _("Centro de Éxito"),
            "link": "/admin/dashboard/?tab=retencion",
        },
        {
            "icon": "forum",
            "title": _("Conversaciones"),
            "link": "/admin/conversaciones/",
        },
        {
            "icon": "school",
            "title": _("Cursos"),
            "link": reverse_lazy("admin:core_curso_changelist"),
        },
        {
            "icon": "add_circle",
            "title": _("Curso nuevo"),
            "link": "/admin/curso-nuevo/",
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
    "STYLES": [_eki_admin_styles, _eki_admin_tones_styles],
    "SCRIPTS": [_eki_eco_graph_script, _eki_admin_tones_script, _eki_copiloto_script],
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
    "COMMAND": {
        "search_callback": "core.admin_command_search.eki_command_search_callback",
        # Lista acotada (callback): True escaneaba todo el admin y podía 500 en Aprende.
        "search_models": "core.admin_command_search.eki_searchable_models",
        "show_history": True,
    },
    "SIDEBAR": {
        "show_search": True,
        "command_search": True,
        # Catálogo de apps/modelos (equivalente al sidebar Jazzmin por app).
        "show_all_applications": True,
        "navigation": [
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
                        "title": _("Manual"),
                        "icon": "menu_book",
                        "link": "/admin/instrucciones/",
                    },
                    {
                        "title": _("Analítica"),
                        "icon": "analytics",
                        "link": "/admin/dashboard/",
                    },
                    {
                        "title": _("Conversaciones"),
                        "icon": "forum",
                        "link": "/admin/conversaciones/",
                    },
                ],
            },
            {
                "title": _("Captar"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Clientes"),
                        "icon": "apartment",
                        "link": reverse_lazy("admin:core_cliente_changelist"),
                    },
                    {
                        "title": _("Bot comercial / Nat"),
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
            {
                "title": _("Enseñar"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Cursos"),
                        "icon": "school",
                        "link": reverse_lazy("admin:core_curso_changelist"),
                    },
                    {
                        "title": _("Módulos"),
                        "icon": "view_timeline",
                        "link": reverse_lazy("admin:core_modulo_changelist"),
                    },
                    {
                        "title": _("Campañas"),
                        "icon": "campaign",
                        "link": reverse_lazy("admin:core_campana_changelist"),
                    },
                    {
                        "title": _("Calendario campañas"),
                        "icon": "event",
                        "link": "/admin/calendario/",
                    },
                    {
                        "title": _("Push recordatorios"),
                        "icon": "notifications_active",
                        "link": "/admin/push-estudiantes/",
                    },
                ],
            },
            {
                "title": _("Retener"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Estudiantes"),
                        "icon": "group",
                        "link": reverse_lazy("admin:core_estudiante_changelist"),
                    },
                    {
                        "title": _("Centro de Éxito"),
                        "icon": "trending_up",
                        "link": "/admin/dashboard/?tab=retencion",
                    },
                    {
                        "title": _("Envío certificados"),
                        "icon": "verified",
                        "link": "/admin/envio-certificados/",
                    },
                    {
                        "title": _("WhatsappLog"),
                        "icon": "history",
                        "link": reverse_lazy("admin:core_whatsapplog_changelist"),
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
                        "title": _("Mensajes push (CRUD)"),
                        "icon": "campaign",
                        "link": reverse_lazy("admin:core_mensajepush_changelist"),
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
                        "title": _("Curso nuevo"),
                        "icon": "add_circle",
                        "link": "/admin/curso-nuevo/",
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
