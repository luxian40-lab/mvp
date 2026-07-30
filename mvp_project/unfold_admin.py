"""Configuración Unfold (admin eki). Importado desde settings.py."""

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
    "STYLES": [_eki_admin_styles],
    "COLORS": {
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
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Operaciones"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Inicio admin"),
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
                        "title": _("Clientes"),
                        "icon": "apartment",
                        "link": reverse_lazy("admin:core_cliente_changelist"),
                    },
                    {
                        "title": _("Nuevo cliente"),
                        "icon": "add_business",
                        "link": reverse_lazy("admin:core_cliente_add"),
                    },
                    {
                        "title": _("Cursos"),
                        "icon": "menu_book",
                        "link": reverse_lazy("admin:core_curso_changelist"),
                    },
                    {
                        "title": _("Nuevo curso"),
                        "icon": "post_add",
                        "link": reverse_lazy("admin:core_curso_add"),
                    },
                    {
                        "title": _("Módulos"),
                        "icon": "layers",
                        "link": reverse_lazy("admin:core_modulo_changelist"),
                    },
                    {
                        "title": _("Nuevo módulo"),
                        "icon": "note_add",
                        "link": reverse_lazy("admin:core_modulo_add"),
                    },
                    {
                        "title": _("Estudiantes"),
                        "icon": "people",
                        "link": reverse_lazy("admin:core_estudiante_changelist"),
                    },
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
                        "title": _("Infra"),
                        "icon": "monitor_heart",
                        "link": "/admin/infra/",
                    },
                    {
                        "title": _("Manual"),
                        "icon": "help",
                        "link": "/admin/instrucciones/",
                    },
                ],
            },
            {
                "title": _("Atajos"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Panel GEI"),
                        "icon": "eco",
                        "link": "/admin/gei/panel/",
                    },
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
                    {
                        "title": _("AI Ops"),
                        "icon": "memory",
                        "link": "/admin/ai-ops/eventos/",
                    },
                    {
                        "title": _("Aula web"),
                        "icon": "laptop",
                        "link": "/admin/aula-web/",
                    },
                    {
                        "title": _("Crear curso IA"),
                        "icon": "auto_awesome",
                        "link": "/admin/crear-curso-ia/",
                    },
                ],
            },
        ],
    },
}
