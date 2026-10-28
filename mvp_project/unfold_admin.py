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


def _eki_inicio_styles(request):
    return static_safe("admin/css/inicio.css")


def _eki_admin_tones_styles(request):
    return static_safe("admin/css/eki_admin_tones.css")


def _eki_eco_graph_script(request):
    return static_safe("admin/js/eki_eco_graph.js")


def _eki_admin_tones_script(request):
    return static_safe("admin/js/eki_admin_tones.js")


def _eki_copiloto_script(request):
    return static_safe("admin/js/eki_copiloto_chat.js")


def _puede_modelo(codename):
    def _check(request):
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return False
        if user.is_superuser:
            return True
        return user.has_perm(codename)
    return _check


def _laboratorio_visible(request):
    return _es_staff(request)


def _bandeja_visible(request):
    from core.admin.agentes_v2_flag import admin_agentes_v2_activo

    return admin_agentes_v2_activo(request) and _puede_modelo(
        'agents_commercial.view_conversacionragcandidata',
    )(request)


def _es_staff(request):
    user = getattr(request, 'user', None)
    return bool(user and getattr(user, 'is_authenticated', False) and user.is_staff)


def badge_plantillas_meta(request):
    from core.admin.home_data import badge_nav

    return badge_nav(request.user, 'plantillas')


def badge_modulos_borrador(request):
    from core.admin.home_data import badge_nav

    return badge_nav(request.user, 'modulos')


def modulos_nav_activo(request):
    """Módulos sigue resaltado en el listado y en el Module Builder."""
    path = getattr(request, 'path', '') or ''
    return path.startswith('/admin/core/modulo/') or path.startswith('/admin/module-builder/')


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
        "light": lambda request: static_safe("favicons/admin.svg"),
        "dark": lambda request: static_safe("favicons/admin.svg"),
    },
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_BACK_BUTTON": True,
    # Sin THEME forzado → switcher light/dark/auto (sidebar usuario + barra superior vía userlinks override).
    # Paletas/COLORS = branding eki en código; no hay skins Jazzmin.
    "BORDER_RADIUS": "12px",
    # Pestañas de organizaciones y de plantillas Meta. Cada callback devuelve [] fuera de su listado.
    "TABS": "core.admin.unfold_tabs.tabs_admin",
    "ENVIRONMENT": "mvp_project.unfold_admin.environment_callback",
    "DASHBOARD_CALLBACK": "core.views_admin_panel.unfold_dashboard_callback",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "type": "image/svg+xml",
            "href": lambda request: static_safe("favicons/admin.svg"),
        },
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
    "STYLES": [_eki_admin_styles, _eki_admin_tones_styles, _eki_inicio_styles],
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
        "show_all_applications": False,
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
                        "permission": _es_staff,
                    },
                    {
                        "title": _("Conversaciones"),
                        "icon": "forum",
                        "link": "/admin/conversaciones/",
                        "permission": _es_staff,
                    },
                ],
            },
            {
                "title": _("Personas"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Estudiantes"),
                        "icon": "group",
                        "link": reverse_lazy("admin:core_estudiante_changelist"),
                        "permission": _puede_modelo("core.view_estudiante"),
                    },
                    {
                        "title": _("Grupos"),
                        "icon": "groups",
                        "link": reverse_lazy("admin:core_grupoestudiantes_changelist"),
                        "permission": _puede_modelo("core.view_grupoestudiantes"),
                    },
                    {
                        "title": _("Organizaciones"),
                        "icon": "apartment",
                        "link": reverse_lazy("admin:core_cliente_changelist"),
                        "permission": _puede_modelo("core.view_cliente"),
                    },
                ],
            },
            {
                "title": _("Mensajería"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Líneas"),
                        "icon": "call",
                        "link": "/admin/lineas/",
                        "permission": _puede_modelo("core.view_campanameta"),
                    },
                    {
                        "title": _("Campañas"),
                        "icon": "campaign",
                        "link": reverse_lazy("admin:core_campanameta_changelist"),
                        "permission": _puede_modelo("core.view_campanameta"),
                    },
                    {
                        "title": _("Plantillas Meta"),
                        "icon": "article",
                        "link": reverse_lazy("admin:core_plantillameta_changelist"),
                        "permission": _puede_modelo("core.view_plantillameta"),
                        "badge": "mvp_project.unfold_admin.badge_plantillas_meta",
                    },
                    {
                        "title": _("Avisos de módulo"),
                        "icon": "notifications_active",
                        "link": reverse_lazy("admin:core_avisomodulodisponible_changelist"),
                        "permission": _puede_modelo("core.view_avisomodulodisponible"),
                    },
                    {
                        "title": _("Recordatorios de curso"),
                        "icon": "alarm",
                        "link": reverse_lazy("admin:core_recordatoriocurso_changelist"),
                        "permission": _puede_modelo("core.view_recordatoriocurso"),
                    },
                ],
            },
            {
                "title": _("Contenido"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Cursos"),
                        "icon": "school",
                        "link": reverse_lazy("admin:core_curso_changelist"),
                        "permission": _puede_modelo("core.view_curso"),
                    },
                    {
                        "title": _("Módulos"),
                        "icon": "view_timeline",
                        "link": reverse_lazy("admin:core_modulo_changelist"),
                        "active": modulos_nav_activo,
                        "permission": _puede_modelo("core.view_modulo"),
                        "badge": "mvp_project.unfold_admin.badge_modulos_borrador",
                    },
                    {
                        "title": _("Conocimiento de agentes"),
                        "icon": "model_training",
                        "link": reverse_lazy("admin:core_conocimientoagente_changelist"),
                        "permission": _puede_modelo("core.view_conocimientoagente"),
                    },
                    {
                        "title": _("Fichas del negocio"),
                        "icon": "storefront",
                        "link": reverse_lazy("admin:core_fichanegocio_changelist"),
                        "permission": _puede_modelo("core.view_fichanegocio"),
                    },
                    {
                        "title": _("Derivaciones de asesoría"),
                        "icon": "alt_route",
                        "link": reverse_lazy("admin:core_derivacionasesoria_changelist"),
                        "permission": _puede_modelo("core.view_derivacionasesoria"),
                    },
                    {
                        "title": _("Bandeja de revisión"),
                        "icon": "inbox",
                        "link": reverse_lazy(
                            "admin:agents_commercial_conversacionragcandidata_changelist",
                        ),
                        "permission": _bandeja_visible,
                    },
                    {
                        "title": _("Laboratorio"),
                        "icon": "science",
                        "link": "/admin/laboratorio/",
                        "permission": _laboratorio_visible,
                    },
                ],
            },
            {
                "title": _("Medir"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Analítica"),
                        "icon": "analytics",
                        "link": "/admin/dashboard/",
                        "permission": _es_staff,
                    },
                    {
                        "title": _("GEI"),
                        "icon": "eco",
                        "link": "/admin/gei/panel/",
                        "permission": _es_staff,
                    },
                ],
            },
            {
                "title": _("Sistema"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Infraestructura"),
                        "icon": "monitor_heart",
                        "link": "/admin/infra/",
                        "permission": _es_staff,
                    },
                ],
            },
        ],
    },
}
