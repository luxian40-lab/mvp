"""
Management command para probar el sistema de evaluación
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
import os

from core.models import (
    Curso, Modulo, Estudiante, Cliente,
    ObjetivoCurso, RubricaEvaluacion, EjercicioPractico, 
    RespuestaEjercicio, InteraccionLog
)
from core.evaluacion_ia import (
    evaluar_ejercicio_numerico,
    evaluar_respuesta_abierta,
    generar_reto_hipotetico,
    generar_pregunta_comprension
)


class Command(BaseCommand):
    help = 'Prueba el sistema de evaluación educativa'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write("CREANDO DATOS DE PRUEBA")
        self.stdout.write("="*60 + "\n")
        
        # Crear cliente
        cliente, _ = Cliente.objects.get_or_create(
            nombre="Cliente Prueba",
            defaults={'telefono': '+573001234567'}
        )
        self.stdout.write(f"Cliente: {cliente.nombre}")
        
        # Crear curso
        curso, _ = Curso.objects.get_or_create(
            nombre="Finanzas para Emprendedores Rurales",
            defaults={
                'descripcion': 'Aprende a gestionar las finanzas de tu negocio rural',
                'cliente': cliente,
                'activo': True
            }
        )
        self.stdout.write(f"Curso: {curso.nombre}")
        
        # Crear módulo
        modulo, _ = Modulo.objects.get_or_create(
            curso=curso,
            numero=1,
            defaults={
                'titulo': 'Calculo de Utilidades',
                'descripcion': 'Aprende a calcular los ingresos, costos y utilidades',
                'contenido': 'Utilidad = Ingresos - Costos'
            }
        )
        self.stdout.write(f"Modulo: {modulo.titulo}")
        
        # Crear objetivo
        objetivo, _ = ObjetivoCurso.objects.get_or_create(
            curso=curso,
            tipo='especifico',
            defaults={
                'descripcion': 'Calcular correctamente ingresos, costos y utilidades',
                'peso_evaluacion': 40,
                'orden': 1
            }
        )
        self.stdout.write(f"✅ Objetivo creado")
        
        # Crear rúbrica
        rubrica, _ = RubricaEvaluacion.objects.get_or_create(
            objetivo=objetivo,
            defaults={
                'nombre': 'Rubrica Comprension Financiera',
                'criterios': {'excelente': {'puntaje': 100}},
                'palabras_clave': 'ingresos, costos, utilidad'
            }
        )
        self.stdout.write(f"✅ Rubrica creada")
        
        # Crear ejercicio numérico
        ejercicio_num, _ = EjercicioPractico.objects.get_or_create(
            modulo=modulo,
            tipo='numerico',
            defaults={
                'objetivo': objetivo,
                'enunciado': 'Juan vendio 200 racimos a $8,000. Costos: $900,000. ¿Cual fue su utilidad?',
                'respuesta_numerica_esperada': Decimal('700000'),
                'tolerancia_porcentual': 5,
                'formula_evaluacion': 'Ingresos - Costos',
                'puntaje_maximo': 100
            }
        )
        self.stdout.write(f"✅ Ejercicio numerico creado")
        
        # Crear estudiante
        estudiante, _ = Estudiante.objects.get_or_create(
            telefono='+573001111111',
            defaults={
                'nombre': 'Maria Lopez',
                'municipio': 'Riosucio',
                'departamento': 'Caldas',
                'cliente': cliente,
                'cedula': '1234567890'
            }
        )
        self.stdout.write(f"✅ Estudiante: {estudiante.nombre}\n")
        
        # Probar evaluación numérica
        self.stdout.write("\n" + "="*60)
        self.stdout.write("🧮 PROBANDO EVALUACION NUMERICA")
        self.stdout.write("="*60 + "\n")
        
        # Caso 1: Correcto
        self.stdout.write("Caso 1: Respuesta correcta (700,000)")
        resultado = evaluar_ejercicio_numerico(
            ejercicio=ejercicio_num,
            respuesta_numerica=Decimal('700000'),
            estudiante=estudiante,
            intento=1
        )
        self.stdout.write(f"   Puntaje: {resultado['puntaje']}/100")
        self.stdout.write(f"   Correcto: {resultado['es_correcto']}")
        self.stdout.write(f"   Diferencia: {resultado['diferencia_porcentual']}%\n")
        
        # Caso 2: Cercano
        self.stdout.write("Caso 2: Respuesta cercana (720,000)")
        resultado = evaluar_ejercicio_numerico(
            ejercicio=ejercicio_num,
            respuesta_numerica=Decimal('720000'),
            estudiante=estudiante,
            intento=2
        )
        self.stdout.write(f"   Puntaje: {resultado['puntaje']}/100")
        self.stdout.write(f"   Correcto: {resultado['es_correcto']}\n")
        
        # Caso 3: Incorrecto
        self.stdout.write("Caso 3: Respuesta incorrecta (500,000)")
        resultado = evaluar_ejercicio_numerico(
            ejercicio=ejercicio_num,
            respuesta_numerica=Decimal('500000'),
            estudiante=estudiante,
            intento=3
        )
        self.stdout.write(f"   Puntaje: {resultado['puntaje']}/100")
        self.stdout.write(f"   Correcto: {resultado['es_correcto']}\n")
        
        # Estadísticas
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📊 ESTADISTICAS DEL SISTEMA")
        self.stdout.write("="*60 + "\n")
        
        self.stdout.write(f"Total cursos: {Curso.objects.count()}")
        self.stdout.write(f"Total modulos: {Modulo.objects.count()}")
        self.stdout.write(f"Total estudiantes: {Estudiante.objects.count()}")
        self.stdout.write(f"Total ejercicios: {EjercicioPractico.objects.count()}")
        self.stdout.write(f"Total respuestas: {RespuestaEjercicio.objects.count()}")
        self.stdout.write(f"Total interacciones: {InteraccionLog.objects.count()}\n")
        
        self.stdout.write(self.style.SUCCESS('\n✅ PRUEBAS COMPLETADAS\n'))
