"""Mixins compartidos para reorganizar el admin sin duplicar permisos."""
from django.contrib.auth import get_permission_codename


class CorePermissionsAdminMixin:
    """
    Modelos proxy en apps nuevas (agents_commercial, analytics, etc.)
    reutilizan permisos core.* sobre la misma tabla — sin migrar roles.
    """

    permissions_app_label = 'core'

    def _has_core_perm(self, request, action):
        if not getattr(request.user, 'is_active', False) or not getattr(request.user, 'is_staff', False):
            return False
        if request.user.is_superuser:
            return True
        codename = get_permission_codename(action, self.opts)
        return request.user.has_perm(f'{self.permissions_app_label}.{codename}')

    def has_module_permission(self, request):
        return self._has_core_perm(request, 'view')

    def has_view_permission(self, request, obj=None):
        return self._has_core_perm(request, 'view')

    def has_add_permission(self, request):
        return self._has_core_perm(request, 'add')

    def has_change_permission(self, request, obj=None):
        return self._has_core_perm(request, 'change')

    def has_delete_permission(self, request, obj=None):
        return self._has_core_perm(request, 'delete')


def register_core_proxy_admin(admin_site, proxy_model, admin_class):
    """Registra un ModelAdmin de core sobre su modelo proxy (sidebar en otra app)."""

    class ProxyAdmin(admin_class, CorePermissionsAdminMixin):
        pass

    admin_site.register(proxy_model, ProxyAdmin)
