from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Campana
from core.services import ejecutar_campana_servicio


class Command(BaseCommand):
    help = 'Ejecuta campañas programadas que estén listas para enviar'

    def handle(self, *args, **options):
        ahora = timezone.now()
        
        # Buscar campañas programadas que no se han ejecutado y su fecha ya pasó
        campanas_pendientes = Campana.objects.filter(
            ejecutada=False,
            fecha_programada__isnull=False,
            fecha_programada__lte=ahora
        )
        
        self.stdout.write(f"🔍 Buscando campañas programadas...")
        self.stdout.write(f"⏰ Fecha actual: {ahora}")
        
        if not campanas_pendientes.exists():
            self.stdout.write(self.style.WARNING('📭 No hay campañas programadas para ejecutar'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'📤 Encontradas {campanas_pendientes.count()} campañas para ejecutar'))
        
        for campana in campanas_pendientes:
            self.stdout.write(f'\n🚀 Ejecutando: {campana.nombre}')
            self.stdout.write(f'📅 Programada para: {campana.fecha_programada}')
            
            try:
                resultados = ejecutar_campana_servicio(campana)
                
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Campaña ejecutada: {resultados["exitosos"]} exitosos, '
                    f'{resultados["fallidos"]} fallidos de {resultados["total"]} total'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error al ejecutar campaña: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Proceso completado'))
