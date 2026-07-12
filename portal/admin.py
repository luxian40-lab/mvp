from django.contrib import admin, messages
from django.utils.html import format_html

from .models import PortalFeedback, PortalUsuario
from .provision import resetear_password_temporal


@admin.register(PortalUsuario)
class PortalUsuarioAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'organizacion',
        'rol_badge',
        'password_temporal',
        'debe_cambiar_credenciales',
        'aula_web',
    ]
    list_filter = ['rol', 'debe_cambiar_credenciales', 'organizacion']
    search_fields = ['user__username', 'user__email', 'organizacion__nombre', 'password_temporal']
    autocomplete_fields = ['user', 'organizacion']
    readonly_fields = ['password_temporal']
    list_per_page = 50
    actions = ['action_resetear_password_temporal']

    fieldsets = (
        (None, {
            'fields': ('user', 'organizacion', 'rol'),
        }),
        ('Primer acceso', {
            'fields': ('debe_cambiar_credenciales', 'password_temporal'),
            'description': (
                'La contraseña temporal es visible solo hasta que el usuario complete '
                '/portal/primer-acceso/. Nunca uses is_staff en estos usuarios.'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        user = obj.user
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=['is_staff', 'is_superuser'])
            self.message_user(
                request,
                f'Se quitó staff/superuser de «{user.username}» (usuarios portal no son admin Django).',
                level=messages.WARNING,
            )

    @admin.action(description='Resetear contraseña temporal (fuerza primer acceso)')
    def action_resetear_password_temporal(self, request, queryset):
        for pu in queryset.select_related('user'):
            pwd = resetear_password_temporal(pu)
            self.message_user(
                request,
                f'{pu.user.username}: temporal = {pwd}',
                level=messages.SUCCESS,
            )

    @admin.display(description='Rol')
    def rol_badge(self, obj):
        colors = {'admin': '#7a4e8e', 'profesor': '#0d9488', 'viewer': '#64748b'}
        color = colors.get(obj.rol, '#64748b')
        return format_html(
            '<span style="background:{}22;color:{};padding:2px 8px;border-radius:6px;font-size:0.8rem;">{}</span>',
            color, color, obj.get_rol_display(),
        )

    @admin.display(description='Aula web')
    def aula_web(self, obj):
        if obj.rol in ('admin', 'profesor'):
            return format_html('<a href="/aprende/profesor/login/" target="_blank">Entrar ↗</a>')
        return '—'


@admin.register(PortalFeedback)
class PortalFeedbackAdmin(admin.ModelAdmin):
    """Comentarios enviados desde /portal/feedback/ por usuarios B2B."""

    list_display = (
        'creado',
        'categoria_badge',
        'organizacion',
        'usuario_info',
        'mensaje_corto',
    )
    list_filter = ('categoria', 'organizacion', 'creado')
    search_fields = (
        'mensaje',
        'organizacion__nombre',
        'usuario__username',
        'usuario__email',
        'usuario__first_name',
        'usuario__last_name',
    )
    readonly_fields = ('organizacion', 'usuario', 'categoria', 'mensaje', 'creado')
    ordering = ('-creado',)
    list_per_page = 50
    date_hierarchy = 'creado'

    fieldsets = (
        (None, {
            'fields': ('categoria', 'organizacion', 'usuario', 'creado'),
        }),
        ('Mensaje', {
            'fields': ('mensaje',),
        }),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='Categoría')
    def categoria_badge(self, obj):
        colores = {
            'bug': ('#fee2e2', '#b91c1c'),
            'mejora': ('#ede9fe', '#6d28d9'),
            'pregunta': ('#dbeafe', '#1d4ed8'),
            'otro': ('#f1f5f9', '#475569'),
        }
        bg, color = colores.get(obj.categoria, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:8px;font-size:0.8rem;">{}</span>',
            bg, color, obj.get_categoria_display(),
        )

    @admin.display(description='Usuario')
    def usuario_info(self, obj):
        if not obj.usuario:
            return '—'
        nombre = obj.usuario.get_full_name() or obj.usuario.username
        email = obj.usuario.email or ''
        if email:
            return format_html('{}<br><span style="color:#64748b;font-size:0.85rem;">{}</span>', nombre, email)
        return nombre

    @admin.display(description='Mensaje')
    def mensaje_corto(self, obj):
        texto = (obj.mensaje or '').replace('\n', ' ')
        if len(texto) > 120:
            texto = texto[:117] + '…'
        return texto
