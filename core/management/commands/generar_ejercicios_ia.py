"""
Management command para generar ejercicios automáticamente con IA
"""

from django.core.management.base import BaseCommand
from core.models import Curso, Modulo, ObjetivoCurso
from core.generador_ejercicios_ia import generar_y_guardar_ejercicios


class Command(BaseCommand):
    help = 'Genera ejercicios automáticamente usando IA basándose en el contenido del curso'

    def add_arguments(self, parser):
        parser.add_argument(
            '--curso-id',
            type=int,
            required=True,
            help='ID del curso para generar ejercicios'
        )
        parser.add_argument(
            '--cantidad',
            type=int,
            default=5,
            help='Cantidad de ejercicios a generar (default: 5)'
        )
        parser.add_argument(
            '--tipo',
            type=str,
            default='mixto',
            choices=['numerico', 'abierto', 'mixto'],
            help='Tipo de ejercicios: numerico, abierto o mixto (default: mixto)'
        )
        parser.add_argument(
            '--modelo',
            type=str,
            default='gpt-4o-mini',
            choices=['gpt-4o-mini', 'gpt-3.5-turbo', 'claude-3-sonnet', 'claude-3-opus'],
            help='Modelo de IA a usar (default: gpt-4o-mini)'
        )

    def handle(self, *args, **options):
        curso_id = options['curso_id']
        cantidad = options['cantidad']
        tipo = options['tipo']
        modelo = options['modelo']
        
        # Validar curso
        try:
            curso = Curso.objects.get(id=curso_id)
        except Curso.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ Curso con ID {curso_id} no existe\n'))
            return
        
        # Verificar que tenga contenido
        modulos = Modulo.objects.filter(curso=curso)
        if not modulos.exists():
            self.stdout.write(self.style.ERROR(
                f'\n❌ El curso "{curso.nombre}" no tiene módulos con contenido.\n'
                'Añade módulos primero desde el admin de Django.\n'
            ))
            return
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'🤖 GENERANDO EJERCICIOS CON IA')
        self.stdout.write('='*60)
        self.stdout.write(f'📚 Curso: {curso.nombre}')
        self.stdout.write(f'🔢 Cantidad: {cantidad} ejercicios')
        self.stdout.write(f'📝 Tipo: {tipo}')
        self.stdout.write(f'🧠 Modelo: {modelo}')
        self.stdout.write('='*60 + '\n')
        
        # Mostrar contenido del curso que se analizará
        self.stdout.write(f'📖 Módulos encontrados: {modulos.count()}')
        for mod in modulos:
            self.stdout.write(f'   • Módulo {mod.numero}: {mod.titulo}')
        
        self.stdout.write('\n' + '⏳ Generando ejercicios con IA...\n')
        
        try:
            # Generar ejercicios
            ejercicios_creados = generar_y_guardar_ejercicios(
                curso=curso,
                cantidad=cantidad,
                tipo_ejercicios=tipo,
                modelo=modelo
            )
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS(f'✅ COMPLETADO'))
            self.stdout.write(f'   Ejercicios creados: {ejercicios_creados}')
            self.stdout.write('='*60 + '\n')
            
            # Mostrar estadísticas
            self.stdout.write('📊 ESTADÍSTICAS DEL CURSO:')
            from core.models import EjercicioPractico
            total_ejercicios = EjercicioPractico.objects.filter(modulo__curso=curso).count()
            numericos = EjercicioPractico.objects.filter(modulo__curso=curso, tipo='numerico').count()
            abiertos = EjercicioPractico.objects.filter(modulo__curso=curso, tipo='abierto').count()
            
            self.stdout.write(f'   Total ejercicios: {total_ejercicios}')
            self.stdout.write(f'   • Numéricos: {numericos}')
            self.stdout.write(f'   • Abiertos: {abiertos}')
            self.stdout.write('')
            
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {e}\n'))
            if 'API_KEY' in str(e):
                self.stdout.write(self.style.WARNING(
                    'Configura las variables de entorno:\n'
                    '  - OPENAI_API_KEY (para GPT)\n'
                    '  - ANTHROPIC_API_KEY (para Claude)\n'
                ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR INESPERADO: {e}\n'))
            import traceback
            traceback.print_exc()
