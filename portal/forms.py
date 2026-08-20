"""Formularios auxiliares del portal (admin de clientes)."""
from django import forms

from core.gamificacion_modo import MODO_GAMIFICACION_CHOICES
from core.models import Cliente

PORTAL_PRODUCTO_CHOICES = [
    ('cursos', 'Cursos eki'),
    ('gei', 'Inventario GEI'),
    ('nat', 'Agente Nat'),
    ('empleabilidad', 'Empleabilidad territorial'),
]


class ClientePortalAdminForm(forms.ModelForm):
    portal_modulos = forms.MultipleChoiceField(
        choices=PORTAL_PRODUCTO_CHOICES,
        required=False,
        label='Módulos visibles en portal',
        widget=forms.CheckboxSelectMultiple,
        help_text='Si no marca ninguno, se usa solo el tipo de producto principal.',
    )

    modo_gamificacion = forms.ChoiceField(
        choices=MODO_GAMIFICACION_CHOICES,
        required=True,
        label='Modo de gamificación',
        widget=forms.RadioSelect,
        help_text=(
            'Puntos: ranking por puntos. '
            'Calificación 1–5: gamificación por notas y ranking por promedio ponderado (ej. 3,5). '
            'Desactivada: sin gamificación.'
        ),
    )

    wallpaper_archivo = forms.FileField(
        required=False,
        label='Subir imagen de fondo (recomendado)',
        help_text=(
            'Elija el archivo → Guardar. Se sube a S3 y queda activo en Aprende '
            'para estudiantes de esta organización. JPG/PNG/WebP, máx. 2 MB; '
            'ancho recomendado ≥ 1600px.'
        ),
        widget=forms.ClearableFileInput(
            attrs={'accept': 'image/jpeg,image/png,image/webp'}
        ),
    )
    logo_archivo = forms.FileField(
        required=False,
        label='Subir logo (recomendado)',
        help_text=(
            'Elija PNG/JPG/WebP/GIF → Guardar. Se sube a S3 y se ve en portal B2B, '
            'admin y fichas de curso/estudiante. Máx. 5 MB.'
        ),
        widget=forms.ClearableFileInput(
            attrs={'accept': 'image/jpeg,image/png,image/webp,image/gif'}
        ),
    )
    quitar_wallpaper = forms.BooleanField(
        required=False,
        label='Quitar wallpaper (volver al fondo eki por defecto)',
    )
    quitar_logo = forms.BooleanField(
        required=False,
        label='Quitar logo (volver a inicial del nombre)',
    )

    class Meta:
        model = Cliente
        exclude = (
            'portal_productos',
            'usar_gamificacion',
            'peso_gamificacion_reto',
            'peso_gamificacion_abierta',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw = (self.instance.portal_productos or '').strip() if self.instance.pk else ''
        if raw:
            self.fields['portal_modulos'].initial = [
                p.strip() for p in raw.split(',') if p.strip()
            ]
        if 'wallpaper_aula_url' in self.fields:
            self.fields['wallpaper_aula_url'].label = 'O pegar URL pública (opcional)'
            self.fields['wallpaper_aula_url'].help_text = (
                'Solo si la imagen ya está en internet/S3. Si sube un archivo arriba, '
                'la URL se completa sola al guardar.'
            )
            self.fields['wallpaper_aula_url'].required = False
        if 'logo_url' in self.fields:
            self.fields['logo_url'].label = 'O pegar URL del logo (opcional)'
            self.fields['logo_url'].help_text = (
                'Alternativa al archivo. Si sube logo arriba, esta URL se reemplaza al guardar.'
            )
            self.fields['logo_url'].required = False

    def clean_logo_archivo(self):
        f = self.cleaned_data.get('logo_archivo')
        if not f:
            return f
        from portal.utils import LOGO_MAX_BYTES, LOGO_TIPOS_PERMITIDOS

        ct = (getattr(f, 'content_type', '') or '').lower()
        name = (getattr(f, 'name', '') or '').lower()
        ok = ct in LOGO_TIPOS_PERMITIDOS or name.endswith(
            ('.jpg', '.jpeg', '.png', '.webp', '.gif')
        )
        if not ok:
            raise forms.ValidationError('Solo JPG, PNG, WebP o GIF.')
        if f.size > LOGO_MAX_BYTES:
            raise forms.ValidationError('Máximo 5 MB.')
        return f

    def clean_wallpaper_archivo(self):
        f = self.cleaned_data.get('wallpaper_archivo')
        if not f:
            return f
        from portal.utils import WALLPAPER_MAX_BYTES, WALLPAPER_TIPOS_PERMITIDOS

        ct = (getattr(f, 'content_type', '') or '').lower()
        name = (getattr(f, 'name', '') or '').lower()
        ok = ct in WALLPAPER_TIPOS_PERMITIDOS or name.endswith(
            ('.jpg', '.jpeg', '.png', '.webp')
        )
        if not ok:
            raise forms.ValidationError('Solo JPG, PNG o WebP.')
        if f.size > WALLPAPER_MAX_BYTES:
            raise forms.ValidationError('Máximo 2 MB.')
        return f

    def save(self, commit=True):
        obj = super().save(commit=False)
        mods = self.cleaned_data.get('portal_modulos') or []
        obj.portal_productos = ','.join(mods) if mods else ''

        if commit:
            obj.save()
            self.save_m2m()
            if obj.pk:
                self.sync_media_fields(obj)
        return obj

    def sync_media_fields(self, obj):
        """Logo/wallpaper: el admin llama save(commit=False); requiere pk."""
        from portal.utils import guardar_logo_organizacion, guardar_wallpaper_aula

        uploaded_wall = self.cleaned_data.get('wallpaper_archivo')
        quitar_wall = self.cleaned_data.get('quitar_wallpaper')
        uploaded_logo = self.cleaned_data.get('logo_archivo')
        quitar_logo = self.cleaned_data.get('quitar_logo')

        update_fields: list[str] = []
        if quitar_logo:
            if obj.logo_url:
                obj.logo_url = ''
                update_fields.append('logo_url')
        elif uploaded_logo:
            try:
                obj.logo_url = guardar_logo_organizacion(uploaded_logo, obj.pk)
            except ValueError as exc:
                raise forms.ValidationError({'logo_archivo': str(exc)}) from exc
            update_fields.append('logo_url')
        if quitar_wall:
            if obj.wallpaper_aula_url:
                obj.wallpaper_aula_url = ''
                update_fields.append('wallpaper_aula_url')
        elif uploaded_wall:
            try:
                obj.wallpaper_aula_url = guardar_wallpaper_aula(uploaded_wall, obj.pk)
            except ValueError as exc:
                raise forms.ValidationError({'wallpaper_archivo': str(exc)}) from exc
            update_fields.append('wallpaper_aula_url')
        if update_fields:
            obj.save(update_fields=list(dict.fromkeys(update_fields)))
