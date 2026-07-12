from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import PortalUsuario
from .provision import generar_password_temporal, provisionar_usuario_portal


class CrearUsuarioPortalForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=150)
    first_name = forms.CharField(
        label='Nombre (opcional)',
        max_length=150,
        required=False,
        help_text='El usuario lo confirmará o cambiará en el primer ingreso.',
    )
    last_name = forms.CharField(label='Apellido (opcional)', max_length=150, required=False)
    email = forms.EmailField(label='Email', required=False)
    password1 = forms.CharField(
        label='Contraseña temporal',
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text='Vacío = se genera automáticamente. Queda visible en admin hasta el primer acceso.',
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(render_value=True),
        required=False,
    )
    rol = forms.ChoiceField(label='Rol en portal', choices=PortalUsuario.ROL_CHOICES, initial='viewer')
    is_active = forms.BooleanField(label='Usuario activo', required=False, initial=True)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre.')
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = (cleaned.get('password1') or '').strip()
        p2 = (cleaned.get('password2') or '').strip()
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError('Las contraseñas no coinciden.')
        else:
            cleaned['password1'] = generar_password_temporal()
        return cleaned

    def save(self, cliente):
        try:
            user, _pu, password_plano = provisionar_usuario_portal(
                cliente=cliente,
                username=self.cleaned_data['username'],
                password=self.cleaned_data.get('password1'),
                first_name=self.cleaned_data.get('first_name', ''),
                last_name=self.cleaned_data.get('last_name', ''),
                email=self.cleaned_data.get('email', ''),
                rol=self.cleaned_data['rol'],
                is_active=self.cleaned_data.get('is_active', True),
                forzar_cambio=True,
            )
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages if hasattr(exc, 'messages') else [str(exc)])
        user._password_plano_provision = password_plano
        return user


class PrimerAccesoPortalForm(forms.Form):
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150, required=False)
    password1 = forms.CharField(label='Nueva contraseña', widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput, min_length=8)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned
