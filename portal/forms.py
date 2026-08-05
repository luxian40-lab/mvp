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
    quitar_wallpaper = forms.BooleanField(
        required=False,
        label='Quitar wallpaper (volver al fondo eki por defecto)',
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
        from portal.utils import guardar_wallpaper_aula

        obj = super().save(commit=False)
        mods = self.cleaned_data.get('portal_modulos') or []
        obj.portal_productos = ','.join(mods) if mods else ''

        uploaded = self.cleaned_data.get('wallpaper_archivo')
        quitar = self.cleaned_data.get('quitar_wallpaper')

        if commit:
            obj.save()
            self.save_m2m()
            if quitar:
                if obj.wallpaper_aula_url:
                    obj.wallpaper_aula_url = ''
                    obj.save(update_fields=['wallpaper_aula_url'])
            elif uploaded:
                try:
                    obj.wallpaper_aula_url = guardar_wallpaper_aula(uploaded, obj.pk)
                except ValueError as exc:
                    raise forms.ValidationError({'wallpaper_archivo': str(exc)}) from exc
                obj.save(update_fields=['wallpaper_aula_url'])
        return obj
