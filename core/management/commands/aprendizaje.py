"""
Comando para ver reporte de aprendizaje continuo de la IA
"""

from django.core.management.base import BaseCommand
from core.learning_system import SistemaAprendizaje


class Command(BaseCommand):
    help = 'Muestra reporte del sistema de aprendizaje continuo'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('📊 REPORTE DE APRENDIZAJE CONTINUO'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        # Generar resumen
        resumen = SistemaAprendizaje.generar_resumen_aprendizaje()
        
        # Mostrar estadísticas generales
        self.stdout.write(f"📅 Periodo: {resumen.get('periodo', 'N/A')}")
        self.stdout.write(f"💬 Total de interacciones: {resumen.get('total_interacciones', 0)}")
        self.stdout.write(f"👥 Estudiantes activos: {resumen.get('estudiantes_activos', 0)}")
        self.stdout.write('\n' + '-'*80 + '\n')
        
        # Temas populares
        self.stdout.write(self.style.SUCCESS('📚 TEMAS MÁS CONSULTADOS:\n'))
        temas = resumen.get('temas_populares', {})
        
        if temas:
            max_count = max(temas.values()) if temas else 1
            for tema, count in list(temas.items())[:10]:
                barra_length = int((count / max_count) * 30)
                barra = '█' * barra_length
                self.stdout.write(f"  {tema:15} │ {count:3} │ {barra}")
        else:
            self.stdout.write("  No hay datos disponibles")
        
        self.stdout.write('\n' + '-'*80 + '\n')
        
        # Preguntas frecuentes
        self.stdout.write(self.style.SUCCESS('❓ PREGUNTAS MÁS FRECUENTES:\n'))
        preguntas = resumen.get('preguntas_frecuentes', [])
        
        if preguntas:
            for i, pregunta_info in enumerate(preguntas, 1):
                pregunta = pregunta_info.get('pregunta', '')
                frecuencia = pregunta_info.get('frecuencia', 0)
                
                # Truncar pregunta si es muy larga
                if len(pregunta) > 60:
                    pregunta = pregunta[:57] + '...'
                
                self.stdout.write(f"  {i}. [{frecuencia}x] {pregunta}")
        else:
            self.stdout.write("  No hay datos suficientes")
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('✅ La IA aprende de cada interacción para mejorar'))
        self.stdout.write('='*80 + '\n')
