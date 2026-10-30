"""
Custom Widget para Color Picker en Django Admin
Permite seleccionar colores de forma visual en lugar de escribir códigos hex
"""

from django import forms
from django.utils.html import format_html


class ColorPickerWidget(forms.TextInput):
    """
    Widget personalizado para seleccionar colores
    Usa HTML5 input type="color" para mejor UX
    """
    input_type = 'color'
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'color-picker-input',
            'style': 'width: 60px; height: 40px; cursor: pointer; border: 2px solid #ddd; border-radius: 4px;'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)
    
    def render(self, name, value, attrs=None, renderer=None):
        """Renderiza el color picker con vista previa"""
        # Asegurar que el valor sea un color válido
        color_value = value if value else '#2C3E50'
        
        # Crear HTML del color picker con vista previa
        html = super().render(name, color_value, attrs, renderer)
        
        # Agregar vista previa y texto
        preview_html = format_html(
            '''
            <div style="display: flex; align-items: center; gap: 10px;">
                {}
                <input 
                    type="text" 
                    value="{}" 
                    readonly 
                    style="width: 100px; padding: 8px; border: 2px solid #ddd; border-radius: 4px; font-family: monospace; background: #f5f5f5;"
                >
                <div style="
                    width: 40px;
                    height: 40px;
                    background-color: {};
                    border: 2px solid #ddd;
                    border-radius: 6px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                "></div>
            </div>
            ''',
            html,
            color_value,
            color_value
        )
        
        return preview_html
