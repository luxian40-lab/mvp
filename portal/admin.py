from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import PortalFeedback, PortalUsuario, ProfesorAula
from .provision import establecer_password_admin, resetear_password_temporal


class PortalUsuarioAdminForm(forms.ModelForm):
    first_name = forms.CharField(
        label='Nombre',
        required=False,
        max_length=150,
        help_text='Nombre visible (User.first_name).',
    )
    last_name = forms.CharField(
        label='Apellido',
        required=False,
        max_length=150,
    )
    nueva_password = forms.CharField(
        label='Nueva contraseña',
        required=False,
        min_length=8,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
        help_text=(
            'Escribe una contraseña para actualizarla ahora mismo. '
            'Si la dejas vacía, no se modifica. Mínimo 8 caracteres.'
        ),
    )
    confirmar_password = forms.CharField(
        label='Confirmar contraseña',
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
    )
    forzar_primer_acceso = forms.BooleanField(
        label='Forzar cambio en el próximo ingreso',
        required=False,
        help_text=(
            'Si marcas esto junto con una nueva contraseña, el usuario deberá '
            'completar /portal/primer-acceso/ (nombre + contraseña nueva). '
            'Sin marcar, la contraseña queda definitiva y usable de inmediato en aula/portal.'
        ),
    )

    class Meta:
        model = PortalUsuario
        fields = (
            'user',
            'organizacion',
            'rol',
            'debe_cambiar_credenciales',
            'password_temporal',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = getattr(self.instance, 'user', None)
        if user and getattr(user, 'pk', None):
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name

    def clean(self):
        cleaned = super().clean()
        pwd = (cleaned.get('nueva_password') or '').strip()
        conf = (cleaned.get('confirmar_password') or '').strip()
        if pwd or conf:
            if pwd != conf:
                raise ValidationError({'confirmar_password': 'Las contraseñas no coinciden.'})
            if len(pwd) < 8:
                raise ValidationError({'nueva_password': 'Mínimo 8 caracteres.'})
        return cleaned


class PortalUsuarioAdminBase(admin.ModelAdmin):
    form = PortalUsuarioAdminForm
    list_display = [
        'user',
        'nombre_completo',
        'organizacion',
        'rol_badge',
        'password_temporal',
        'debe_cambiar_credenciales',
        'aula_web',
    ]
    list_filter = ['rol', 'debe_cambiar_credenciales', 'organizacion']
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'organizacion__nombre',
        'password_temporal',
    ]
    autocomplete_fields = ['user', 'organizacion']
    readonly_fields = ['password_temporal']
    list_per_page = 50
    actions = ['action_resetear_password_temporal']

    fieldsets = (
        (None, {
            'fields': ('user', 'organizacion', 'rol'),
        }),
        ('Nombre de la persona', {
            'fields': ('first_name', 'last_name'),
            'description': 'Actualiza el nombre sin salir a portal clientes ni al flujo de primer acceso.',
        }),
        ('Contraseña', {
            'fields': ('nueva_password', 'confirmar_password', 'forzar_primer_acceso'),
            'description': (
                'Define aquí la contraseña del profesor/usuario. '
                'Si no marcas «forzar cambio», queda lista para /aprende/profesor/ o /portal/.'
            ),
        }),
        ('Primer acceso (referencia)', {
            'fields': ('debe_cambiar_credenciales', 'password_temporal'),
            'description': (
                'La contraseña temporal es solo referencia operativa hasta completar '
                '/portal/primer-acceso/. Nunca uses is_staff en estos usuarios.'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        user = obj.user
        update_fields = []
        first_name = (form.cleaned_data.get('first_name') or '').strip()
        last_name = (form.cleaned_data.get('last_name') or '').strip()
        if user.first_name != first_name:
            user.first_name = first_name
            update_fields.append('first_name')
        if user.last_name != last_name:
            user.last_name = last_name
            update_fields.append('last_name')
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            update_fields.extend(['is_staff', 'is_superuser'])
            self.message_user(
                request,
                f'Se quitó staff/superuser de «{user.username}» (usuarios portal no son admin Django).',
                level=messages.WARNING,
            )
        if update_fields:
            user.save(update_fields=list(dict.fromkeys(update_fields)))

        nueva = (form.cleaned_data.get('nueva_password') or '').strip()
        if nueva:
            try:
                establecer_password_admin(
                    obj,
                    nueva,
                    forzar_primer_acceso=bool(form.cleaned_data.get('forzar_primer_acceso')),
                )
            except ValidationError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
                return
            if form.cleaned_data.get('forzar_primer_acceso'):
                self.message_user(
                    request,
                    f'Contraseña temporal definida para «{user.username}». '
                    'Debe completar primer acceso en el próximo ingreso.',
                    level=messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    f'Contraseña actualizada para «{user.username}». '
                    'Ya puede entrar al aula/portal con esa clave.',
                    level=messages.SUCCESS,
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

    @admin.display(description='Nombre')
    def nombre_completo(self, obj):
        nombre = obj.user.get_full_name().strip()
        return nombre or '—'

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


@admin.register(PortalUsuario)
class PortalUsuarioAdmin(PortalUsuarioAdminBase):
    pass


@admin.register(ProfesorAula)
class ProfesorAulaAdmin(PortalUsuarioAdminBase):
    """Solo profesores del aula: mismo formulario, filtrado por rol=profesor."""

    list_filter = ['debe_cambiar_credenciales', 'organizacion']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(rol='profesor')

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial['rol'] = 'profesor'
        return initial

    def save_model(self, request, obj, form, change):
        if not obj.rol:
            obj.rol = 'profesor'
        # Evitar que desde esta pantalla se creen admins/viewers por accidente.
        if obj.rol != 'profesor':
            obj.rol = 'profesor'
            self.message_user(
                request,
                'Rol forzado a «Profesor» (esta sección solo gestiona profesores del aula).',
                level=messages.INFO,
            )
        super().save_model(request, obj, form, change)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'rol':
            kwargs['choices'] = [('profesor', 'Profesor (solo aula web /aprende/)')]
        return super().formfield_for_choice_field(db_field, request, **kwargs)


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
