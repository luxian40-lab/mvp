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

    class Meta:
        model = Cliente
        exclude = ('portal_productos', 'usar_gamificacion', 'peso_gamificacion_reto', 'peso_gamificacion_abierta')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw = (self.instance.portal_productos or '').strip() if self.instance.pk else ''
        if raw:
            self.fields['portal_modulos'].initial = [
                p.strip() for p in raw.split(',') if p.strip()
            ]

    def save(self, commit=True):
        obj = super().save(commit=False)
        mods = self.cleaned_data.get('portal_modulos') or []
        obj.portal_productos = ','.join(mods) if mods else ''
        if commit:
            obj.save()
            self.save_m2m()
        return obj
