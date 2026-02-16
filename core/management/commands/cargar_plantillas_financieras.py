"""
Management command para cargar plantillas de ejercicios financieros
"""

from django.core.management.base import BaseCommand
from core.models import Curso, Modulo, ObjetivoCurso, RubricaEvaluacion, EjercicioPractico
from core.plantillas_ejercicios import (
    EJERCICIOS_FINANCIEROS,
    RUBRICAS_FINANCIERAS,
    crear_ejercicio_desde_plantilla
)


class Command(BaseCommand):
    help = 'Carga plantillas de ejercicios financieros en un curso'

    def add_arguments(self, parser):
        parser.add_argument(
            '--curso-id',
            type=int,
            help='ID del curso donde cargar los ejercicios'
        )
        parser.add_argument(
            '--listar',
            action='store_true',
            help='Solo listar plantillas disponibles sin cargar'
        )

    def handle(self, *args, **options):
        
        if options['listar']:
            self._listar_plantillas()
            return
        
        curso_id = options.get('curso_id')
        
        if not curso_id:
            self.stdout.write(self.style.ERROR(
                '\nDebes especificar --curso-id o usar --listar\n'
                'Ejemplo: python manage.py cargar_plantillas_financieras --curso-id 1'
            ))
            return
        
        try:
            curso = Curso.objects.get(id=curso_id)
        except Curso.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\nCurso con ID {curso_id} no existe\n'))
            return
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'CARGANDO PLANTILLAS EN: {curso.nombre}')
        self.stdout.write('='*60 + '\n')
        
        # Crear objetivo general si no existe
        objetivo, created = ObjetivoCurso.objects.get_or_create(
            curso=curso,
            tipo='general',
            defaults={
                'descripcion': 'Aplicar conceptos financieros básicos para gestionar un negocio rural',
                'peso_evaluacion': 100,
                'orden': 1
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Objetivo general creado'))
        else:
            self.stdout.write('Objetivo general ya existe')
        
        # Crear rúbrica si no existe
        rubrica, created = RubricaEvaluacion.objects.get_or_create(
            objetivo=objetivo,
            nombre='Comprensión Financiera Rural',
            defaults={
                'criterios': RUBRICAS_FINANCIERAS['rubrica_conceptos_basicos']['criterios'],
                'palabras_clave': RUBRICAS_FINANCIERAS['rubrica_conceptos_basicos']['palabras_clave']
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Rúbrica creada'))
        else:
            self.stdout.write('Rúbrica ya existe')
        
        # Obtener o crear módulos para los ejercicios
        modulos_creados = 0
        ejercicios_creados = 0
        
        # Módulo 1: Ingresos
        modulo_ingresos, created = Modulo.objects.get_or_create(
            curso=curso,
            numero=1,
            defaults={
                'titulo': 'Cálculo de Ingresos',
                'descripcion': 'Aprende a calcular los ingresos de tu negocio',
                'contenido': '**Ingresos** = Todo el dinero que recibes por ventas.\n\nFórmula: Cantidad × Precio'
            }
        )
        if created: modulos_creados += 1
        
        # Módulo 2: Costos
        modulo_costos, created = Modulo.objects.get_or_create(
            curso=curso,
            numero=2,
            defaults={
                'titulo': 'Cálculo de Costos',
                'descripcion': 'Identifica y suma todos tus gastos',
                'contenido': '**Costos** = Todo el dinero que gastas para producir o vender.\n\nSuma: Materia prima + Transporte + Mano de obra + Otros'
            }
        )
        if created: modulos_creados += 1
        
        # Módulo 3: Utilidad
        modulo_utilidad, created = Modulo.objects.get_or_create(
            curso=curso,
            numero=3,
            defaults={
                'titulo': 'Cálculo de Utilidad',
                'descripcion': 'Calcula tu ganancia real',
                'contenido': '**Utilidad** = Tu ganancia después de restar costos.\n\nFórmula: Ingresos - Costos'
            }
        )
        if created: modulos_creados += 1
        
        # Módulo 4: Precios y Rentabilidad
        modulo_precios, created = Modulo.objects.get_or_create(
            curso=curso,
            numero=4,
            defaults={
                'titulo': 'Precios y Rentabilidad',
                'descripcion': 'Define precios y analiza tu negocio',
                'contenido': '**Precio de Venta** = Costo + Ganancia deseada\n\n**Margen %** = (Ganancia/Costo) × 100'
            }
        )
        if created: modulos_creados += 1
        
        self.stdout.write(f'\n📂 Módulos: {modulos_creados} creados\n')
        
        # Cargar ejercicios
        ejercicios_config = [
            ('calculo_ingresos_basico', modulo_ingresos),
            ('calculo_ingresos_avanzado', modulo_ingresos),
            ('calculo_costos_basico', modulo_costos),
            ('calculo_utilidad_basico', modulo_utilidad),
            ('calculo_utilidad_cafe', modulo_utilidad),
            ('precio_venta_adecuado', modulo_precios),
            ('calculo_margen_ganancia', modulo_precios),
            ('punto_equilibrio', modulo_precios),
        ]
        
        for plantilla_key, modulo in ejercicios_config:
            # Verificar si ya existe
            plantilla = EJERCICIOS_FINANCIEROS[plantilla_key]
            existe = EjercicioPractico.objects.filter(
                modulo=modulo,
                tipo='numerico',
                enunciado=plantilla['enunciado']
            ).exists()
            
            if not existe:
                datos = crear_ejercicio_desde_plantilla(plantilla_key, modulo, objetivo)
                EjercicioPractico.objects.create(**datos)
                ejercicios_creados += 1
                self.stdout.write(self.style.SUCCESS(f'  ✅ {plantilla["titulo"]}'))
            else:
                self.stdout.write(f'  ⏭️  {plantilla["titulo"]} (ya existe)')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ COMPLETADO'))
        self.stdout.write(f'   Módulos creados: {modulos_creados}')
        self.stdout.write(f'   Ejercicios creados: {ejercicios_creados}')
        self.stdout.write('='*60 + '\n')
    
    def _listar_plantillas(self):
        """Lista todas las plantillas disponibles"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📋 PLANTILLAS DISPONIBLES')
        self.stdout.write('='*60 + '\n')
        
        self.stdout.write(self.style.SUCCESS('🧮 EJERCICIOS NUMÉRICOS:'))
        for key, plantilla in EJERCICIOS_FINANCIEROS.items():
            self.stdout.write(f'  • {key}')
            self.stdout.write(f'    {plantilla["titulo"]}')
        
        self.stdout.write('\n' + self.style.SUCCESS('📝 RÚBRICAS:'))
        for key, rubrica in RUBRICAS_FINANCIERAS.items():
            self.stdout.write(f'  • {key}')
            self.stdout.write(f'    {rubrica["nombre"]}')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('Para cargar en un curso:')
        self.stdout.write('python manage.py cargar_plantillas_financieras --curso-id <ID>')
        self.stdout.write('='*60 + '\n')
