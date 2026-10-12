"""Interruptor del admin de agentes. Apagado: las pantallas actuales no cambian."""


def admin_agentes_v2_activo(request=None) -> bool:
    """True con ADMIN_AGENTES_V2, o si un superusuario abrió ?ui=v2.

    ?ui=v1 lo apaga para esa sesión. El resto del personal no lo ve.
    """
    from django.conf import settings

    if bool(getattr(settings, 'ADMIN_AGENTES_V2', False)):
        return True
    if request is None:
        return False
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False) or not user.is_superuser:
        return False
    ui = (request.GET.get('ui') or '').strip()
    sesion = getattr(request, 'session', None)
    if ui == 'v1':
        if sesion is not None:
            sesion.pop('eki_agentes_v2', None)
        return False
    if ui == 'v2':
        if sesion is not None:
            sesion['eki_agentes_v2'] = '1'
        return True
    if sesion is not None and sesion.get('eki_agentes_v2') == '1':
        return True
    return False
