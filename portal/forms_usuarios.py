from django import forms
from django.contrib.auth import get_user_model

from .models import PortalUsuario


class CrearUsuarioPortalForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=150)
    first_name = forms.CharField(label='Nombre', max_length=150, required=False)
    last_name = forms.CharField(label='Apellido', max_length=150, required=False)
    email = forms.EmailField(label='Email', required=False)
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput)
    rol = forms.ChoiceField(label='Rol', choices=PortalUsuario.ROL_CHOICES, initial='viewer')
    is_active = forms.BooleanField(label='Usuario activo', required=False, initial=True)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre.')
        return username

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned

    def save(self, cliente):
        User = get_user_model()
        user = User(
            username=self.cleaned_data['username'],
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            email=self.cleaned_data.get('email', ''),
            is_staff=False,
            is_superuser=False,
            is_active=self.cleaned_data.get('is_active', True),
        )
        user.set_password(self.cleaned_data['password1'])
        user.save()
        PortalUsuario.objects.create(
            user=user,
            organizacion=cliente,
            rol=self.cleaned_data['rol'],
        )
        return user
