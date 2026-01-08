"""
Comando Django para ejecutar seguimiento proactivo
Uso: python manage.py seguimiento_estudiantes
"""

from django.core.management.base import BaseCommand
from core.seguimiento_proactivo import ejecutar_seguimiento_proactivo


class Command(BaseCommand):
    help = 'Ejecuta seguimiento proactivo de estudiantes inactivos (estilo Huaku)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔄 Iniciando seguimiento proactivo...'))
        
        try:
            mensajes_enviados = ejecutar_seguimiento_proactivo()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Seguimiento completado. Mensajes enviados: {mensajes_enviados}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en seguimiento: {str(e)}')
            )
