"""
Comando Django para ver reporte de uso de agentes
Uso: python manage.py reporte_agentes
"""

from django.core.management.base import BaseCommand
from core.agentes.monitoreo_agentes import generar_reporte_agentes, analizar_efectividad_agentes


class Command(BaseCommand):
    help = 'Muestra reporte de uso de agentes IA (monitoreo estilo Huaku)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detallado',
            action='store_true',
            help='Mostrar análisis detallado de efectividad',
        )

    def handle(self, *args, **options):
        # Generar reporte básico
        reporte = generar_reporte_agentes()
        self.stdout.write(reporte)
        
        # Si se solicita análisis detallado
        if options['detallado']:
            self.stdout.write("\n")
            self.stdout.write(self.style.SUCCESS("📈 ANÁLISIS DE EFECTIVIDAD:"))
            self.stdout.write("=" * 60)
            
            analisis = analizar_efectividad_agentes()
            
            for agente, metricas in analisis.items():
                self.stdout.write(f"\n🤖 {agente}:")
                self.stdout.write(f"   • Total usos: {metricas['total_usos']}")
                self.stdout.write(f"   • Tiempo promedio: {metricas['tiempo_promedio_respuesta']}s")
                
            self.stdout.write("\n" + "=" * 60)
