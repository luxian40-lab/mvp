"""
Script para agregar preguntas de validación a los módulos existentes.
Ejecutar: python agregar_preguntas_modulos.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Modulo, PreguntaModulo

# Preguntas para Curso de Café
preguntas_cafe = {
    1: {
        'pregunta': '¿Cuál es la temperatura ideal para el cultivo de café?',
        'opcion_a': 'Entre 17°C y 23°C',
        'opcion_b': 'Entre 10°C y 15°C',
        'opcion_c': 'Entre 30°C y 35°C',
        'opcion_d': 'Más de 40°C',
        'respuesta_correcta': 'A',
        'explicacion': 'El café requiere temperaturas moderadas entre 17°C y 23°C para un crecimiento óptimo.'
    },
    2: {
        'pregunta': '¿Qué indica que el café está listo para cosechar?',
        'opcion_a': 'Los granos están verdes',
        'opcion_b': 'Los granos están rojos cereza',
        'opcion_c': 'Los granos están amarillos',
        'opcion_d': 'Las hojas se caen',
        'respuesta_correcta': 'B',
        'explicacion': 'El punto óptimo de cosecha es cuando los granos alcanzan el color rojo cereza intenso.'
    },
    3: {
        'pregunta': '¿Qué es la técnica Re-Re para control de broca?',
        'opcion_a': 'Regar y Recoger',
        'opcion_b': 'Recolectar Repasando cada 15 días',
        'opcion_c': 'Repetir Revisión',
        'opcion_d': 'Remover Raíces',
        'respuesta_correcta': 'B',
        'explicacion': 'Re-Re significa Recolectar Repasando: revisar cada 15 días para eliminar granos brocados.'
    },
    4: {
        'pregunta': '¿Qué nutriente es más importante en la floración del café?',
        'opcion_a': 'Nitrógeno (N)',
        'opcion_b': 'Fósforo (P)',
        'opcion_c': 'Potasio (K)',
        'opcion_d': 'Calcio (Ca)',
        'respuesta_correcta': 'B',
        'explicacion': 'El Fósforo (P) es crucial en la etapa de floración para el desarrollo de flores y frutos.'
    },
    5: {
        'pregunta': '¿Cuándo se debe podar el café?',
        'opcion_a': 'Durante la cosecha',
        'opcion_b': 'En época de lluvias',
        'opcion_c': 'Después de la cosecha principal',
        'opcion_d': 'Nunca se debe podar',
        'respuesta_correcta': 'C',
        'explicacion': 'La poda debe hacerse después de la cosecha para renovar las ramas productivas.'
    }
}

# Preguntas para Curso de Cacao  
preguntas_cacao = {
    1: {
        'pregunta': '¿Cuánta sombra necesita el cacao?',
        'opcion_a': '10-20%',
        'opcion_b': '30-50%',
        'opcion_c': '70-80%',
        'opcion_d': '100% (sombra total)',
        'respuesta_correcta': 'B',
        'explicacion': 'El cacao requiere sombra moderada del 30-50% para crecer óptimamente.'
    },
    2: {
        'pregunta': '¿Cuánto tarda una mazorca de cacao en madurar?',
        'opcion_a': '1-2 meses',
        'opcion_b': '3-4 meses',
        'opcion_c': '5-6 meses',
        'opcion_d': '8-10 meses',
        'respuesta_correcta': 'C',
        'explicacion': 'Las mazorcas de cacao tardan entre 5-6 meses en madurar completamente.'
    },
    3: {
        'pregunta': '¿Qué enfermedad afecta más al cacao en Colombia?',
        'opcion_a': 'Roya',
        'opcion_b': 'Monilia',
        'opcion_c': 'Broca',
        'opcion_d': 'Sigatoka',
        'respuesta_correcta': 'B',
        'explicacion': 'La Monilia (Moniliophthora roreri) es la principal enfermedad del cacao en Colombia.'
    }
}

def agregar_preguntas():
    """Agrega preguntas a los módulos existentes"""
    print("🎯 Agregando preguntas a módulos de café...")
    
    # Curso de café
    modulos_cafe = Modulo.objects.filter(curso__nombre__icontains='café').order_by('numero')
    for modulo in modulos_cafe:
        if modulo.numero in preguntas_cafe:
            pregunta_data = preguntas_cafe[modulo.numero]
            pregunta, created = PreguntaModulo.objects.get_or_create(
                modulo=modulo,
                pregunta=pregunta_data['pregunta'],
                defaults={
                    'opcion_a': pregunta_data['opcion_a'],
                    'opcion_b': pregunta_data['opcion_b'],
                    'opcion_c': pregunta_data.get('opcion_c', ''),
                    'opcion_d': pregunta_data.get('opcion_d', ''),
                    'respuesta_correcta': pregunta_data['respuesta_correcta'],
                    'explicacion': pregunta_data.get('explicacion', ''),
                    'activa': True
                }
            )
            if created:
                print(f"   ✅ Módulo {modulo.numero}: {modulo.titulo}")
            else:
                print(f"   ⚠️ Módulo {modulo.numero}: Ya tenía pregunta")
    
    print("\n🎯 Agregando preguntas a módulos de cacao...")
    
    # Curso de cacao
    modulos_cacao = Modulo.objects.filter(curso__nombre__icontains='cacao').order_by('numero')
    for modulo in modulos_cacao:
        if modulo.numero in preguntas_cacao:
            pregunta_data = preguntas_cacao[modulo.numero]
            pregunta, created = PreguntaModulo.objects.get_or_create(
                modulo=modulo,
                pregunta=pregunta_data['pregunta'],
                defaults={
                    'opcion_a': pregunta_data['opcion_a'],
                    'opcion_b': pregunta_data['opcion_b'],
                    'opcion_c': pregunta_data.get('opcion_c', ''),
                    'opcion_d': pregunta_data.get('opcion_d', ''),
                    'respuesta_correcta': pregunta_data['respuesta_correcta'],
                    'explicacion': pregunta_data.get('explicacion', ''),
                    'activa': True
                }
            )
            if created:
                print(f"   ✅ Módulo {modulo.numero}: {modulo.titulo}")
            else:
                print(f"   ⚠️ Módulo {modulo.numero}: Ya tenía pregunta")
    
    print("\n✅ COMPLETADO - Preguntas agregadas exitosamente")
    print(f"\nTotal preguntas en DB: {PreguntaModulo.objects.count()}")

if __name__ == '__main__':
    agregar_preguntas()
