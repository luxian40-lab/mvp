"""Pestañas Unfold del admin. Cada listado aporta las suyas y calla en el resto."""


def tabs_admin(request):
    from core.admin.campana_meta import tabs_campana_meta
    from core.admin.clientes_v2 import tabs_cliente
    from core.admin.plantilla_meta_admin import tabs_plantilla_meta

    return [*tabs_cliente(request), *tabs_plantilla_meta(request), *tabs_campana_meta(request)]
