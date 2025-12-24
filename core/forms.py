from django import forms
from .models import Etiqueta


class EtiquetaForm(forms.ModelForm):
    """Form personalizado para Etiqueta con selector de color"""
    
    COLORES_PREDEFINIDOS = [
        ('#667eea', '🟣 Púrpura'),
        ('#f093fb', '🌸 Rosa'),
        ('#4facfe', '🔵 Azul'),
        ('#43e97b', '🟢 Verde'),
        ('#fa709a', '🔴 Rojo'),
        ('#feca57', '🟡 Amarillo'),
        ('#ff6348', '🟠 Naranja'),
        ('#00d2d3', '🔷 Cian'),
        ('#786fa6', '🟣 Lavanda'),
        ('#f8b500', '🟨 Dorado'),
    ]
    
    color = forms.ChoiceField(
        choices=COLORES_PREDEFINIDOS,
        widget=forms.RadioSelect(attrs={'class': 'color-selector'}),
        label='Color de la etiqueta',
        help_text='Selecciona un color para identificar visualmente esta etiqueta'
    )
    
    class Meta:
        model = Etiqueta
        fields = ['nombre', 'color', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Estudiantes Nuevos'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción opcional de la etiqueta'}),
        }
