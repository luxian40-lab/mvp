#!/usr/bin/env python
"""
Script para cargar datos de demostración en la BD
Uso: python manage.py shell < load_demo_data.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import (
    Cliente, Linea, TemaCampana, Curso, Modulo, PreguntaExamen,
    Estudiante, PerfilGamificacion, Examen
)
from django.contrib.auth.models import User

print("🚀 Iniciando carga de datos de demostración...")

# 1. CREAR TEMA
print("\n✓ Creando temas...")
tema, _ = TemaCampana.objects.get_or_create(
    nombre="Café",
    defaults={
        'emoji': '☕',
        'descripcion': 'Tema sobre cultivo y comercialización de café',
        'activo': True
    }
)

# 2. CREAR CLIENTE
print("✓ Creando cliente...")
cliente, _ = Cliente.objects.get_or_create(
    nombre="Federación Nacional de Café",
    defaults={
        'nit': '860001022',
        'contacto_principal': 'Juan Pérez',
        'email': 'contacto@fnccafe.org',
        'telefono': '+57 1 2345678',
        'activo': True,
        'notas_internas': 'Cliente principal para demostración'
    }
)

# 3. CREAR LÍNEA TELEFÓNICA
print("✓ Creando línea telefónica...")
linea, _ = Linea.objects.get_or_create(
    numero='+573001234567',
    defaults={
        'cliente': cliente,
        'activa': True,
        'descripcion': 'Línea de demostración WhatsApp'
    }
)

# 4. CREAR CURSO
print("✓ Creando curso...")
curso, _ = Curso.objects.get_or_create(
    titulo="Fundamentos del Cultivo de Café",
    defaults={
        'descripcion': 'Curso completo sobre cómo cultivar, cuidar y cosechar café',
        'cliente': cliente,
        'duracion_dias': 30,
        'activo': True
    }
)

# 5. CREAR MÓDULOS
print("✓ Creando módulos...")
modulos_data = [
    {
        'titulo': 'Establecimiento del Cafetal',
        'descripcion': 'Cómo preparar y sembrar café',
        'contenido': '''☕ **LECCIÓN 1: Siembra del Café**

📚 Aprende a establecer tu cafetal correctamente:

📍 **Condiciones ideales:**
   ✓ Altitud: 1.200-2.000 msnm
   ✓ Temperatura: 17-23°C
   ✓ Sombra: 30-50% (con árboles)

🌱 **Preparación:**
   1. Hoyos: 30x30x30 cm
   2. Distancia: 1.5 x 1.5 metros
   3. Abono orgánico en el hoyo

🌳 **Sombrío:**
   • Guamos, nogales, cítricos
   • Controla luz del sol
   • Protege del viento

⏰ **Mejor época:** Inicio de lluvias

💡 **Consejo del tutor:** El café necesita sombra para producir mejor. ¡Preguntas? ¡Escríbeme! 💬'''
    },
    {
        'titulo': 'Mantenimiento y Cuidados',
        'descripcion': 'Plagas, enfermedades y control de maleza',
        'contenido': '''🛡️ **LECCIÓN 2: Proteger tu Cafetal**

Evita plagas y enfermedades comunes:

🐛 **Plagas principales:**
   • Broca del café
   • Minador de la hoja
   • Caracol de tierra

🍂 **Enfermedades:**
   • Roya del café
   • Mancha de hierro
   • Antracnosis

🧹 **Control:**
   ✓ Monitoreo semanal
   ✓ Prácticas culturales
   ✓ Productos orgánicos permitidos'''
    },
    {
        'titulo': 'Cosecha y Poscosecha',
        'descripcion': 'Técnicas de recolección y procesamiento',
        'contenido': '''🌾 **LECCIÓN 3: Cosecha Optima**

Maximiza tu producción:

📅 **Época de cosecha:**
   • Septiembre - Noviembre
   • Grano rojo bien maduro

✋ **Técnicas:**
   ✓ Recolección selectiva
   ✓ Evitar grano verde
   ✓ Bolsas limpias

🏭 **Poscosecha:**
   1. Despulpado
   2. Fermentación (12-24h)
   3. Lavado
   4. Secado'''
    }
]

modulos = []
for i, mod_data in enumerate(modulos_data, 1):
    modulo, _ = Modulo.objects.get_or_create(
        curso=curso,
        numero=i,
        defaults={
            'titulo': mod_data['titulo'],
            'descripcion': mod_data['descripcion'],
            'contenido': mod_data['contenido'],
            'duracion_dias': 7,
            'activo': True
        }
    )
    modulos.append(modulo)

# 6. CREAR PREGUNTAS POR MÓDULO
print("✓ Creando preguntas...")

preguntas_por_modulo = [
    [  # Módulo 1
        {
            'pregunta': '¿Cuál es la temperatura ideal para el cultivo de café?',
            'opcion_a': 'Entre 17°C y 23°C',
            'opcion_b': 'Entre 10°C y 15°C',
            'opcion_c': 'Entre 30°C y 35°C',
            'opcion_d': 'Más de 40°C',
            'respuesta_correcta': 'A'
        },
        {
            'pregunta': '¿A qué altitud crece mejor el café?',
            'opcion_a': '500-1.000 msnm',
            'opcion_b': '1.200-2.000 msnm',
            'opcion_c': 'Más de 3.000 msnm',
            'opcion_d': 'A nivel del mar',
            'respuesta_correcta': 'B'
        },
        {
            'pregunta': '¿Cuál es la distancia ideal entre plantas?',
            'opcion_a': '0.5 x 0.5 metros',
            'opcion_b': '1 x 1 metros',
            'opcion_c': '1.5 x 1.5 metros',
            'opcion_d': '2 x 2 metros',
            'respuesta_correcta': 'C'
        }
    ],
    [  # Módulo 2
        {
            'pregunta': '¿Cuál es la plaga más común del café?',
            'opcion_a': 'Caracol de tierra',
            'opcion_b': 'Broca del café',
            'opcion_c': 'Minador de la hoja',
            'opcion_d': 'Todas las anteriores',
            'respuesta_correcta': 'B'
        },
        {
            'pregunta': '¿Con qué frecuencia debes monitorear tu cafetal?',
            'opcion_a': 'Mensualmente',
            'opcion_b': 'Quincenalmente',
            'opcion_c': 'Semanalmente',
            'opcion_d': 'Diariamente',
            'respuesta_correcta': 'C'
        }
    ],
    [  # Módulo 3
        {
            'pregunta': '¿En qué meses es la mejor época de cosecha?',
            'opcion_a': 'Enero - Marzo',
            'opcion_b': 'Abril - Junio',
            'opcion_c': 'Septiembre - Noviembre',
            'opcion_d': 'Junio - Agosto',
            'respuesta_correcta': 'C'
        },
        {
            'pregunta': '¿Cuánto tiempo toma la fermentación del café?',
            'opcion_a': '2-4 horas',
            'opcion_b': '12-24 horas',
            'opcion_c': '2-3 días',
            'opcion_d': '1 semana',
            'respuesta_correcta': 'B'
        }
    ]
]

for modulo, preguntas_data in zip(modulos, preguntas_por_modulo):
    for i, preg_data in enumerate(preguntas_data, 1):
        PreguntaExamen.objects.get_or_create(
            modulo=modulo,
            pregunta=preg_data['pregunta'],
            defaults={
                'opcion_a': preg_data['opcion_a'],
                'opcion_b': preg_data['opcion_b'],
                'opcion_c': preg_data['opcion_c'],
                'opcion_d': preg_data['opcion_d'],
                'respuesta_correcta': preg_data['respuesta_correcta'],
                'activa': True
            }
        )

# 7. CREAR PERFIL DE GAMIFICACIÓN
print("✓ Creando perfil de gamificación...")
perfil, _ = PerfilGamificacion.objects.get_or_create(
    nombre="Cafetalero Principiante",
    defaults={
        'descripcion': 'Perfil inicial para estudiantes nuevos',
        'activo': True,
        'puntos_por_leccion': 10,
        'puntos_por_quiz': 25,
        'puntos_por_modulo': 50
    }
)

# 8. CREAR ESTUDIANTES DE PRUEBA
print("✓ Creando estudiantes...")
estudiantes_data = [
    {
        'nombre': 'María García',
        'telefono': '+573001111111',
        'email': 'maria@example.com'
    },
    {
        'nombre': 'Carlos López',
        'telefono': '+573002222222',
        'email': 'carlos@example.com'
    },
    {
        'nombre': 'Ana Martínez',
        'telefono': '+573003333333',
        'email': 'ana@example.com'
    }
]

for est_data in estudiantes_data:
    Estudiante.objects.get_or_create(
        telefono=est_data['telefono'],
        defaults={
            'nombre': est_data['nombre'],
            'email': est_data['email'],
            'cliente': cliente,
            'linea': linea,
            'activo': True,
            'perfil_gamificacion': perfil
        }
    )

# 9. CREAR EXAMEN
print("✓ Creando examen...")
examen, _ = Examen.objects.get_or_create(
    curso=curso,
    titulo="Examen Final - Fundamentos del Cultivo de Café",
    defaults={
        'descripcion': 'Evaluación final del curso',
        'duracion_minutos': 30,
        'puntaje_minimo': 70,
        'activo': True
    }
)

print("\n✅ ¡Datos de demostración cargados exitosamente!")
print(f"\n📊 Resumen:")
print(f"   • Cliente: {cliente}")
print(f"   • Curso: {curso}")
print(f"   • Módulos: {len(modulos)}")
print(f"   • Preguntas totales: 8")
print(f"   • Estudiantes: 3")
print(f"   • Perfil de gamificación: {perfil}")
print(f"\n👤 Usuario admin:")
print(f"   Usuario: admin")
print(f"   Contraseña: admin123")
print(f"\n🌐 Accede a: http://127.0.0.1:8000/admin/")
