"""
Django Management Command: Enviar recordatorios diarios

Uso:
    python manage.py enviar_recordatorios

Puedes programarlo con cron (Linux) o Task Scheduler (Windows)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import Estudiante
from core.services import enviar_mensaje_proactivo_inteligente


class Command(BaseCommand):
    help = 'Envía recordatorios diarios a estudiantes activos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            default='recordatorio',
            help='Tipo de mensaje: bienvenida, recordatorio, tarea, progreso'
        )
        
        parser.add_argument(
            '--limite',
            type=int,
            default=None,
            help='Límite de estudiantes a procesar (para testing)'
        )

    def handle(self, *args, **options):
        tipo_mensaje = options['tipo']
        limite = options['limite']
        
        self.stdout.write(self.style.SUCCESS(f'\n🚀 Iniciando envío de {tipo_mensaje}s...'))
        
        # Obtener estudiantes activos
        estudiantes = Estudiante.objects.filter(activo=True)
        
        if limite:
            estudiantes = estudiantes[:limite]
            self.stdout.write(f'📊 Limitado a {limite} estudiantes')
        
        total = estudiantes.count()
        exitosos = 0
        fallidos = 0
        
        self.stdout.write(f'📱 Total estudiantes: {total}\n')
        
        for i, estudiante in enumerate(estudiantes, 1):
            self.stdout.write(f'[{i}/{total}] Procesando {estudiante.nombre}...')
            
            try:
                # Personalizar kwargs según tipo de mensaje
                kwargs = self._preparar_kwargs(tipo_mensaje, estudiante)
                
                resultado = enviar_mensaje_proactivo_inteligente(
                    estudiante=estudiante,
                    tipo_mensaje=tipo_mensaje,
                    **kwargs
                )
                
                if resultado.get('exito'):
                    metodo = resultado.get('metodo_usado', 'desconocido')
                    exitosos += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✅ Enviado ({metodo})')
                    )
                else:
                    fallidos += 1
                    error = resultado.get('error', 'Error desconocido')
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Fallido: {error}')
                    )
            
            except Exception as e:
                fallidos += 1
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error: {str(e)}')
                )
        
        # Resumen final
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ COMPLETADO'))
        self.stdout.write(f'Total: {total}')
        self.stdout.write(self.style.SUCCESS(f'Exitosos: {exitosos}'))
        if fallidos > 0:
            self.stdout.write(self.style.ERROR(f'Fallidos: {fallidos}'))
        self.stdout.write('='*60 + '\n')
    
    def _preparar_kwargs(self, tipo_mensaje, estudiante):
        """Prepara kwargs específicos para cada tipo de mensaje"""
        
        if tipo_mensaje == 'bienvenida':
            return {}
        
        elif tipo_mensaje == 'recordatorio':
            # Aquí puedes consultar clases reales del estudiante
            # Por ahora usamos datos de ejemplo
            return {
                'materia': 'Matemáticas',
                'hora': '10:00am',
                'tema': 'Ecuaciones cuadráticas'
            }
        
        elif tipo_mensaje == 'tarea':
            # Puedes consultar tareas pendientes reales
            from core.models import EnvioLog
            
            tarea_pendiente = EnvioLog.objects.filter(
                estudiante=estudiante,
                estado='PENDIENTE'
            ).first()
            
            if tarea_pendiente:
                # Calcular días restantes
                if hasattr(tarea_pendiente, 'fecha_envio'):
                    dias = (tarea_pendiente.fecha_envio.date() - timezone.now().date()).days
                    dias_restantes = str(max(0, dias))
                else:
                    dias_restantes = 'varios'
                
                return {
                    'materia': tarea_pendiente.campana.nombre,
                    'fecha_entrega': tarea_pendiente.fecha_envio.strftime('%d de %B'),
                    'dias_restantes': dias_restantes
                }
            else:
                return {
                    'materia': 'General',
                    'fecha_entrega': 'Próximamente',
                    'dias_restantes': 'varios'
                }
        
        elif tipo_mensaje == 'progreso':
            # Calcular progreso real del estudiante
            from core.models import EnvioLog
            
            total_envios = EnvioLog.objects.filter(estudiante=estudiante).count()
            exitosos = EnvioLog.objects.filter(
                estudiante=estudiante,
                estado='ENVIADO'
            ).count()
            
            tareas_completadas = f"{exitosos}/{total_envios}" if total_envios > 0 else "0/0"
            promedio = "4.5"  # Puedes calcular el promedio real
            
            # Mensaje motivacional según desempeño
            if total_envios > 0:
                porcentaje = (exitosos / total_envios) * 100
                if porcentaje >= 80:
                    mensaje = "¡Excelente trabajo!"
                elif porcentaje >= 60:
                    mensaje = "¡Muy bien, sigue así!"
                else:
                    mensaje = "¡Tú puedes mejorar!"
            else:
                mensaje = "¡Comienza tu aprendizaje!"
            
            return {
                'semana': f"Semana {timezone.now().isocalendar()[1]}",
                'tareas_completadas': tareas_completadas,
                'clases_asistidas': '4/5',  # Puedes calcular real
                'promedio': promedio,
                'mensaje_motivacional': mensaje
            }
        
        return {}
